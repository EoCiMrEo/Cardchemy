"""One approved, supervised public audit of the pinned CPU Qwen3-4B export.

No provider execution, database access or runtime policy selection. The parent
accepts bounded numerical aggregates only and terminates a stalled child.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import queue
import secrets
import subprocess
import sys
import threading
from time import perf_counter

MAX_SECONDS = 600.0
MAX_STARTUP_SECONDS = 30.0
MAX_CHECK_SECONDS = 10.0
MAX_RSS_BYTES = 4 * 1024**3
MAX_BUNDLE_BYTES = 3 * 1024**3
CLEANUP_SECONDS = 2.0
MAX_MESSAGE_BYTES = 16_384
FIXTURE_SHA256 = 'f87855899d54ce89f11979fe1876f6c5495c2803f94c886e38de293f39b51369'
PROCEDURE_VERSION = 'public_global_label_calibration_v1'
RUNTIME_ONLY_DIAGNOSTIC = 'seven_runtime_files_verified_readme_missing'
DIAGNOSTIC_COMPLETED = 'public_diagnostic_completed'
STATUSES = {
    'public_completed', 'calibration_no_rule', 'heldout_rejected',
    DIAGNOSTIC_COMPLETED,
    'calibration_inference_unavailable', 'calibration_resource_rejected',
    'startup_resource_rejected', 'calibration_preflight_unavailable',
    'supervisor_startup_timeout', 'supervisor_total_timeout',
    'supervisor_memory_rejected', 'supervisor_protocol_rejected',
    'supervisor_child_unavailable', 'supervisor_measurement_unavailable',
}
SAFE_REASONS = {
    'experiment_input_budget', 'experiment_latency_budget',
    'experiment_inference_unavailable', 'experiment_output_invalid',
    'experiment_unavailable',
}


def failure(status, *, runtime_only_diagnostic=False):
    result = {'status': status, 'candidate_passed': False,
            'runtime_policy_changed': False, 'provider_requests': 0,
            'database_writes': 0, 'private_cases_evaluated': 0,
            'release_gate_passed': False, 'heldout_evaluated': False}
    if runtime_only_diagnostic:
        result['incomplete_bundle_diagnostic'] = RUNTIME_ONLY_DIAGNOSTIC
    return result


def numeric(value, *, maximum=1e12):
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= maximum


def count(value, maximum=96):
    return type(value) is int and 0 <= value <= maximum


def validate_aggregate(value, maximum=48):
    required = {'case_count', 'inference_completed', 'expected_positive_count',
                'winner_labels', 'nonlabel_winner_count', 'correct_global_label_count',
                'old_confidence_rule_correct_count', 'confidence_bins',
                'label_mass_bins', 'global_margin_bins', 'failures', 'p95_ms'}
    if type(value) is not dict or set(value) != required:
        return False
    for key in required - {'winner_labels', 'confidence_bins', 'label_mass_bins',
                           'global_margin_bins', 'failures', 'p95_ms'}:
        if not count(value[key], maximum):
            return False
    labels = value['winner_labels']
    if type(labels) is not dict or set(labels) != {'A', 'B', 'C'} or any(not count(v, maximum) for v in labels.values()):
        return False
    for key in ('confidence_bins', 'label_mass_bins', 'global_margin_bins'):
        bins = value[key]
        if type(bins) is not list or len(bins) != 6 or any(not count(v, maximum) for v in bins):
            return False
        if sum(bins) != value['inference_completed']:
            return False
    failures = value['failures']
    if type(failures) is not dict or not set(failures) <= SAFE_REASONS or any(not count(v, maximum) for v in failures.values()):
        return False
    if (sum(labels.values()) + value['nonlabel_winner_count'] != value['inference_completed']
        or value['inference_completed'] + sum(failures.values()) != value['case_count']
        or value['correct_global_label_count'] > value['inference_completed']
        or value['old_confidence_rule_correct_count'] > value['correct_global_label_count']
        or value['expected_positive_count'] > value['case_count']):
        return False
    return (value['p95_ms'] is None and value['case_count'] == 0
            or numeric(value['p95_ms'], maximum=MAX_SECONDS * 1000))


def validate_child_report(report, *, runtime_only_diagnostic=False):
    """Reject content, unknown nested fields and success without complete gates."""
    minimum = set(failure('calibration_preflight_unavailable',
                          runtime_only_diagnostic=runtime_only_diagnostic))
    allowed = minimum | {'procedure_version', 'fixture_sha256', 'startup_ms',
        'bundle_bytes', 'max_complete_input_tokens', 'confidence_floors',
        'minimum_label_mass', 'minimum_global_margin', 'bin_boundaries',
        'calibration', 'heldout', 'completed', 'selected_rule', 'peak_rss_increase_mib'}
    if (type(report) is not dict or not minimum <= set(report) <= allowed
        or type(report['status']) is not str or report['status'] not in STATUSES):
        return False
    if (report.get('incomplete_bundle_diagnostic') !=
        (RUNTIME_ONLY_DIAGNOSTIC if runtime_only_diagnostic else None)):
        return False
    if any(report[key] is not False for key in ('runtime_policy_changed', 'release_gate_passed')):
        return False
    if any(type(report[key]) is not int or report[key] != 0 for key in ('provider_requests', 'database_writes', 'private_cases_evaluated')):
        return False
    if any(type(report[key]) is not bool for key in ('candidate_passed', 'heldout_evaluated')):
        return False
    if runtime_only_diagnostic and report['candidate_passed']:
        return False
    if (report['status'] == DIAGNOSTIC_COMPLETED and not runtime_only_diagnostic
        or report['status'] == 'public_completed' and runtime_only_diagnostic):
        return False
    if 'procedure_version' in report and report['procedure_version'] != PROCEDURE_VERSION:
        return False
    if 'fixture_sha256' in report and report['fixture_sha256'] != FIXTURE_SHA256:
        return False
    for key, maximum in (('startup_ms', MAX_SECONDS * 1000), ('bundle_bytes', MAX_BUNDLE_BYTES),
                         ('max_complete_input_tokens', 512), ('peak_rss_increase_mib', 8192)):
        if key in report and not numeric(report[key], maximum=maximum):
            return False
    for key, expected in (('confidence_floors', [.8, .65, .5, .25, .1]),
                          ('minimum_label_mass', .5), ('minimum_global_margin', .01),
                          ('bin_boundaries', [0, .1, .25, .5, .65, .8, 1])):
        if key in report and report[key] != expected:
            return False
    for key in ('calibration', 'heldout', 'completed'):
        if key in report and not validate_aggregate(report[key], 96 if key == 'completed' else 48):
            return False
    rule = report.get('selected_rule')
    if rule is not None and (type(rule) is not dict
        or set(rule) != {'confidence_floor', 'label_mass_minimum', 'global_margin_minimum'}
        or rule['confidence_floor'] not in [.8, .65, .5, .25, .1]
        or rule['label_mass_minimum'] != .5 or rule['global_margin_minimum'] != .01):
        return False
    if report['heldout_evaluated'] and (rule is None or 'heldout' not in report):
        return False
    if report['candidate_passed'] or report['status'] == DIAGNOSTIC_COMPLETED:
        success_required = {'procedure_version', 'fixture_sha256', 'selected_rule',
                            'bundle_bytes', 'max_complete_input_tokens',
                            'confidence_floors', 'minimum_label_mass',
                            'minimum_global_margin', 'bin_boundaries'}
        if (not success_required <= set(report)
            or report['status'] != (DIAGNOSTIC_COMPLETED if runtime_only_diagnostic else 'public_completed')
            or not report['heldout_evaluated']
            or report.get('startup_ms', math.inf) > MAX_STARTUP_SECONDS * 1000
            or report.get('peak_rss_increase_mib', math.inf) > MAX_RSS_BYTES / 1024**2):
            return False
        for key in ('calibration', 'heldout'):
            summary = report.get(key, {})
            if (summary.get('case_count') != 48 or summary.get('expected_positive_count') != 24
                or summary.get('correct_global_label_count') != 48
                or summary.get('winner_labels') != {'A': 24, 'B': 24, 'C': 0}
                or summary.get('nonlabel_winner_count') != 0
                or summary.get('failures') != {}
                or not numeric(summary.get('p95_ms'), maximum=MAX_CHECK_SECONDS * 1000)):
                return False
    return True


def process_peak(pid):
    """Linux process high-water RSS; absence never fabricates a zero reading."""
    try:
        for line in Path(f'/proc/{pid}/status').read_text(encoding='ascii').splitlines():
            if line.startswith('VmHWM:'):
                return int(line.split()[1]) * 1024
    except (OSError, ValueError):
        return None
    return None


def run_case(case, scorer, rule, *, absolute_deadline, prompt_for, peak_rss, before):
    tick = perf_counter()
    deadline = min(tick + MAX_CHECK_SECONDS, absolute_deadline - CLEANUP_SECONDS)
    if deadline <= tick or peak_rss() - before > MAX_RSS_BYTES:
        raise ValueError('calibration_resource_rejected')
    observed, reason, verdict = None, 'observed', None
    from app.ai.local_support import LocalSupportUnavailable
    try:
        prompt = prompt_for(case)
        observed = scorer.observe(prompt, deadline=deadline)
        verdict = rule.verdict(observed)
        if perf_counter() > deadline:
            observed, verdict, reason = None, None, 'experiment_latency_budget'
    except LocalSupportUnavailable as exc:
        reason = str(exc) if str(exc) in SAFE_REASONS else 'experiment_unavailable'
    row = {'observed': observed, 'expected': case['expected_supported'],
           'reason': reason, 'verdict': verdict, 'elapsed_ms': (perf_counter() - tick) * 1000}
    if perf_counter() > absolute_deadline - CLEANUP_SECONDS or peak_rss() - before > MAX_RSS_BYTES:
        raise ValueError('calibration_resource_rejected')
    return row


def evaluate(root, fixture, *, started, emit_startup, runtime_only_diagnostic=False):
    backend = Path('/app') if Path('/app/app').is_dir() else Path(__file__).resolve().parents[1] / 'backend'
    sys.path.insert(0, str(backend))
    import calibrate_local_relation as public
    import local_relation_4b_candidate as candidate
    absolute_deadline = started + MAX_SECONDS
    before = public._rss_bytes()
    cases = public.read_fixture(fixture)
    # Complete heldout inputs may be size-checked before inference; their model
    # outcomes remain closed until the selected public rule is frozen.
    # The constructor validates every pinned artifact before allocating the
    # tokenizer/session. Reuse that verified tokenizer, avoiding a second full
    # graph/data hash or tokenizer allocation inside the startup budget.
    scorer = (candidate.Onnx4BDecisionScorer(root, runtime_only_diagnostic=True)
              if runtime_only_diagnostic else candidate.Onnx4BDecisionScorer(root))
    counts = [len(scorer.tokenizer.encode(public.prompt_for(case), add_special_tokens=False).ids) for case in cases]
    if any(not 0 < value <= 512 for value in counts):
        raise ValueError('calibration_complete_input_budget')
    startup = perf_counter() - started
    base = {**failure('calibration_no_rule', runtime_only_diagnostic=runtime_only_diagnostic),
        'procedure_version': PROCEDURE_VERSION,
        'fixture_sha256': FIXTURE_SHA256, 'startup_ms': round(startup * 1000, 2),
        'bundle_bytes': scorer.bundle_bytes, 'max_complete_input_tokens': max(counts),
        'confidence_floors': list(public.CONFIDENCE_FLOORS), 'minimum_label_mass': public.MIN_LABEL_MASS,
        'minimum_global_margin': public.MIN_GLOBAL_MARGIN, 'bin_boundaries': [0, .1, .25, .5, .65, .8, 1]}
    if startup > MAX_STARTUP_SECONDS or public.peak_rss() - before > MAX_RSS_BYTES:
        return {**base, 'status': 'startup_resource_rejected'}
    emit_startup({'event': 'startup_completed'})
    rows = []
    def one(case, rule):
        if perf_counter() + MAX_CHECK_SECONDS + CLEANUP_SECONDS > absolute_deadline:
            raise ValueError('calibration_resource_rejected')
        row = run_case(case, scorer, rule, absolute_deadline=absolute_deadline,
                       prompt_for=public.prompt_for, peak_rss=public.peak_rss, before=before)
        rows.append(row)
        return row
    def finish(status, **values):
        return {**base, **values, 'status': status,
                'peak_rss_increase_mib': round(max(0, public.peak_rss() - before) / 1024**2, 2)}
    try:
        calibration = []
        for case in cases:
            if case['split'] != 'calibration':
                continue
            row = one(case, public.Rule(.8))
            calibration.append(row)
            if row['observed'] is None:
                return finish('calibration_inference_unavailable', calibration=public.aggregate(calibration))
        summary = public.aggregate(calibration)
        base['calibration'] = summary
        rule = public.choose_rule([(row['observed'], row['expected']) for row in calibration])
        if rule is None or summary['p95_ms'] > MAX_CHECK_SECONDS * 1000:
            return finish('calibration_no_rule', selected_rule=None)
        base['selected_rule'] = {'confidence_floor': rule.confidence_floor,
            'label_mass_minimum': public.MIN_LABEL_MASS, 'global_margin_minimum': public.MIN_GLOBAL_MARGIN}
        base['heldout_evaluated'] = True
        emit_startup({'event': 'heldout_started'})
        heldout = []
        for case in cases:
            if case['split'] != 'heldout':
                continue
            row = one(case, rule)
            heldout.append(row)
            if row['observed'] is None or row['verdict'] != row['expected']:
                return finish('heldout_rejected', heldout=public.aggregate(heldout))
        heldout_summary = public.aggregate(heldout)
        observed_quality = len(heldout) == 48 and heldout_summary['p95_ms'] <= MAX_CHECK_SECONDS * 1000
        return finish(DIAGNOSTIC_COMPLETED if runtime_only_diagnostic else 'public_completed',
                      heldout=heldout_summary,
                      candidate_passed=observed_quality and not runtime_only_diagnostic)
    except ValueError:
        # If resource rejection follows heldout opening, preserve its aggregate.
        values = {'completed': public.aggregate(rows)}
        if base['heldout_evaluated']:
            values['heldout'] = public.aggregate([row for row in rows[48:]])
        return finish('calibration_resource_rejected', **values)


def _messages(stream, mailbox):
    try:
        for _index in range(4):
            line = stream.readline(MAX_MESSAGE_BYTES + 1)
            if not line:
                mailbox.put(('eof', None))
                return
            if len(line) > MAX_MESSAGE_BYTES or not line.endswith(b'\n'):
                mailbox.put(('invalid', None))
                return
            try:
                value = json.loads(line)
            except (ValueError, UnicodeError):
                mailbox.put(('invalid', None))
                return
            mailbox.put(('message', value))
        mailbox.put(('invalid', None))
    except (OSError, ValueError):
        mailbox.put(('invalid', None))


def stop_child(child, absolute_deadline, *, terminate=True):
    try:
        if terminate and child.poll() is None:
            child.kill()
        remaining = max(.01, min(CLEANUP_SECONDS, absolute_deadline - perf_counter()))
        child.wait(timeout=remaining)
    except subprocess.TimeoutExpired:
        try:
            if child.poll() is None:
                child.kill()
        except OSError:
            pass
        return False
    except OSError:
        return False
    return True


def supervise(root, fixture, *, runtime_only_diagnostic=False):
    def fail(status):
        return failure(status, runtime_only_diagnostic=runtime_only_diagnostic)

    if sys.platform != 'linux':
        return fail('calibration_preflight_unavailable')
    started = perf_counter()
    absolute_deadline = started + MAX_SECONDS
    parent_before = process_peak(os.getpid())
    if parent_before is None:
        return fail('calibration_preflight_unavailable')
    allowed_env = {'PATH', 'PYTHONPATH', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'LANG', 'LC_ALL'}
    env = {key: value for key, value in os.environ.items() if key in allowed_env}
    env.update(PYTHONUNBUFFERED='1', PYTHONDONTWRITEBYTECODE='1')
    # ORM types transitively construct Settings/engine without connecting. Use
    # independent disposable process values; no operator credentials or root
    # environment file reach the child, and loopback port 1 is not the app DB.
    env.update(ENVIRONMENT='test', SECRET_KEY=secrets.token_urlsafe(48),
               GENERATION_SOURCE_ENCRYPTION_KEY=secrets.token_urlsafe(32),
               DATABASE_URL='postgresql+asyncpg://offline:offline@127.0.0.1:1/offline_test',
               FLASHCARD_AI_PROVIDER_ENABLED='false', RAG_ASK_ENABLED='false')
    child = None
    result = fail('supervisor_child_unavailable')
    maximum = 0
    memory_measured = False
    heldout_started = False
    try:
        command = [sys.executable, str(Path(__file__).resolve()), '--worker',
            '--artifacts', str(root), '--fixture', str(fixture), '--started', str(started)]
        if runtime_only_diagnostic:
            command.append('--runtime-only-diagnostic')
        child = subprocess.Popen(command,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env)
        mailbox = queue.Queue(maxsize=5)
        reader = threading.Thread(target=_messages, args=(child.stdout, mailbox), daemon=True)
        reader.start()
        ready, final, normal_eof, heldout_started = False, None, False, False
        while True:
            now = perf_counter()
            if now >= absolute_deadline - CLEANUP_SECONDS:
                result = fail('supervisor_total_timeout')
                break
            if not ready and now >= started + MAX_STARTUP_SECONDS:
                result = fail('supervisor_startup_timeout')
                break
            child_peak, parent_peak = process_peak(child.pid), process_peak(os.getpid())
            if child_peak is not None and parent_peak is not None:
                memory_measured = True
                maximum = max(maximum, child_peak + max(0, parent_peak - parent_before))
                if maximum > MAX_RSS_BYTES:
                    result = fail('supervisor_memory_rejected')
                    break
            elif child.poll() is None:
                result = fail('supervisor_measurement_unavailable')
                break
            try:
                kind, message = mailbox.get(timeout=min(.05, absolute_deadline - CLEANUP_SECONDS - now))
            except queue.Empty:
                continue
            if kind == 'eof':
                normal_eof = True
                result = final if final is not None else fail('supervisor_child_unavailable')
                break
            if kind != 'message':
                result = fail('supervisor_protocol_rejected')
                break
            if message == {'event': 'startup_completed'} and not ready and final is None:
                ready = True
                continue
            if message == {'event': 'heldout_started'} and ready and not heldout_started and final is None:
                heldout_started = True
                continue
            if (type(message) is not dict or set(message) != {'event', 'report'}
                or message['event'] != 'completed' or final is not None
                or not validate_child_report(message['report'],
                                             runtime_only_diagnostic=runtime_only_diagnostic)):
                result = fail('supervisor_protocol_rejected')
                break
            final = message['report']
            if ((final['candidate_passed'] or final['status'] == DIAGNOSTIC_COMPLETED) and not ready
                or final['heldout_evaluated'] != heldout_started):
                result = fail('supervisor_protocol_rejected')
                break
        stopped = stop_child(child, absolute_deadline, terminate=not normal_eof)
        if not stopped or child.returncode != 0:
            result = (fail('supervisor_child_unavailable')
                      if result.get('candidate_passed') or result['status'] == DIAGNOSTIC_COMPLETED
                      else result)
        if perf_counter() > absolute_deadline:
            result = fail('supervisor_total_timeout')
        if (result.get('candidate_passed') or result['status'] == DIAGNOSTIC_COMPLETED) and not memory_measured:
            result = fail('supervisor_measurement_unavailable')
    except (OSError, ValueError):
        result = fail('supervisor_child_unavailable')
    finally:
        if child is not None:
            stop_child(child, absolute_deadline)
            if child.stdout is not None:
                child.stdout.close()
    if result['status'].startswith('supervisor_'):
        # Without a validated final message, an unconsumed progress event could
        # precede a kill. Never assert that heldout stayed untouched in that case.
        result['heldout_evaluated'] = True if heldout_started else None
    # This conservative guard counts the entire child's high-water RSS plus
    # parent high-water growth; it is stricter than subtracting a child baseline.
    return {**result, 'supervisor_child_peak_plus_parent_growth_mib':
            round(maximum / 1024**2, 2) if memory_measured else None,
            'supervisor_elapsed_ms': round((perf_counter() - started) * 1000, 2)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifacts', type=Path, required=True)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--runtime-only-diagnostic', action='store_true',
                        help='Explicit public-only audit with seven pinned runtime files and absent README; never qualifies the candidate')
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--started', type=float, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        def emit(value):
            print(json.dumps(value, separators=(',', ':')), flush=True)
        try:
            if args.started is None or not math.isfinite(args.started):
                raise ValueError('invalid_supervisor_origin')
            result = evaluate(args.artifacts, args.fixture, started=args.started,
                              emit_startup=emit,
                              runtime_only_diagnostic=args.runtime_only_diagnostic)
        except Exception:
            result = failure('calibration_preflight_unavailable',
                             runtime_only_diagnostic=args.runtime_only_diagnostic)
        emit({'event': 'completed', 'report': result})
        return 0
    result = supervise(args.artifacts, args.fixture,
                       runtime_only_diagnostic=args.runtime_only_diagnostic)
    print(json.dumps(result, separators=(',', ':')))
    return 0 if result.get('status') in {
        'public_completed', DIAGNOSTIC_COMPLETED, 'calibration_no_rule', 'heldout_rejected',
    } else 1


if __name__ == '__main__':
    raise SystemExit(main())
