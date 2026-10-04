"""Keyless, read-only experiment; never activates a runtime Ask policy.

Run in the answer-worker with scripts and public experiment artifacts mounted
read-only. Private text remains in memory; output contains fixed labels only.
The owner approved the experiment ceilings, not a runtime budget change.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path
import sys
from time import perf_counter

BACKEND = Path('/app') if Path('/app/app').is_dir() else Path(__file__).resolve().parents[1] / 'backend'
sys.path.insert(0, str(BACKEND))

from app.ai.answering import ValidatedAnswerClaim  # noqa: E402
from app.ai.chunking import estimate_tokens  # noqa: E402
from app.ai.local_support import (  # noqa: E402
    LocalSupportUnavailable, LocalSupportVerifier, NliScores, OnnxNliScorer, OnnxQaScorer,
    create_local_support_verifier,
)
from app.config import get_settings  # noqa: E402
from app.database import close_database  # noqa: E402
from evaluate_local_support import _chunk, _rss_bytes  # noqa: E402
from evaluate_private_ask_support_v2 import (  # noqa: E402
    PROBES, _eligible_owner_chunks, select_probe_source,
    nearest_heading_page_span, shortest_contiguous_line_window,
)

MAX_BUNDLE_BYTES = 1024**3
MAX_RSS_BYTES = 2 * 1024**3
MAX_STARTUP_MS = 20_000
MAX_P95_MS = 5_000
PUBLIC_PINS = {
    'nli': ('Xenova/DeBERTa-v3-base-mnli-fever-anli',
            '72a1ce83a0144efaf828b3c3844320a61197a53d',
            'ab9da76bb06054ea6b921560c1ecf5683a9e4d96f0ea73d78d3b4a8990aea882'),
    'qa': ('onnx-community/roberta-base-squad2-ONNX',
           '6d1aeed784b6386659454d3be72de76fad8b73db',
           'b573474247f705a1d0bd21997e690d8b7f8bc4379066fc11498bcdd08f735b6b'),
}
TOKENIZER_PINS = {
    'nli': 'a86f883318afa11c8c10466f1bf4efaeb6ded28a52cbe57217a8fa0d0a2a87df',
    'qa': '2bb1a22cfbe25b8e5a232b7fc4d7fc5073923b45724a5f813b00811bb6620f66',
}


class ReorderedNli:
    """The public candidate exports entailment, neutral, contradiction logits."""

    def __init__(self, scorer: OnnxNliScorer):
        self.scorer = scorer

    def score(self, premise: str, hypothesis: str) -> NliScores:
        raw = self.scorer.score(premise, hypothesis)
        return NliScores(raw.neutral, raw.contradiction, raw.entailment)


def verified_manifest(root: Path) -> tuple[dict[str, dict[str, str]], int]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError('experiment_artifacts_unavailable')
    rows = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    if not isinstance(rows, list) or len(rows) != 8:
        raise ValueError('experiment_manifest_invalid')
    hashes: dict[str, dict[str, str]] = {'nli': {}, 'qa': {}}
    total = 0
    for row in rows:
        role, name = row['role'], row['file']
        if role not in PUBLIC_PINS or name not in {'model.onnx', 'tokenizer.json', 'config.json', 'README.md'}:
            raise ValueError('experiment_manifest_invalid')
        repository, revision, model_hash = PUBLIC_PINS[role]
        if row['repository'] != repository or row['revision'] != revision or name in hashes[role]:
            raise ValueError('experiment_manifest_invalid')
        path = root / role / name
        if (
            (root / role).is_symlink() or path.is_symlink()
            or not path.resolve().is_relative_to(root.resolve())
            or not path.is_file() or path.stat().st_size != row['bytes']
        ):
            raise ValueError('experiment_artifact_invalid')
        total += path.stat().st_size
        if total > MAX_BUNDLE_BYTES:
            raise ValueError('experiment_bundle_limit')
        with path.open('rb') as source:
            digest = hashlib.file_digest(source, 'sha256').hexdigest()
        if (
            digest != row['sha256']
            or (name == 'model.onnx' and digest != model_hash)
            or (name == 'tokenizer.json' and digest != TOKENIZER_PINS[role])
        ):
            raise ValueError('experiment_artifact_digest')
        hashes[role][name] = digest
    config = json.loads((root / 'nli' / 'config.json').read_text(encoding='utf-8'))
    if config.get('id2label') != {'0': 'entailment', '1': 'neutral', '2': 'contradiction'}:
        raise ValueError('experiment_label_order')
    return hashes, total


def verdict(verifier, question, statement, quote, chunk, timings):
    claim = ValidatedAnswerClaim(statement=statement, source_quote=quote, source=chunk)
    started = perf_counter()
    try:
        result = verifier.evaluate(question=question, claims=(claim,), chunks=(chunk,))
        return result.supported, result.reason_code
    except LocalSupportUnavailable:
        return False, 'verifier_unavailable'
    finally:
        timings.append((perf_counter() - started) * 1000)


def case_passes(outcomes: list[tuple[bool, str]], expected: bool) -> bool:
    # An unavailable verifier is not successful evidence abstention.
    return bool(outcomes) and all(
        actual == expected and reason != 'verifier_unavailable'
        for actual, reason in outcomes
    )


async def evaluate(root: Path, fixture: Path, repetitions: int, *, page_spans: bool = False) -> dict:
    hashes, total = verified_manifest(root)
    payload = json.loads(fixture.read_text(encoding='utf-8'))
    public_cases = payload['cases']
    if len(public_cases) != 11 or not 1 <= repetitions <= 3:
        raise ValueError('experiment_corpus_invalid')
    chunks, active, pages, _slots = await _eligible_owner_chunks(with_pages=page_spans)
    selected = [select_probe_source(probe, chunks) for probe in PROBES]
    if len(selected) != 6 or any(state != 'selected' or chunk is None or quote is None for state, chunk, quote in selected):
        raise ValueError('experiment_private_selection')
    page_report = []
    if page_spans:
        page_selected = []
        for probe, (state, chunk, _quote) in zip(PROBES, selected, strict=True):
            page = pages.get(chunk.chunk_id, '')
            kind, span = nearest_heading_page_span(page, probe, chunk)
            if span is None:
                span = shortest_contiguous_line_window(page, probe.quote_terms, max_lines=40)
                kind = 'fixed_exact_concept_window'
            if not span or span not in page or len(span) > 950 or estimate_tokens(span + ' ' + probe.positive) > 360:
                raise ValueError('experiment_page_span_unavailable')
            page_selected.append((state, replace(chunk, content=page, token_count=estimate_tokens(page)), span))
            page_report.append({'case': probe.label, 'span_rule': kind, 'exact_page_slice': True, 'citable_current_chunk': span in chunk.content})
        selected = page_selected
    rss_before = _rss_bytes()
    started = perf_counter()
    baseline = create_local_support_verifier(get_settings().rag_local_support_model_dir)
    nli_raw = OnnxNliScorer(root / 'nli', model_sha256=hashes['nli']['model.onnx'], tokenizer_sha256=hashes['nli']['tokenizer.json'])
    nli = ReorderedNli(nli_raw)
    qa = OnnxQaScorer(root / 'qa', model_sha256=hashes['qa']['model.onnx'], tokenizer_sha256=hashes['qa']['tokenizer.json'])
    startup_ms = (perf_counter() - started) * 1000
    if startup_ms > MAX_STARTUP_MS or _rss_bytes() - rss_before > MAX_RSS_BYTES:
        raise ValueError('experiment_startup_resource_limit')
    reports = []
    variants = [('pinned', baseline),
                ('larger_nli', LocalSupportVerifier(nli, baseline._qa)),
                ('larger_qa', LocalSupportVerifier(baseline._nli, qa)),
                ('larger_both', LocalSupportVerifier(nli, qa))]
    for label, verifier in variants:
        timings, rows = [], []
        positives = wrong_claims = wrong_questions = public_passed = false_accepts = unavailable = 0
        for probe, (_state, chunk, quote) in zip(PROBES, selected, strict=True):
            positive, negative, unrelated = [], [], []
            for _ in range(repetitions):
                positive.append(verdict(verifier, probe.question, probe.positive, quote, chunk, timings))
                negative.append(verdict(verifier, probe.question, probe.negative, quote, chunk, timings))
                unrelated.append(verdict(verifier, 'What is the boiling point of water?', probe.positive, quote, chunk, timings))
            positives += int(all(result[0] for result in positive))
            wrong_claims += int(any(result[0] for result in negative))
            wrong_questions += int(any(result[0] for result in unrelated))
            unavailable += sum(result[1] == 'verifier_unavailable' for result in [*positive, *negative, *unrelated])
            rows.append({'case': probe.label, 'positive': positive[0][1], 'wrong_claim': negative[0][1], 'unrelated_question': unrelated[0][1], 'repeat_stable': len(set(positive)) == len(set(negative)) == len(set(unrelated)) == 1})
            if _rss_bytes() - rss_before > MAX_RSS_BYTES:
                raise ValueError('experiment_memory_limit')
        for case in public_cases:
            chunk = _chunk(case)
            expected = bool(case['expected_supported'])
            outcomes = [verdict(verifier, case['question'], case['statement'], case['source_quote'], chunk, timings) for _ in range(repetitions)]
            public_passed += int(case_passes(outcomes, expected))
            false_accepts += int(not expected and any(actual for actual, _reason in outcomes))
            unavailable += sum(reason == 'verifier_unavailable' for _actual, reason in outcomes)
        p95 = sorted(timings)[max(0, math.ceil(len(timings) * .95) - 1)]
        reports.append({'variant': label, 'positive_passed': positives, 'wrong_claim_accepted': wrong_claims, 'unrelated_question_accepted': wrong_questions, 'public_passed': public_passed, 'public_false_accepts': false_accepts, 'inference_unavailable_count': unavailable, 'p95_ms': round(p95, 2), 'latency_ceiling_passed': p95 <= MAX_P95_MS, 'results': rows})
    return {'status': 'completed', 'runtime_policy_changed': False, 'provider_requests': 0, 'database_writes': 0, 'scope': 'canonical_page_hypothesis_not_current_citations' if page_spans else 'six_reviewed_single_source_pairs_not_model_answer_replay', 'active_space_match': active, 'repetitions': repetitions, 'bundle_bytes': total, 'startup_ms': round(startup_ms, 2), 'rss_increase_mib': round(max(0, _rss_bytes() - rss_before) / 1024**2, 2), 'page_spans': page_report, 'variants': reports}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifacts', type=Path, required=True)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--repetitions', type=int, default=3)
    parser.add_argument('--canonical-page-spans', action='store_true')
    args = parser.parse_args()
    async def run():
        try:
            return await evaluate(args.artifacts, args.fixture, args.repetitions, page_spans=args.canonical_page_spans)
        finally:
            await close_database()
    try:
        report = asyncio.run(run())
    except Exception:
        print('{"status":"experiment_unavailable","runtime_policy_changed":false}')
        return 1
    print(json.dumps(report, separators=(',', ':')))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
