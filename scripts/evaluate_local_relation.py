"""Keyless, read-only local instruction-model experiment; never activates Ask."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
from pathlib import Path
import sys
from time import perf_counter

BACKEND = Path('/app') if Path('/app/app').is_dir() else Path(__file__).resolve().parents[1] / 'backend'
sys.path.insert(0, str(BACKEND))

from app.ai.answering import ValidatedAnswerClaim  # noqa: E402
from app.database import close_database  # noqa: E402
from evaluate_local_support import _chunk, _rss_bytes  # noqa: E402
from evaluate_private_ask_support_v2 import PROBES, _eligible_owner_chunks, select_probe_source  # noqa: E402
from local_relation_candidate import CONFIGURATIONS, OnnxDecisionScorer, RelationVerifier  # noqa: E402

MAX_STARTUP_SECONDS = 20.0
MAX_RSS_BYTES = 2 * 1024**3
MAX_EXPERIMENT_SECONDS = 600.0
FIXTURE_PINS = {
    'product_quality_lane5_local_support_v1.json': 'bc53404526f393580e476cf6930b8771388da3300de3b8454b4d9262a20603cd',
    'local_relation_adversarial_v1.json': 'ab64f20a1329bcba92aab0d9be470c460801ddf9058e64cccffa734c9074facd',
}


def load_fixture(root: Path, name: str):
    path = root / name
    if root.is_symlink() or path.is_symlink() or not path.is_file() or path.stat().st_size > 65536:
        raise ValueError('experiment_fixture_invalid')
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != FIXTURE_PINS[name]:
        raise ValueError('experiment_fixture_identity')
    return json.loads(body)['cases']


def check_resources(started: float, before: int):
    if peak_rss() - before > MAX_RSS_BYTES or perf_counter() - started > MAX_EXPERIMENT_SECONDS:
        raise ValueError('experiment_resource_rejected')


def bounded_case(verifier, question, statement, quote, chunk, *, started: float, before: int):
    check_resources(started, before)
    # Reserve the complete per-case deadline and a cleanup margin before
    # starting; the aggregate budget is not permission for one more full call.
    if perf_counter() - started > MAX_EXPERIMENT_SECONDS - 6.0:
        raise ValueError('experiment_resource_rejected')
    result = evaluate_case(verifier, question, statement, quote, chunk)
    check_resources(started, before)
    return result


def quality_pass(actual: bool, reason: str, expected: bool) -> bool:
    # Safe abstention is reported separately; invalid/uncertain/inconsistent
    # inference is not evidence that the semantic checker recognized a negative.
    return actual == expected and reason not in (
        'verifier_unavailable', 'invalid_source_binding', 'decision_unknown',
        'label_consistency_rejected', 'missing_evidence',
    )


def peak_rss() -> int:
    status = Path('/proc/self/status')
    if status.is_file():
        for line in status.read_text(encoding='utf-8').splitlines():
            if line.startswith('VmHWM:'):
                return int(line.split()[1]) * 1024
    return _rss_bytes()


def evaluate_case(verifier, question, statement, quote, chunk):
    started = perf_counter()
    try:
        claim = ValidatedAnswerClaim(statement=statement, source_quote=quote, source=chunk)
        actual, reason = verifier.evaluate(question=question, claim=claim, chunks=(chunk,))
    except Exception:
        actual, reason = False, 'verifier_unavailable'
    return actual, reason, (perf_counter() - started) * 1000


async def evaluate(root: Path, fixture_root: Path, *, smoke: bool = False):
    before = _rss_bytes()
    started = perf_counter()
    scorer = OnnxDecisionScorer(root)
    startup = perf_counter() - started
    base = {'runtime_policy_changed': False, 'provider_requests': 0, 'database_writes': 0,
            'bundle_bytes': scorer.bundle_bytes, 'startup_ms': round(startup * 1000, 2)}
    if startup > MAX_STARTUP_SECONDS or peak_rss() - before > MAX_RSS_BYTES:
        return {**base, 'status': 'startup_resource_rejected', 'candidate_passed': False}
    maintained = load_fixture(fixture_root, 'product_quality_lane5_local_support_v1.json')
    adversarial = load_fixture(fixture_root, 'local_relation_adversarial_v1.json')
    if len(maintained) != 11 or len(adversarial) != 24:
        raise ValueError('experiment_corpus_invalid')
    if smoke:
        case = maintained[3]
        chunk = _chunk(case)
        verdict = bounded_case(RelationVerifier(scorer, 'joint'), case['question'], case['statement'], case['source_quote'], chunk, started=started, before=before)
        return {**base, 'status': 'cpu_smoke_unavailable' if verdict[1] == 'verifier_unavailable' else 'cpu_smoke_completed',
                'inference_completed': verdict[1] != 'verifier_unavailable',
                'smoke_quality_passed': quality_pass(verdict[0], verdict[1], True),
                'supported': verdict[0], 'reason': verdict[1],
                'verification_ms': round(verdict[2], 2), 'peak_rss_increase_mib': round(max(0, peak_rss() - before) / 1024**2, 2)}
    chunks, active, _pages, _slots = await _eligible_owner_chunks()
    selected = [select_probe_source(probe, chunks) for probe in PROBES]
    if not active or any(state != 'selected' or chunk is None or quote is None for state, chunk, quote in selected):
        raise ValueError('experiment_private_selection')
    reports = []
    for configuration in CONFIGURATIONS:
        verifier = RelationVerifier(scorer, configuration)
        rows, timings = [], []
        repetitions, all_passed = 0, True
        for repetition in range(3):
            repetition_passed = True
            for probe, (_state, chunk, quote) in zip(PROBES, selected, strict=True):
                for kind, question, statement, expected in (
                    ('positive', probe.question, probe.positive, True),
                    ('wrong_claim', probe.question, probe.negative, False),
                    ('unrelated_question', 'What is the boiling point of water?', probe.positive, False),
                ):
                    actual, reason, elapsed = bounded_case(verifier, question, statement, quote, chunk, started=started, before=before)
                    timings.append(elapsed)
                    passed = quality_pass(actual, reason, expected)
                    repetition_passed &= passed
                    rows.append({'corpus': 'private', 'case': probe.label, 'kind': kind, 'repeat': repetition + 1,
                                 'supported': actual, 'reason': reason, 'passed': passed})
            for corpus, cases in (('maintained', maintained), ('adversarial', adversarial)):
                for case in cases:
                    chunk = _chunk(case)
                    actual, reason, elapsed = bounded_case(verifier, case['question'], case['statement'], case['source_quote'], chunk, started=started, before=before)
                    timings.append(elapsed)
                    passed = quality_pass(actual, reason, case['expected_supported'])
                    repetition_passed &= passed
                    rows.append({'corpus': corpus, 'case': case['id'], 'repeat': repetition + 1,
                                 'supported': actual, 'reason': reason, 'passed': passed})
            repetitions += 1
            all_passed &= repetition_passed
            # Failed development configurations cannot satisfy the three-repeat
            # release gate; do not spend time repeating already failed evidence.
            if not repetition_passed:
                break
        private = [row for row in rows if row['corpus'] == 'private' and row['repeat'] == 1]
        p95 = sorted(timings)[math.ceil(len(timings) * .95) - 1]
        reports.append({'configuration': configuration, 'repetitions': repetitions,
                        'private_positive_passed': sum(row['supported'] for row in private if row['kind'] == 'positive'),
                        'private_wrong_claim_accepted': sum(row['supported'] for row in private if row['kind'] == 'wrong_claim'),
                        'private_unrelated_question_accepted': sum(row['supported'] for row in private if row['kind'] == 'unrelated_question'),
                        'maintained_passed_first_repeat': sum(row['passed'] for row in rows if row['corpus'] == 'maintained' and row['repeat'] == 1),
                        'adversarial_passed_first_repeat': sum(row['passed'] for row in rows if row['corpus'] == 'adversarial' and row['repeat'] == 1),
                        'inference_unavailable': sum(row['reason'] == 'verifier_unavailable' for row in rows),
                        'uncertain_or_inconsistent': sum(row['reason'] in ('decision_unknown', 'label_consistency_rejected') for row in rows),
                        'p95_ms': round(p95, 2), 'candidate_passed': all_passed and repetitions == 3 and p95 <= 5000,
                        'results': rows})
        print(json.dumps({'progress': 'configuration_completed', 'configuration': configuration,
                          'positive_passed': reports[-1]['private_positive_passed']}), flush=True)
    return {**base, 'status': 'completed', 'scope': 'single_source_authored_claims_not_model_answer_or_real_query_replay',
            'peak_rss_increase_mib': round(max(0, peak_rss() - before) / 1024**2, 2),
            'candidate_passed': any(report['candidate_passed'] for report in reports), 'configurations': reports}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifacts', type=Path, required=True)
    parser.add_argument('--fixtures', type=Path, required=True)
    parser.add_argument('--cpu-smoke-only', action='store_true')
    args = parser.parse_args()
    async def run():
        try:
            return await evaluate(args.artifacts, args.fixtures, smoke=args.cpu_smoke_only)
        finally:
            await close_database()
    try:
        print(json.dumps(asyncio.run(run()), separators=(',', ':')))
    except Exception as exc:
        # Only these local, fixed classifications may cross the output boundary.
        status = 'experiment_resource_rejected' if isinstance(exc, ValueError) and str(exc) == 'experiment_resource_rejected' else 'experiment_unavailable'
        print(json.dumps({'status': status, 'runtime_policy_changed': False, 'candidate_passed': False}))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
