"""One provider-free public calibration audit; never activates a runtime policy.

All cases and the selection procedure are frozen before inference. No private
Knowledge, provider execution or database access. Output is aggregate only.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import gc
import json
import math
from pathlib import Path
import sys
from time import perf_counter

BACKEND = Path('/app') if Path('/app/app').is_dir() else Path(__file__).resolve().parents[1] / 'backend'
sys.path.insert(0, str(BACKEND))

from app.ai.answering import _source_units  # noqa: E402
from app.ai.local_support import LocalSupportUnavailable  # noqa: E402
from evaluate_local_support import _chunk, _rss_bytes  # noqa: E402
from local_relation_candidate import (  # noqa: E402
    DecisionObservation, MAX_CHECK_SECONDS, MAX_INPUT_TOKENS, OnnxDecisionScorer,
    render_prompt,
)

FIXTURE_NAME = 'local_relation_calibration_v1.json'
FIXTURE_SHA256 = 'f87855899d54ce89f11979fe1876f6c5495c2803f94c886e38de293f39b51369'
MAX_SECONDS = 600.0
MAX_STARTUP_SECONDS = 20.0
MAX_RSS_BYTES = 2 * 1024**3
MIN_LABEL_MASS = .50
MIN_GLOBAL_MARGIN = .01
# Strictest passing floor wins; no additional parameter, prompt or rule search.
CONFIDENCE_FLOORS = (.80, .65, .50, .25, .10)
PROCEDURE_VERSION = 'public_global_label_calibration_v1'


@dataclass(frozen=True)
class Rule:
    confidence_floor: float

    def verdict(self, observed: DecisionObservation) -> bool | None:
        if (observed.label not in ('A', 'B') or observed.confidence < self.confidence_floor
            or observed.label_mass < MIN_LABEL_MASS or observed.winner_margin < MIN_GLOBAL_MARGIN):
            return None
        return observed.label == 'A'


def choose_rule(rows) -> Rule | None:
    if len(rows) != 48 or Counter(expected for _observation, expected in rows) != {True: 24, False: 24}:
        return None
    for floor in CONFIDENCE_FLOORS:
        rule = Rule(floor)
        if all(observation is not None and rule.verdict(observation) == expected
               for observation, expected in rows):
            return rule
    return None


def read_fixture(path: Path):
    if path.name != FIXTURE_NAME or path.is_symlink() or not path.is_file() or path.stat().st_size > 200_000:
        raise ValueError('calibration_fixture_invalid')
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != FIXTURE_SHA256:
        raise ValueError('calibration_fixture_identity')
    cases = json.loads(body)['cases']
    if len(cases) != 96:
        raise ValueError('calibration_fixture_invalid')
    for split in ('calibration', 'heldout'):
        selected = [case for case in cases if case['split'] == split]
        if len(selected) != 48 or Counter(case['expected_supported'] for case in selected) != {True: 24, False: 24}:
            raise ValueError('calibration_fixture_invalid')
    return cases


def prompt_for(case):
    chunk = _chunk(case)
    quote = case['source_quote']
    if quote not in chunk.content or case['quote_start'] != 0 or case['quote_end'] != len(quote):
        raise ValueError('calibration_source_binding')
    units = _source_units((chunk,))
    return render_prompt('joint', {
        'question': case['question'], 'claim': case['statement'], 'selected_quote': quote,
        'source_units': [{'unit_id': unit.unit_id, 'text': unit.source.content[unit.start:unit.end]} for unit in units],
    })


def peak_rss():
    status = Path('/proc/self/status')
    if status.is_file():
        for line in status.read_text(encoding='utf-8').splitlines():
            if line.startswith('VmHWM:'):
                return int(line.split()[1]) * 1024
    return _rss_bytes()


def check_resources(started, before):
    if peak_rss() - before > MAX_RSS_BYTES or perf_counter() - started > MAX_SECONDS - 6:
        raise ValueError('calibration_resource_rejected')


def aggregate(rows):
    observations = [row['observed'] for row in rows if row['observed'] is not None]
    def bins(attribute):
        values = [getattr(value, attribute) for value in observations]
        boundaries = (0, .10, .25, .50, .65, .80, 1.000001)
        return [sum(low <= value < high for value in values) for low, high in zip(boundaries, boundaries[1:])]
    timings = sorted(row['elapsed_ms'] for row in rows)
    return {
        'case_count': len(rows), 'inference_completed': len(observations),
        'expected_positive_count': sum(row['expected'] for row in rows),
        'winner_labels': {label: sum(value.label == label for value in observations) for label in ('A', 'B', 'C')},
        'nonlabel_winner_count': sum(value.label is None for value in observations),
        'correct_global_label_count': sum(value.label == ('A' if row['expected'] else 'B')
            for row in rows if (value := row['observed']) is not None),
        'old_confidence_rule_correct_count': sum(value.confidence >= .80 and value.label == ('A' if row['expected'] else 'B')
            for row in rows if (value := row['observed']) is not None),
        'confidence_bins': bins('confidence'), 'label_mass_bins': bins('label_mass'),
        'global_margin_bins': bins('winner_margin'),
        'failures': dict(Counter(row['reason'] for row in rows if row['reason'] != 'observed')),
        'p95_ms': round(timings[math.ceil(len(timings) * .95) - 1], 2) if timings else None,
    }


def evaluate(root, fixture):
    before, started = _rss_bytes(), perf_counter()
    cases = read_fixture(fixture)
    prompts = [prompt_for(case) for case in cases]
    # Before model inference, reject any complete context that does not fit.
    from tokenizers import Tokenizer
    from local_relation_candidate import PINS
    tokenizer_path = root / 'tokenizer.json'
    if (root.is_symlink() or not root.is_dir() or tokenizer_path.is_symlink()
        or not tokenizer_path.is_file() or tokenizer_path.stat().st_size != PINS['tokenizer.json'][0]):
        raise ValueError('calibration_tokenizer_identity')
    digest = hashlib.sha256()
    with tokenizer_path.open('rb') as source:
        while block := source.read(1024 * 1024):
            digest.update(block)
    if digest.hexdigest() != PINS['tokenizer.json'][1]:
        raise ValueError('calibration_tokenizer_identity')
    tokenizer = Tokenizer.from_file(str(tokenizer_path))
    token_counts = [len(tokenizer.encode(prompt, add_special_tokens=False).ids) for prompt in prompts]
    if any(not 0 < count <= MAX_INPUT_TOKENS for count in token_counts):
        raise ValueError('calibration_complete_input_budget')
    del tokenizer
    gc.collect()
    model_started = perf_counter()
    scorer = OnnxDecisionScorer(root)
    startup = perf_counter() - model_started
    base = {'procedure_version': PROCEDURE_VERSION, 'fixture_sha256': FIXTURE_SHA256,
        'runtime_policy_changed': False, 'provider_requests': 0, 'database_writes': 0,
        'candidate_passed': False, 'startup_ms': round(startup * 1000, 2),
        'bundle_bytes': scorer.bundle_bytes, 'max_complete_input_tokens': max(token_counts),
        'confidence_floors': list(CONFIDENCE_FLOORS), 'minimum_label_mass': MIN_LABEL_MASS,
        'minimum_global_margin': MIN_GLOBAL_MARGIN, 'heldout_evaluated': False,
        'bin_boundaries': [0, .10, .25, .50, .65, .80, 1], 'private_cases_evaluated': 0,
        'release_gate_passed': False}
    if startup > MAX_STARTUP_SECONDS or peak_rss() - before > MAX_RSS_BYTES:
        return {**base, 'status': 'startup_resource_rejected'}
    results = []
    def run_case(case, *, rule=None):
        check_resources(started, before)
        tick = perf_counter()
        observed, reason, verdict = None, 'observed', None
        try:
            # Preflight rejects overflowing complete inputs, but per-case timing
            # also includes exact binding, unit/prompt construction and the rule.
            prompt = prompt_for(case)
            observed = scorer.observe(prompt, deadline=tick + MAX_CHECK_SECONDS)
            verdict = (rule or Rule(.80)).verdict(observed)
            if perf_counter() > tick + MAX_CHECK_SECONDS:
                observed, verdict, reason = None, None, 'experiment_latency_budget'
        except LocalSupportUnavailable as exc:
            safe = {'experiment_input_budget', 'experiment_latency_budget', 'experiment_inference_unavailable', 'experiment_output_invalid'}
            reason = str(exc) if str(exc) in safe else 'experiment_unavailable'
        row = {'observed': observed, 'expected': case['expected_supported'], 'reason': reason,
               'verdict': verdict, 'elapsed_ms': (perf_counter() - tick) * 1000}
        results.append(row)
        check_resources(started, before)
        return row
    try:
        calibration = []
        for case, prompt in zip(cases, prompts, strict=True):
            if case['split'] != 'calibration':
                continue
            row = run_case(case)
            calibration.append(row)
            if row['observed'] is None:
                return {**base, 'status': 'calibration_inference_unavailable', 'calibration': aggregate(calibration),
                        'peak_rss_increase_mib': round(max(0, peak_rss() - before) / 1024**2, 2)}
        rule = choose_rule([(row['observed'], row['expected']) for row in calibration])
        base['calibration'] = aggregate(calibration)
        base['peak_rss_increase_mib'] = round(max(0, peak_rss() - before) / 1024**2, 2)
        if rule is None or base['calibration']['p95_ms'] > 5000:
            return {**base, 'status': 'calibration_no_rule', 'selected_rule': None}
        # Do not read heldout outcomes during selection or update this rule.
        base['selected_rule'] = {'confidence_floor': rule.confidence_floor,
                                'label_mass_minimum': MIN_LABEL_MASS, 'global_margin_minimum': MIN_GLOBAL_MARGIN}
        base['heldout_evaluated'] = True
        heldout = []
        for case, prompt in zip(cases, prompts, strict=True):
            if case['split'] != 'heldout':
                continue
            row = run_case(case, rule=rule)
            heldout.append(row)
            if row['observed'] is None or row['verdict'] != row['expected']:
                return {**base, 'status': 'heldout_rejected', 'heldout': aggregate(heldout),
                        'peak_rss_increase_mib': round(max(0, peak_rss() - before) / 1024**2, 2)}
        summary = aggregate(heldout)
        return {**base, 'status': 'public_completed', 'heldout': summary,
                'candidate_passed': len(heldout) == 48 and summary['p95_ms'] <= 5000,
                'peak_rss_increase_mib': round(max(0, peak_rss() - before) / 1024**2, 2)}
    except ValueError:
        return {**base, 'status': 'calibration_resource_rejected', 'completed': aggregate(results),
                'peak_rss_increase_mib': round(max(0, peak_rss() - before) / 1024**2, 2)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifacts', type=Path, required=True)
    parser.add_argument('--fixture', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = evaluate(args.artifacts, args.fixture)
    except Exception:
        result = {'status': 'calibration_preflight_unavailable', 'candidate_passed': False,
                  'provider_requests': 0, 'database_writes': 0, 'runtime_policy_changed': False}
    print(json.dumps(result, separators=(',', ':')))
    return 0 if result['status'] in ('public_completed', 'calibration_no_rule', 'heldout_rejected') else 1


if __name__ == '__main__':
    raise SystemExit(main())
