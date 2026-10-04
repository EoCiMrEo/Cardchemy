"""Keyless gates for public-only selection and closed heldout/private paths."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
import calibrate_local_relation as audit
import local_relation_candidate as candidate
from app.ai.local_support import LocalSupportUnavailable


def observation(label='A', confidence=.7, mass=.9, margin=.5):
    return candidate.DecisionObservation(label, confidence, mass, margin, 320)


def calibration_rows():
    return [(observation('A' if expected else 'B'), expected)
            for expected in [True] * 24 + [False] * 24]


def test_selects_strictest_predeclared_public_floor_only():
    assert audit.choose_rule(calibration_rows()) == audit.Rule(.65)
    stronger = [(replace(value, confidence=.85), expected) for value, expected in calibration_rows()]
    assert audit.choose_rule(stronger) == audit.Rule(.8)


@pytest.mark.parametrize('label,mass,margin', [(None, .9, .5), ('C', .9, .5), ('B', .9, .5), ('A', .49, .2), ('A', .9, .009)])
def test_unknown_nonlabel_wrong_label_and_nonlabel_competition_block_selection(label, mass, margin):
    rows = calibration_rows()
    rows[0] = (observation(label, min(.4, mass), mass, min(margin, .4)), True)
    assert audit.choose_rule(rows) is None


def test_missing_unbalanced_and_unavailable_cases_do_not_calibrate():
    rows = calibration_rows()
    assert audit.choose_rule(rows[:-1]) is None
    assert audit.choose_rule([(value, True) for value, _expected in rows]) is None
    rows[0] = (None, True)
    assert audit.choose_rule(rows) is None


@pytest.mark.parametrize('change', [
    {'confidence': float('nan')}, {'confidence': float('inf')}, {'label_mass': -.1},
    {'label_mass': .5}, {'winner_margin': .8}, {'input_tokens': 513}, {'label': 'secret-token'},
])
def test_observation_rejects_invalid_numeric_or_label_contract(change):
    with pytest.raises(LocalSupportUnavailable):
        replace(observation(), **change)


def test_uncertain_negative_does_not_count_as_semantic_pass():
    assert audit.Rule(.65).verdict(observation('B', .4, .9, .2)) is None
    summary = audit.aggregate([{'observed': observation(None, .7), 'expected': False,
                               'reason': 'observed', 'elapsed_ms': 1}])
    assert summary['correct_global_label_count'] == 0
    assert summary['old_confidence_rule_correct_count'] == 0
    assert summary['nonlabel_winner_count'] == 1


def prepare_fake_audit(monkeypatch, tmp_path, *, first_wrong=False, heldout_wrong=False, unavailable=False):
    cases = []
    for split in ('calibration', 'heldout'):
        for index, expected in enumerate([True] * 24 + [False] * 24):
            quote = f'Synthetic public source {split} {index}.'
            cases.append({'split': split, 'expected_supported': expected,
                          'question': 'Which synthetic fact applies?', 'statement': quote,
                          'source_quote': quote, 'quote_start': 0, 'quote_end': len(quote)})
    monkeypatch.setattr(audit, 'read_fixture', lambda _path: cases)
    monkeypatch.setattr(audit, 'peak_rss', lambda: 100)
    monkeypatch.setattr(audit, '_rss_bytes', lambda: 100)
    tokenizer_body = b'fake-public-tokenizer'
    (tmp_path / 'tokenizer.json').write_bytes(tokenizer_body)
    monkeypatch.setitem(candidate.PINS, 'tokenizer.json', (len(tokenizer_body), hashlib.sha256(tokenizer_body).hexdigest()))
    import tokenizers
    class Tokenizer:
        @staticmethod
        def from_file(_path):
            return Tokenizer()
        def encode(self, _prompt, **_kwargs):
            return type('Encoded', (), {'ids': [1, 2]})()
    monkeypatch.setattr(tokenizers, 'Tokenizer', Tokenizer)
    calls = []
    class Scorer:
        bundle_bytes = 1
        def __init__(self, _root):
            pass
        def observe(self, prompt, *, deadline):
            index = len(calls)
            calls.append(prompt)
            assert deadline > audit.perf_counter()
            if unavailable:
                raise LocalSupportUnavailable('experiment_inference_unavailable')
            expected = cases[index]['expected_supported']
            wrong = (first_wrong and index == 0) or (heldout_wrong and index == 48)
            return observation('A' if expected != wrong else 'B')
    monkeypatch.setattr(audit, 'OnnxDecisionScorer', Scorer)
    return calls


def test_calibration_failure_keeps_heldout_closed_and_never_opens_private_cases(monkeypatch, tmp_path):
    calls = prepare_fake_audit(monkeypatch, tmp_path, first_wrong=True)
    result = audit.evaluate(tmp_path, tmp_path / 'ignored')
    assert len(calls) == 48 and not result['heldout_evaluated']
    assert result['selected_rule'] is None and not result['candidate_passed']
    assert result['private_cases_evaluated'] == result['provider_requests'] == result['database_writes'] == 0


def test_rule_is_frozen_before_heldout_and_first_heldout_error_stops(monkeypatch, tmp_path):
    calls = prepare_fake_audit(monkeypatch, tmp_path, heldout_wrong=True)
    result = audit.evaluate(tmp_path, tmp_path / 'ignored')
    assert len(calls) == 49 and result['status'] == 'heldout_rejected'
    assert result['selected_rule']['confidence_floor'] == .65 and not result['candidate_passed']


def test_full_public_pass_is_separate_from_release_and_contains_no_source_text(monkeypatch, tmp_path):
    calls = prepare_fake_audit(monkeypatch, tmp_path)
    result = audit.evaluate(tmp_path, tmp_path / 'ignored')
    assert len(calls) == 96 and result['candidate_passed']
    assert not result['release_gate_passed'] and not result['runtime_policy_changed']
    assert result['heldout']['case_count'] == 48 and result['private_cases_evaluated'] == 0
    assert 'Synthetic public source' not in json.dumps(result)


def test_inference_failure_stops_instead_of_counting_a_negative_pass(monkeypatch, tmp_path):
    calls = prepare_fake_audit(monkeypatch, tmp_path, unavailable=True)
    result = audit.evaluate(tmp_path, tmp_path / 'ignored')
    assert len(calls) == 1 and result['status'] == 'calibration_inference_unavailable'
    assert result['calibration']['inference_completed'] == 0 and not result['heldout_evaluated']


def test_total_resource_guard_reserves_full_call_and_cleanup(monkeypatch):
    monkeypatch.setattr(audit, 'peak_rss', lambda: 100)
    monkeypatch.setattr(audit, 'perf_counter', lambda: 595.0)
    with pytest.raises(ValueError, match='calibration_resource_rejected'):
        audit.check_resources(0, 100)


def test_fixture_digest_is_required_before_any_case_is_used(tmp_path):
    path = tmp_path / audit.FIXTURE_NAME
    path.write_text('{"cases": []}', encoding='utf-8')
    with pytest.raises(ValueError, match='calibration_fixture_identity'):
        audit.read_fixture(path)


def fake_observer(logits):
    import numpy as np
    scorer = candidate.OnnxDecisionScorer.__new__(candidate.OnnxDecisionScorer)
    scorer.np = np
    scorer.label_ids = {10: 'A', 20: 'B', 30: 'C'}
    scorer.inputs = {'input_ids': None, 'attention_mask': None, 'position_ids': None}
    scorer.tokenizer = type('Tokenizer', (), {'encode': lambda *_args, **_kwargs: type('Encoded', (), {'ids': [1]})()})()
    scorer.ort = type('Ort', (), {'RunOptions': type('Options', (), {'terminate': False})})()
    class Session:
        def run(self, outputs, feed, options):
            assert outputs == ['logits'] and feed['input_ids'].shape == (1, 1)
            return [logits]
    scorer.session = Session()
    return scorer


def test_full_vocabulary_nonlabel_winner_is_never_forced_to_a_label(capsys):
    import numpy as np
    logits = np.full((1, 1, 151936), -100.0)
    logits[0, 0, [10, 20, 30, 40]] = [2, 1, 0, 3]
    observed = fake_observer(logits).observe('synthetic prompt', deadline=audit.perf_counter() + 5)
    assert observed.label is None
    assert observed.label_mass == pytest.approx((np.exp(2) + np.exp(1) + 1) / (np.exp(3) + np.exp(2) + np.exp(1) + 1))
    assert observed.winner_margin == pytest.approx((np.exp(3) - np.exp(2)) / (np.exp(3) + np.exp(2) + np.exp(1) + 1))
    assert capsys.readouterr().out == ''


def test_label_winner_uses_nonlabel_runner_up_and_existing_decide_cutoff():
    import numpy as np
    logits = np.full((1, 1, 151936), -100.0)
    logits[0, 0, [10, 20, 30, 40]] = [3, 0, -1, 2]
    scorer = fake_observer(logits)
    observed = scorer.observe('synthetic prompt', deadline=audit.perf_counter() + 5)
    assert observed.label == 'A' and observed.confidence < .8
    assert observed.winner_margin == pytest.approx((np.exp(3) - np.exp(2)) / (np.exp(3) + np.exp(2) + 1 + np.exp(-1)))
    assert scorer.decide('synthetic prompt', deadline=audit.perf_counter() + 5) == candidate.Decision('A', False)


@pytest.mark.parametrize('kind', ['nan', 'shape'])
def test_invalid_onnx_output_fails_closed_before_softmax(kind):
    import numpy as np
    logits = np.zeros((1, 1, 151936)) if kind == 'nan' else np.zeros((1, 1, 3))
    logits[0, 0, 0] = float('nan') if kind == 'nan' else 0
    with pytest.raises(LocalSupportUnavailable, match='experiment_output_invalid'):
        fake_observer(logits).observe('synthetic prompt', deadline=audit.perf_counter() + 5)
