"""One-shot offline audit of within-question source ranking, not Ask runtime.

The public packet contains invented passages only. This script neither reads the
application database nor imports an application model or provider. By default
it validates the fixture and pinned public bundle without model inference.
The parent process freezes identities and supervises a single child. Run the
approved inference only in an isolated, networkless, resource-limited container.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
from time import perf_counter

from audit_source_ranker import RELATIONS, REPOSITORY, REVISION, verify_bundle

SCHEMA = 'source_ranker_listwise_public_v1'
PROCEDURE = 'one_page_top_margin_calibrated_on_no_useful_v1'
SPLIT_FORMS = {
    'calibration': ('calibration-workshop-prose', 'calibration-direct-questions'),
    'heldout': ('heldout-field-records', 'heldout-indirect-tasks'),
}
DIRECT_QUESTION_PREFIXES = ('what ', 'how ', 'why ', 'when ', 'where ', 'which ')
MAX_RAM = 2 * 1024**3
MAX_TOKENS = 512
MAX_STARTUP_SECONDS = 20.0
MAX_TOTAL_SECONDS = 600.0
MAX_POOL_SECONDS = 5.0
MAX_WINDOW_CHARS = 480


def digest(path: Path) -> str:
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def _text(value: object, maximum: int) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= maximum


def validate_fixture(path: Path, expected_sha: str) -> list[dict]:
    if not isinstance(expected_sha, str) or len(expected_sha) != 64 or digest(path) != expected_sha:
        raise ValueError('fixture_identity')
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 250_000:
        raise ValueError('fixture_budget')
    packet = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(packet, dict) or packet.get('schema') != SCHEMA:
        raise ValueError('fixture_schema')
    groups = packet.get('groups')
    if not isinstance(groups, list) or len(groups) != 48:
        raise ValueError('fixture_counts')
    group_ids, candidate_ids, document_ids = set(), set(), set()
    source_families, template_families = defaultdict(set), defaultdict(set)
    structure = Counter()
    positions = Counter()
    for group in groups:
        if not isinstance(group, dict):
            raise ValueError('fixture_group')
        split, relation = group.get('split'), group.get('relation')
        group_id, question = group.get('group_id'), group.get('question')
        previous = group.get('previous_question')
        if (split not in ('calibration', 'heldout') or relation not in RELATIONS
            or not _text(group_id, 90) or group_id in group_ids
            or not _text(question, 4000)
            or previous is not None and not _text(previous, 4000)
            or type(group.get('useful_available')) is not bool
            or not _text(group.get('source_family'), 100)
            or not _text(group.get('template_family'), 100)):
            raise ValueError('fixture_group')
        is_direct_question = group['question'].lower().startswith(DIRECT_QUESTION_PREFIXES)
        if ((group['source_family'], group['template_family']) != SPLIT_FORMS[split]
            or is_direct_question != (split == 'calibration')):
            raise ValueError('fixture_split_template')
        group_ids.add(group_id)
        source_families[split].add(group['source_family'])
        template_families[split].add(group['template_family'])
        candidates = group.get('candidates')
        if not isinstance(candidates, list) or len(candidates) != 4:
            raise ValueError('fixture_cardinality')
        useful = 0
        windows = set()
        heldout_heading = None
        for position, candidate in enumerate(candidates, 1):
            if not isinstance(candidate, dict):
                raise ValueError('fixture_candidate')
            candidate_id, document_id = candidate.get('candidate_id'), candidate.get('document_id')
            page = candidate.get('page_text')
            start, end = candidate.get('start_offset'), candidate.get('end_offset')
            if (not _text(candidate_id, 120) or candidate_id in candidate_ids
                or not _text(document_id, 150) or document_id in document_ids
                or type(candidate.get('page_number')) is not int or candidate['page_number'] < 1
                or type(candidate.get('useful')) is not bool
                or not _text(page, 20_000)
                or type(start) is not int or type(end) is not int
                or not 0 <= start < end <= len(page)
                or end-start > MAX_WINDOW_CHARS
                or not page[start:end].strip()
                or not _text(candidate.get('rationale'), 300)):
                raise ValueError('fixture_candidate')
            candidate_ids.add(candidate_id)
            document_ids.add(document_id)
            window = page[start:end]
            if ('\n' in window) != (split == 'heldout'):
                raise ValueError('fixture_source_template')
            if split == 'heldout':
                heading, entry = window.split('\n', 1)
                if (not heading.strip() or not entry.startswith('Entry: ')
                    or not entry[len('Entry: '):].strip()
                    or heldout_heading is not None and heading != heldout_heading):
                    raise ValueError('fixture_source_template')
                heldout_heading = heading
            if window in windows:
                raise ValueError('fixture_duplicate_window')
            windows.add(window)
            useful += candidate['useful']
            if candidate['useful']:
                positions[(split, position)] += 1
        if useful != int(group['useful_available']):
            raise ValueError('fixture_labels')
        structure[(split, relation, group['useful_available'])] += 1
    if source_families['calibration'] & source_families['heldout'] or (template_families['calibration']
                                                                   & template_families['heldout']):
        raise ValueError('fixture_split_leak')
    expected = Counter({(split, relation, available): 2 if available else 1
                        for split in ('calibration', 'heldout') for relation in RELATIONS
                        for available in (True, False)})
    if structure != expected:
        raise ValueError('fixture_balance')
    if any(positions[(split, slot)] != 4 for split in ('calibration', 'heldout')
           for slot in range(1, 5)):
        raise ValueError('fixture_position_balance')
    return groups


def pair_for(group: dict, candidate: dict) -> tuple[str, str]:
    question = group['question']
    if group['previous_question'] is not None:
        question = 'Previous question: ' + group['previous_question'] + '\nCurrent question: ' + question
    return question, candidate['page_text'][candidate['start_offset']:candidate['end_offset']]


def _ordered(row: dict) -> list[dict]:
    for candidate in row['candidates']:
        if type(candidate['score']) not in (float, int) or not math.isfinite(candidate['score']):
            raise ValueError('score_invalid')
    return sorted(row['candidates'], key=lambda c: (-c['score'], c['candidate_id']))


def choose_rule(calibration_rows: list[dict]) -> dict:
    """Freeze one simple relative rule before any heldout score is consumed.

    A single useful page per positive group means a second/third output would
    be filler in this packet. The rule displays at most one. The only fitted
    parameter is the smallest top-two margin that excludes all eight public
    no-useful calibration groups. Failure to separate heldout groups is a real
    negative result; no threshold retune is permitted after that observation.
    """
    if len(calibration_rows) != 24:
        raise ValueError('calibration_counts')
    absent = [row for row in calibration_rows if not row['useful_available']]
    if len(absent) != 8 or sum(row['useful_available'] for row in calibration_rows) != 16:
        raise ValueError('calibration_counts')
    margins = []
    for row in absent:
        ordered = _ordered(row)
        margin = ordered[0]['score'] - ordered[1]['score']
        if not math.isfinite(margin):
            raise ValueError('score_invalid')
        margins.append(margin)
    threshold = math.nextafter(max(margins), math.inf)
    if not math.isfinite(threshold):
        raise ValueError('score_invalid')
    return {'procedure': PROCEDURE, 'top_two_margin_threshold': threshold,
            'max_displayed_pages': 1, 'calibration_groups': 24,
            'calibration_no_useful_groups': 8, 'heldout_scored': False}


def summarize(rows: list[dict], rule: dict) -> dict:
    if not isinstance(rows, list) or len(rows) != 24:
        raise ValueError('summary_counts')
    positive_count = sum(row['useful_available'] for row in rows)
    no_useful_count = len(rows)-positive_count
    if positive_count != 16 or no_useful_count != 8:
        raise ValueError('summary_counts')
    metric = Counter()
    for key in ('positive_groups', 'no_useful_groups', 'raw_rank_one_useful',
                'raw_pool_hit_at_three', 'displayed_cards', 'displayed_useful_cards',
                'displayed_useful_top_one', 'displayed_useful_hit_at_three',
                'weak_primary_positive', 'no_useful_false_primary'):
        metric[key] = 0
    per_relation = defaultdict(Counter)
    for row in rows:
        ordered = _ordered(row)
        top = ordered[0]
        margin = top['score']-ordered[1]['score']
        selected = margin >= rule['top_two_margin_threshold']
        relation = row['relation']
        if row['useful_available']:
            metric['positive_groups'] += 1
            per_relation[relation]['positive_groups'] += 1
            rank_one = bool(top['useful'])
            metric['raw_rank_one_useful'] += rank_one
            metric['raw_pool_hit_at_three'] += any(c['useful'] for c in ordered[:3])
            if selected:
                metric['displayed_cards'] += 1
                metric['displayed_useful_cards'] += rank_one
                metric['displayed_useful_top_one'] += rank_one
                metric['displayed_useful_hit_at_three'] += rank_one
                metric['weak_primary_positive'] += not rank_one
                per_relation[relation]['displayed_useful_top_one'] += rank_one
        else:
            metric['no_useful_groups'] += 1
            per_relation[relation]['no_useful_groups'] += 1
            if selected:
                metric['no_useful_false_primary'] += 1
                metric['displayed_cards'] += 1
                per_relation[relation]['no_useful_false_primary'] += 1
    metric['all_card_useful_precision'] = (metric['displayed_useful_cards'] / metric['displayed_cards']
                                           if metric['displayed_cards'] else 0.0)
    metric['relations'] = {relation: dict(per_relation[relation]) for relation in sorted(RELATIONS)}
    return dict(metric)


def public_passed(value: dict) -> bool:
    return (value.get('positive_groups') == 16 and value.get('no_useful_groups') == 8
            and value.get('displayed_useful_top_one', 0) >= 14
            and value.get('displayed_useful_hit_at_three', 0) >= 14
            and value.get('all_card_useful_precision', 0) >= 0.9
            and value.get('no_useful_false_primary', 0) == 0)


def peak_rss() -> int:
    for line in Path('/proc/self/status').read_text(encoding='utf-8').splitlines():
        if line.startswith('VmHWM:'):
            return int(line.split()[1])*1024
    raise ValueError('memory_measurement_unavailable')


def emit(value: dict) -> None:
    print(json.dumps(value, allow_nan=False), flush=True)


def child(args: argparse.Namespace) -> None:
    before = peak_rss()
    started = perf_counter()
    groups = validate_fixture(args.fixture, args.fixture_sha256)
    verify_bundle(args.bundle)
    from tokenizers import Tokenizer
    import numpy as np
    import onnxruntime as ort
    tokenizer = Tokenizer.from_file(str(args.bundle/'tokenizer.json'))
    tokenizer.no_truncation()
    tokenizer.no_padding()
    flat = [(group, candidate) for group in groups for candidate in group['candidates']]
    encodings = [tokenizer.encode(*pair_for(group, candidate), add_special_tokens=True)
                 for group, candidate in flat]
    if any(not 0 < len(encoding.ids) <= MAX_TOKENS for encoding in encodings):
        raise ValueError('complete_input_budget')
    configuration = json.loads((args.bundle/'config.json').read_text(encoding='utf-8'))
    pad = configuration.get('pad_token_id')
    if type(pad) is not int or pad < 0:
        raise ValueError('padding_configuration')
    options = ort.SessionOptions()
    options.intra_op_num_threads = 4
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.log_severity_level = 4
    model = ort.InferenceSession(str(args.bundle/'onnx/model_int8.onnx'),
                                sess_options=options, providers=['CPUExecutionProvider'])
    names = {entry.name for entry in model.get_inputs()}
    if not {'input_ids', 'attention_mask'} <= names <= {'input_ids', 'attention_mask', 'token_type_ids'}:
        raise ValueError('model_inputs')
    if perf_counter()-started > MAX_STARTUP_SECONDS or peak_rss()-before > MAX_RAM:
        raise ValueError('startup_resource_budget')
    emit({'event': 'startup_ready', 'startup_ms': round((perf_counter()-started)*1000, 3)})
    all_pool_times: list[float] = []

    def score(indices: list[int]) -> tuple[list[float], float]:
        if not 1 <= len(indices) <= 30:
            raise ValueError('pool_budget')
        width = max(len(encodings[index].ids) for index in indices)
        ids = np.full((len(indices), width), pad, dtype=np.int64)
        mask = np.zeros_like(ids)
        types = np.zeros_like(ids)
        for row_number, index in enumerate(indices):
            encoding = encodings[index]
            count = len(encoding.ids)
            ids[row_number, :count] = encoding.ids
            mask[row_number, :count] = encoding.attention_mask
            types[row_number, :count] = encoding.type_ids
        payload = {'input_ids': ids, 'attention_mask': mask, 'token_type_ids': types}
        tick = perf_counter()
        outputs = model.run(None, {name: payload[name] for name in names})
        elapsed = perf_counter()-tick
        if len(indices) == 30:
            all_pool_times.append(elapsed)
        if len(outputs) != 1 or outputs[0].shape not in ((len(indices),), (len(indices), 1)):
            raise ValueError('model_outputs')
        values = [float(value) for value in outputs[0].reshape(-1)]
        if any(not math.isfinite(value) for value in values):
            raise ValueError('score_invalid')
        if perf_counter()-started > MAX_TOTAL_SECONDS or peak_rss()-before > MAX_RAM:
            raise ValueError('scoring_resource_budget')
        return values, elapsed

    def split_rows(split: str) -> list[dict]:
        # The fixture is laid out group-wise, but scoring remains batched.
        indices = [index for index, (group, _) in enumerate(flat) if group['split'] == split]
        scores = {}
        for offset in range(0, len(indices), 30):
            subset = indices[offset:offset+30]
            values, _elapsed = score(subset)
            scores.update(zip(subset, values, strict=True))
        rows = []
        for group in groups:
            if group['split'] != split:
                continue
            own = []
            for index, (source_group, candidate) in enumerate(flat):
                if source_group is group:
                    own.append({'candidate_id': candidate['candidate_id'],
                                'useful': candidate['useful'], 'score': scores[index]})
            rows.append({'group_id': group['group_id'], 'relation': group['relation'],
                         'useful_available': group['useful_available'], 'candidates': own})
        return rows

    calibration = split_rows('calibration')
    rule = choose_rule(calibration)
    rule['fixture_sha256'] = args.fixture_sha256
    rule_path = args.output/'calibration-rule.json'
    with rule_path.open('x', encoding='utf-8') as handle:
        json.dump(rule, handle, allow_nan=False, indent=2)
    rule_sha = digest(rule_path)

    # Profile fixed 30-window pools using calibration only. Heldout has not yet
    # been scored, and the rule file is already frozen.
    calibration_indices = [index for index, (group, _) in enumerate(flat)
                           if group['split'] == 'calibration']
    for offset in range(10):
        probe = [calibration_indices[(index+offset) % len(calibration_indices)] for index in range(30)]
        _values, _elapsed = score(probe)

    heldout = split_rows('heldout')
    if digest(rule_path) != rule_sha or digest(args.fixture) != args.fixture_sha256:
        raise ValueError('measurement_drift')
    calibration_summary = summarize(calibration, rule)
    heldout_summary = summarize(heldout, rule)
    p95 = sorted(all_pool_times)[math.ceil(0.95*len(all_pool_times))-1]
    passed = public_passed(heldout_summary) and p95 <= MAX_POOL_SECONDS
    emit({'event': 'result', 'status': 'public_passed' if passed else 'public_quality_rejected',
          'candidate_passed': passed, 'release_gate_passed': False,
          'calibration': calibration_summary, 'heldout': heldout_summary,
          'rule_sha256': rule_sha, 'top_two_margin_threshold': rule['top_two_margin_threshold'],
          'max_input_tokens': max(len(encoding.ids) for encoding in encodings),
          'pool30_p95_ms': round(p95*1000, 3),
          'peak_rss_increase_mib': round(max(0, peak_rss()-before)/1024**2, 3),
          'scoring_ms': round((perf_counter()-started)*1000, 3)})


def supervise(args: argparse.Namespace) -> dict:
    args.output.mkdir(parents=True, exist_ok=True)
    frozen = {'procedure': PROCEDURE, 'fixture_sha256': args.fixture_sha256,
              'script_sha256': digest(Path(__file__)),
              'bundle_verifier_sha256': digest(Path(__file__).with_name('audit_source_ranker.py')),
              'manifest_sha256': digest(args.bundle/'manifest.json'),
              'repository': REPOSITORY, 'revision': REVISION,
              'candidate_passed': False, 'release_gate_passed': False,
              'provider_requests': 0, 'database_writes': 0}
    with (args.output/'audit-freeze.json').open('x', encoding='utf-8') as handle:
        json.dump(frozen, handle, indent=2)
    command = [sys.executable, str(Path(__file__)), '--child', '--bundle', str(args.bundle),
               '--fixture', str(args.fixture), '--fixture-sha256', args.fixture_sha256,
               '--output', str(args.output)]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               text=True, env={**os.environ, 'OMP_NUM_THREADS': '4',
                                               'TOKENIZERS_PARALLELISM': 'false'})
    mailbox: queue.Queue = queue.Queue()

    def read() -> None:
        assert process.stdout is not None
        for line in iter(lambda: process.stdout.readline(32_769), ''):
            mailbox.put(line)
        mailbox.put(None)

    threading.Thread(target=read, daemon=True).start()
    started = perf_counter()
    ready = False
    result = {**frozen, 'status': 'child_unavailable'}
    try:
        while True:
            elapsed = perf_counter()-started
            remaining = (MAX_TOTAL_SECONDS if ready else MAX_STARTUP_SECONDS)-elapsed
            if remaining <= 0:
                result['status'] = 'total_timeout' if ready else 'startup_timeout'
                break
            try:
                line = mailbox.get(timeout=remaining)
            except queue.Empty:
                result['status'] = 'total_timeout' if ready else 'startup_timeout'
                break
            if line is None or len(line) > 32_768:
                result['status'] = 'protocol_invalid' if line is not None else 'child_unavailable'
                break
            try:
                message = json.loads(line)
            except (TypeError, ValueError):
                result['status'] = 'protocol_invalid'
                break
            if not isinstance(message, dict):
                result['status'] = 'protocol_invalid'
                break
            if (message.get('event') == 'startup_ready' and not ready
                and type(message.get('startup_ms')) in (int, float)
                and math.isfinite(message['startup_ms'])):
                ready = True
                result['startup_ms'] = message['startup_ms']
            elif (message.get('event') == 'result' and ready
                  and message.get('status') in ('public_passed', 'public_quality_rejected')
                  and type(message.get('candidate_passed')) is bool
                  and isinstance(message.get('heldout'), dict)
                  and type(message.get('pool30_p95_ms')) in (int, float)
                  and math.isfinite(message['pool30_p95_ms'])
                  and message['candidate_passed'] == (public_passed(message['heldout'])
                                                       and message['pool30_p95_ms'] <= 5000)
                  and (message['status'] == 'public_passed') == message['candidate_passed']):
                result.update(message)
                break
            elif message.get('event') == 'failed':
                result['status'] = message.get('reason', 'child_unavailable')
                break
            else:
                result['status'] = 'protocol_invalid'
                break
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=2)
    result.pop('event', None)
    bundle_unchanged = True
    if result['status'] in ('public_passed', 'public_quality_rejected'):
        try:
            _size, current_manifest_sha = verify_bundle(args.bundle)
            bundle_unchanged = current_manifest_sha == frozen['manifest_sha256']
        except (OSError, ValueError):
            bundle_unchanged = False
    if (digest(Path(__file__)) != frozen['script_sha256']
        or digest(Path(__file__).with_name('audit_source_ranker.py')) != frozen['bundle_verifier_sha256']
        or digest(args.fixture) != args.fixture_sha256
        or not bundle_unchanged):
        result.update(status='measurement_drift', candidate_passed=False)
    with (args.output/'audit-result.json').open('x', encoding='utf-8') as handle:
        json.dump(result, handle, allow_nan=False, indent=2)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--fixture-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--execute-approved', action='store_true')
    parser.add_argument('--child', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.child:
        try:
            child(args)
        except Exception as error:
            safe = str(error) if isinstance(error, ValueError) else 'inference_unavailable'
            reasons = {'complete_input_budget', 'padding_configuration', 'model_inputs',
                       'model_outputs', 'startup_resource_budget', 'scoring_resource_budget',
                       'score_invalid', 'pool_latency_budget', 'measurement_drift',
                       'calibration_counts', 'summary_counts'}
            emit({'event': 'failed', 'reason': safe if safe in reasons else 'preflight_or_inference_unavailable'})
        return
    groups = validate_fixture(args.fixture, args.fixture_sha256)
    size, manifest_sha = verify_bundle(args.bundle)
    if not args.execute_approved:
        emit({'status': 'preflight_passed', 'group_count': len(groups),
              'window_count': sum(len(group['candidates']) for group in groups),
              'bundle_bytes': size, 'manifest_sha256': manifest_sha,
              'provider_requests': 0, 'database_writes': 0,
              'model_inferences': 0, 'candidate_passed': False,
              'release_gate_passed': False})
        return
    emit(supervise(args))


if __name__ == '__main__':
    main()
