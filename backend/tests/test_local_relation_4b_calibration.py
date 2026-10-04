"""No-model contracts for the supervised, public-only 4B audit.

All processes, model scorers and clocks are fakes. No download, inference,
provider execution, database access or runtime activation is performed.
"""
import io
import json
from pathlib import Path
import queue
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
import calibrate_local_relation as public
import calibrate_local_relation_4b as audit
from app.ai.local_support import LocalSupportUnavailable
from local_relation_candidate import DecisionObservation


def observation(label='A', confidence=.7, mass=.9, margin=.5):
    return DecisionObservation(label, confidence, mass, margin, 320)


def aggregate(count=48):
    rows = [{'observed': observation('A' if index < count // 2 else 'B'),
             'expected': index < count // 2, 'reason': 'observed', 'elapsed_ms': 1}
            for index in range(count)]
    return public.aggregate(rows)


def success_report():
    return {**audit.failure('public_completed'), 'candidate_passed': True, 'heldout_evaluated': True,
        'procedure_version': audit.PROCEDURE_VERSION, 'fixture_sha256': audit.FIXTURE_SHA256,
        'startup_ms': 1000, 'bundle_bytes': 100, 'max_complete_input_tokens': 320,
        'confidence_floors': [.8, .65, .5, .25, .1], 'minimum_label_mass': .5,
        'minimum_global_margin': .01, 'bin_boundaries': [0, .1, .25, .5, .65, .8, 1],
        'calibration': aggregate(), 'heldout': aggregate(),
        'selected_rule': {'confidence_floor': .65, 'label_mass_minimum': .5, 'global_margin_minimum': .01},
        'peak_rss_increase_mib': 1024}


def diagnostic_report():
    return {**success_report(), 'status': audit.DIAGNOSTIC_COMPLETED,
            'candidate_passed': False,
            'incomplete_bundle_diagnostic': audit.RUNTIME_ONLY_DIAGNOSTIC}


def test_frozen_public_fixture_and_experimental_budgets_match_owner_approval():
    assert audit.FIXTURE_SHA256 == public.FIXTURE_SHA256 == 'f87855899d54ce89f11979fe1876f6c5495c2803f94c886e38de293f39b51369'
    fixture = Path(__file__).parent / 'fixtures/rag_eval/local_relation_calibration_v1.json'
    cases = public.read_fixture(fixture)
    assert len(cases) == 96
    assert [sum(case['split'] == split for case in cases) for split in ('calibration', 'heldout')] == [48, 48]
    assert audit.MAX_SECONDS == 600 and audit.MAX_STARTUP_SECONDS == 30
    assert audit.MAX_CHECK_SECONDS == 10 and audit.MAX_RSS_BYTES == 4 * 1024**3


@pytest.mark.parametrize('tick,absolute,expected', [(100, 600, 110), (595, 600, 598)])
def test_complete_case_deadline_is_capped_by_absolute_budget(monkeypatch, tick, absolute, expected):
    clock = [tick]
    monkeypatch.setattr(audit, 'perf_counter', lambda: clock[0])
    events = []
    def prompt(case):
        events.append('binding_and_render')
        clock[0] += 1
        return 'synthetic prompt'
    class Scorer:
        def observe(self, supplied, *, deadline):
            assert supplied == 'synthetic prompt' and deadline == expected
            events.append('tokenize_and_inference')
            clock[0] += .5
            return observation()
    class Rule:
        def verdict(self, observed):
            events.append('rule')
            clock[0] += .25
            return True
    row = audit.run_case({'expected_supported': True}, Scorer(), Rule(), absolute_deadline=absolute,
                         prompt_for=prompt, peak_rss=lambda: 100, before=100)
    assert events == ['binding_and_render', 'tokenize_and_inference', 'rule']
    assert row['elapsed_ms'] == 1750 and row['verdict'] is True


def test_overrunning_complete_check_is_unknown_not_a_successful_negative(monkeypatch):
    clock = [100]
    monkeypatch.setattr(audit, 'perf_counter', lambda: clock[0])
    class Scorer:
        def observe(self, _prompt, *, deadline):
            clock[0] = deadline + .01
            return observation('B')
    row = audit.run_case({'expected_supported': False}, Scorer(), public.Rule(.65), absolute_deadline=600,
                         prompt_for=lambda case: 'synthetic', peak_rss=lambda: 100, before=100)
    assert row['observed'] is None and row['verdict'] is None
    assert row['reason'] == 'experiment_latency_budget'


@pytest.mark.parametrize('clock,peak', [(599, 100), (100, 100 + 4 * 1024**3 + 1)])
def test_case_resource_rejection_happens_before_model(monkeypatch, clock, peak):
    monkeypatch.setattr(audit, 'perf_counter', lambda: clock)
    class Forbidden:
        def observe(self, *args, **kwargs):
            raise AssertionError('resource rejection must precede inference')
    with pytest.raises(ValueError, match='calibration_resource_rejected'):
        audit.run_case({'expected_supported': False}, Forbidden(), public.Rule(.8), absolute_deadline=600,
                       prompt_for=lambda case: 'synthetic', peak_rss=lambda: peak, before=100)


def test_unknown_inference_does_not_use_exception_text_as_reason(monkeypatch):
    monkeypatch.setattr(audit, 'perf_counter', lambda: 100)
    class Scorer:
        def observe(self, *args, **kwargs):
            raise LocalSupportUnavailable('private arbitrary error body')
    row = audit.run_case({'expected_supported': False}, Scorer(), public.Rule(.8), absolute_deadline=600,
                         prompt_for=lambda case: 'synthetic', peak_rss=lambda: 100, before=100)
    assert row['reason'] == 'experiment_unavailable' and row['observed'] is None
    assert 'private' not in json.dumps({key: value for key, value in row.items() if key != 'observed'})


def fake_evaluate(monkeypatch, *, wrong_calibration=False, wrong_heldout=False, unknown_heldout=False,
                  startup_seconds=0, runtime_only_diagnostic=False):
    cases = [{'split': split, 'expected_supported': expected}
             for split in ('calibration', 'heldout') for expected in [True] * 24 + [False] * 24]
    monkeypatch.setattr(public, 'read_fixture', lambda path: cases)
    monkeypatch.setattr(public, 'prompt_for', lambda case: 'Synthetic public prompt')
    monkeypatch.setattr(public, '_rss_bytes', lambda: 100)
    monkeypatch.setattr(public, 'peak_rss', lambda: 100)
    clock = [0.0]
    monkeypatch.setattr(audit, 'perf_counter', lambda: clock[0])
    import tokenizers
    monkeypatch.setattr(tokenizers, 'Tokenizer', SimpleNamespace(from_file=lambda path: SimpleNamespace(
        encode=lambda prompt, **kwargs: SimpleNamespace(ids=[1, 2]))))
    calls = []
    class Scorer:
        bundle_bytes = 100
        def __init__(self, _root, *, runtime_only_diagnostic=False):
            assert runtime_only_diagnostic is fake_runtime_only_diagnostic
            self.tokenizer = SimpleNamespace(encode=lambda prompt, **kwargs: SimpleNamespace(ids=[1, 2]))
            clock[0] = startup_seconds
        def observe(self, _prompt, *, deadline):
            index = len(calls)
            calls.append(index)
            expected = cases[index]['expected_supported']
            if index == 48 and unknown_heldout:
                return observation('C')
            wrong = (index == 0 and wrong_calibration) or (index == 48 and wrong_heldout)
            return observation('A' if expected != wrong else 'B')
    monkeypatch.setitem(sys.modules, 'local_relation_4b_candidate', SimpleNamespace(
        verify_artifacts=lambda root: None, Onnx4BDecisionScorer=Scorer))
    fake_runtime_only_diagnostic = runtime_only_diagnostic
    startup = []
    result = audit.evaluate(Path('public-model'), Path('public-fixture'), started=0,
                            emit_startup=startup.append,
                            runtime_only_diagnostic=runtime_only_diagnostic)
    return calls, startup, result


def test_calibration_failure_keeps_heldout_closed(monkeypatch):
    calls, startup, result = fake_evaluate(monkeypatch, wrong_calibration=True)
    assert len(calls) == 48 and startup == [{'event': 'startup_completed'}]
    assert result['status'] == 'calibration_no_rule' and result['selected_rule'] is None
    assert not result['heldout_evaluated'] and not result['candidate_passed']


def test_startup_above_30_seconds_never_emits_ready_or_runs_cases(monkeypatch):
    calls, startup, result = fake_evaluate(monkeypatch, startup_seconds=30.001)
    assert calls == [] and startup == []
    assert result['status'] == 'startup_resource_rejected' and not result['candidate_passed']


@pytest.mark.parametrize('unknown', [False, True])
def test_first_wrong_or_unknown_heldout_stops_with_frozen_rule(monkeypatch, unknown):
    calls, startup, result = fake_evaluate(monkeypatch, wrong_heldout=not unknown, unknown_heldout=unknown)
    assert len(calls) == 49 and result['status'] == 'heldout_rejected'
    assert result['selected_rule']['confidence_floor'] == .65
    assert not result['candidate_passed'] and result['heldout']['case_count'] == 1


def test_all_96_public_passes_do_not_activate_release_or_private_cases(monkeypatch):
    calls, startup, result = fake_evaluate(monkeypatch)
    assert len(calls) == 96 and result['status'] == 'public_completed' and result['candidate_passed']
    assert not result['release_gate_passed'] and not result['runtime_policy_changed']
    assert result['private_cases_evaluated'] == result['provider_requests'] == result['database_writes'] == 0
    assert audit.validate_child_report(result)
    assert 'Synthetic public prompt' not in json.dumps(result)


def test_runtime_only_diagnostic_can_observe_96_cases_but_never_pass_candidate(monkeypatch):
    calls, startup, result = fake_evaluate(monkeypatch, runtime_only_diagnostic=True)
    assert len(calls) == 96 and startup == [
        {'event': 'startup_completed'}, {'event': 'heldout_started'},
    ]
    assert result['status'] == audit.DIAGNOSTIC_COMPLETED
    assert result['incomplete_bundle_diagnostic'] == audit.RUNTIME_ONLY_DIAGNOSTIC
    assert not result['candidate_passed'] and not result['release_gate_passed']
    assert result['calibration']['correct_global_label_count'] == 48
    assert result['heldout']['correct_global_label_count'] == 48
    assert audit.validate_child_report(result, runtime_only_diagnostic=True)
    assert not audit.validate_child_report(result)


def test_runtime_only_diagnostic_failure_keeps_heldout_closed(monkeypatch):
    calls, startup, result = fake_evaluate(monkeypatch, wrong_calibration=True,
                                           runtime_only_diagnostic=True)
    assert len(calls) == 48 and startup == [{'event': 'startup_completed'}]
    assert result['status'] == 'calibration_no_rule' and not result['heldout_evaluated']
    assert result['incomplete_bundle_diagnostic'] == audit.RUNTIME_ONLY_DIAGNOSTIC


@pytest.mark.parametrize('change', [
    {'candidate_passed': True},
    {'incomplete_bundle_diagnostic': 'complete'},
    {'status': 'public_completed'},
    {'heldout_evaluated': False},
])
def test_runtime_only_diagnostic_report_cannot_claim_complete_gate(change):
    assert not audit.validate_child_report({**diagnostic_report(), **change},
                                           runtime_only_diagnostic=True)


@pytest.mark.parametrize('field', ['fixture_sha256', 'procedure_version', 'selected_rule'])
def test_success_report_requires_frozen_identity_and_selected_rule(field):
    report = success_report()
    del report[field]
    assert not audit.validate_child_report(report)


@pytest.mark.parametrize('change', [
    {'startup_ms': 30001}, {'peak_rss_increase_mib': 4096.01},
    {'provider_requests': 1}, {'database_writes': 1}, {'private_cases_evaluated': 1},
    {'runtime_policy_changed': True}, {'release_gate_passed': True},
    {'source_text': 'private payload'}, {'fixture_sha256': 'wrong'},
])
def test_child_success_rejects_resource_overrun_or_untrusted_content(change):
    report = {**success_report(), **change}
    assert not audit.validate_child_report(report)


def test_success_report_rejects_p95_or_uncertain_case_counts():
    report = success_report()
    report['heldout']['p95_ms'] = 10001
    assert not audit.validate_child_report(report)
    report = success_report()
    report['heldout']['correct_global_label_count'] = 47
    assert not audit.validate_child_report(report)


@pytest.mark.parametrize('split', ['calibration', 'heldout'])
def test_balanced_complete_success_cannot_claim_all_labels_are_positive(split):
    report = success_report()
    report[split]['winner_labels'] = {'A': 48, 'B': 0, 'C': 0}
    # Generic count accounting still fits, but 48 correct labels with 24
    # positives and 24 negatives requires exactly 24 A and 24 B decisions.
    assert not audit.validate_child_report(report)


def test_completed_resource_aggregate_can_cover_96_without_qualifying():
    report = {**audit.failure('calibration_resource_rejected'), 'completed': aggregate(96)}
    assert audit.validate_child_report(report)
    assert not report['candidate_passed']


@pytest.mark.parametrize('body', [b'private raw output\n', b'{"event":"startup_completed","private":"payload"}\n',
                                  b'x' * (audit.MAX_MESSAGE_BYTES + 1)])
def test_child_stream_accepts_only_bounded_json_protocol(body):
    mailbox = queue.Queue()
    audit._messages(io.BytesIO(body), mailbox)
    kind, value = mailbox.get_nowait()
    if kind == 'message':
        assert value != {'event': 'startup_completed'}
    else:
        assert kind == 'invalid' and value is None


def fake_supervisor(monkeypatch, *, startup=False, final=None, timeout_after=31, peak=100,
                    runtime_only_diagnostic=False):
    clock = [0.0]
    monkeypatch.setattr(audit, 'perf_counter', lambda: clock[0])
    monkeypatch.setattr(audit.sys, 'platform', 'linux')
    monkeypatch.setattr(audit, 'process_peak', lambda pid: 100 if pid == 123 else peak)
    monkeypatch.setattr(audit.os, 'getpid', lambda: 123)
    events = []
    if startup:
        events.append(('message', {'event': 'startup_completed'}))
    if final is not None:
        if final.get('heldout_evaluated'):
            events.append(('message', {'event': 'heldout_started'}))
        events.extend([('message', {'event': 'completed', 'report': final}), ('eof', None)])
    class Mailbox:
        def __init__(self, **kwargs):
            self.events = list(events)
        def get(self, timeout):
            if self.events:
                return self.events.pop(0)
            clock[0] = timeout_after
            raise queue.Empty
    class Thread:
        def __init__(self, **kwargs):
            pass
        def start(self):
            pass
    class Child:
        pid = 456
        returncode = None
        stdout = io.BytesIO()
        killed = False
        wait_timeouts = []
        def poll(self):
            return self.returncode
        def kill(self):
            self.killed = True
            self.returncode = -9
        def wait(self, timeout):
            self.wait_timeouts.append(timeout)
            if final is not None and not self.killed:
                self.returncode = 0
            return self.returncode
    child = Child()
    def popen(command, **kwargs):
        assert '--worker' in command and kwargs['stderr'] == audit.subprocess.DEVNULL
        assert ('--runtime-only-diagnostic' in command) is runtime_only_diagnostic
        assert not any(name.endswith('API_KEY') for name in kwargs['env'])
        assert kwargs['env']['DATABASE_URL'] == 'postgresql+asyncpg://offline:offline@127.0.0.1:1/offline_test'
        assert kwargs['env']['RAG_ASK_ENABLED'] == 'false' and kwargs['env']['FLASHCARD_AI_PROVIDER_ENABLED'] == 'false'
        return child
    monkeypatch.setattr(audit.subprocess, 'Popen', popen)
    monkeypatch.setattr(audit.queue, 'Queue', Mailbox)
    monkeypatch.setattr(audit.threading, 'Thread', Thread)
    return child, audit.supervise(Path('public-model'), Path('public-fixture'),
                                  runtime_only_diagnostic=runtime_only_diagnostic)


def test_supervisor_kills_missing_startup_by_30_seconds(monkeypatch):
    child, report = fake_supervisor(monkeypatch)
    assert child.killed and report['status'] == 'supervisor_startup_timeout'
    assert report['supervisor_elapsed_ms'] == 31000
    assert all(timeout <= 2 for timeout in child.wait_timeouts)


def test_supervisor_absolute_total_budget_is_independent_of_startup_event(monkeypatch):
    child, report = fake_supervisor(monkeypatch, startup=True, timeout_after=599)
    assert child.killed and report['status'] == 'supervisor_total_timeout'
    assert report['supervisor_elapsed_ms'] == 599000


def test_supervisor_kills_child_above_memory_ceiling(monkeypatch):
    child, report = fake_supervisor(monkeypatch, peak=4 * 1024**3 + 1)
    assert child.killed and report['status'] == 'supervisor_memory_rejected'


def test_missing_child_memory_measurement_fails_closed_and_never_fabricates_zero(monkeypatch):
    child, report = fake_supervisor(monkeypatch, peak=None)
    assert child.killed and report['status'] == 'supervisor_measurement_unavailable'
    assert report['supervisor_child_peak_plus_parent_growth_mib'] is None
    assert not report['candidate_passed']


def test_supervisor_rejects_unknown_child_content_without_echo(monkeypatch):
    child, report = fake_supervisor(monkeypatch, startup=True, final={**success_report(), 'private_body': 'marker'})
    assert child.killed and report['status'] == 'supervisor_protocol_rejected'
    assert 'marker' not in json.dumps(report)


def test_normal_eof_waits_for_clean_exit_without_killing_success(monkeypatch):
    child, report = fake_supervisor(monkeypatch, startup=True, final=success_report())
    assert not child.killed and child.returncode == 0
    assert report['status'] == 'public_completed' and report['candidate_passed']


def test_supervisor_keeps_runtime_only_diagnostic_incomplete(monkeypatch):
    child, report = fake_supervisor(monkeypatch, startup=True, final=diagnostic_report(),
                                    runtime_only_diagnostic=True)
    assert not child.killed and child.returncode == 0
    assert report['status'] == audit.DIAGNOSTIC_COMPLETED
    assert not report['candidate_passed'] and not report['release_gate_passed']
    assert report['incomplete_bundle_diagnostic'] == audit.RUNTIME_ONLY_DIAGNOSTIC


def test_runtime_only_diagnostic_cannot_pass_without_startup_event(monkeypatch):
    child, report = fake_supervisor(monkeypatch, final=diagnostic_report(),
                                    runtime_only_diagnostic=True)
    assert child.killed and report['status'] == 'supervisor_protocol_rejected'
    assert report['incomplete_bundle_diagnostic'] == audit.RUNTIME_ONLY_DIAGNOSTIC
