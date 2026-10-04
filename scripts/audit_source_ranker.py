"""Approved, supervised offline question/window ranking feasibility audit.

No application imports, settings, providers, database or network code. This
experiment never returns answers or changes an Ask policy. Default is preflight.
"""
from __future__ import annotations

import argparse
from collections import Counter
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

REPOSITORY = 'Alibaba-NLP/gte-reranker-modernbert-base'
REVISION = 'f7481e6055501a30fb19d090657df9ec1f79ab2c'
MODEL_SHA256 = 'ecc6a0ae67cee3d898167802383112d9185ca9250e07bd5d1fa65019b050179d'
FILES = frozenset({'onnx/model_int8.onnx', 'config.json', 'tokenizer.json',
                   'tokenizer_config.json', 'special_tokens_map.json'})
RELATIONS = frozenset({'acronym_expansion', 'definition', 'mechanism',
                      'measurement', 'reason', 'process', 'property_limitation',
                      'application_example'})
RELATION_ALIASES = {'acronym-expansion': 'acronym_expansion'}
MAX_BYTES = 300 * 1024**2
MAX_RAM = 2 * 1024**3
MAX_TOKENS = 512
MAX_STARTUP = 20.0
MAX_SECONDS = 600.0
MAX_POOL_SECONDS = 5.0
PROCEDURE = 'source_ranker_calibration_only_threshold_v1'


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def read_json(path, maximum):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > maximum:
        raise ValueError('artifact_invalid')
    return json.loads(path.read_text(encoding='utf-8'))


def relation_of(case):
    value = case['relation']
    return RELATION_ALIASES.get(value, value)


def validate_fixture(path, expected_sha):
    if len(expected_sha) != 64 or digest(path) != expected_sha:
        raise ValueError('fixture_identity')
    value = read_json(path, 500_000)
    if value.get('schema') != 'source_ranker_public_audit_v1':
        raise ValueError('fixture_schema')
    cases = value.get('cases')
    if not isinstance(cases, list) or len(cases) != 96:
        raise ValueError('fixture_counts')
    ids = set()
    for case in cases:
        if (not isinstance(case, dict) or not isinstance(case.get('case_id'), str)
            or not 1 <= len(case['case_id']) <= 80 or case['case_id'] in ids
            or relation_of(case) not in RELATIONS
            or case.get('split') not in ('calibration', 'heldout')
            or case.get('label') not in ('sufficient', 'insufficient')):
            raise ValueError('fixture_case')
        ids.add(case['case_id'])
        question, previous, page = case.get('question'), case.get('previous_question'), case.get('page_text')
        start, end = case.get('start_offset'), case.get('end_offset')
        if (not isinstance(question, str) or not question.strip() or len(question) > 4000
            or previous is not None and (not isinstance(previous, str) or not previous.strip() or len(previous) > 4000)
            or not isinstance(page, str) or len(page) > 20_000
            or type(start) is not int or type(end) is not int
            or not 0 <= start < end <= len(page) or end - start > 480
            or not page[start:end].strip() or not isinstance(case.get('rationale'), str)):
            raise ValueError('fixture_source_binding')
    for split, per_label in (('calibration', 2), ('heldout', 4)):
        counts = Counter((relation_of(case), case['label']) for case in cases if case['split'] == split)
        if counts != Counter({(relation, label): per_label for relation in RELATIONS
                              for label in ('sufficient', 'insufficient')}):
            raise ValueError('fixture_split_balance')
    return cases


def verify_bundle(root):
    if root.is_symlink() or not root.is_dir():
        raise ValueError('bundle_identity')
    manifest = read_json(root / 'manifest.json', 32_768)
    files = manifest.get('files')
    if (manifest.get('repository') != REPOSITORY or manifest.get('revision') != REVISION
        or not isinstance(files, dict) or set(files) != FILES):
        raise ValueError('bundle_manifest')
    total = 0
    for name, pin in files.items():
        path = root / name
        if (any(parent.is_symlink() for parent in (path, *path.parents))
            or not isinstance(pin, dict) or type(pin.get('size')) is not int
            or not 0 < pin['size'] <= MAX_BYTES or not path.is_file()
            or path.stat().st_size != pin['size'] or digest(path) != pin.get('sha256')):
            raise ValueError('bundle_hash')
        total += pin['size']
    if total > MAX_BYTES or files['onnx/model_int8.onnx']['sha256'] != MODEL_SHA256:
        raise ValueError('bundle_budget')
    return total, digest(root / 'manifest.json')


def pair_for(case):
    previous = case['previous_question']
    question = case['question'] if previous is None else (
        'Previous question: ' + previous + '\nCurrent question: ' + case['question'])
    return question, case['page_text'][case['start_offset']:case['end_offset']]


def choose_threshold(rows):
    if len(rows) != 32 or Counter(row['label'] for row in rows) != {'sufficient': 16, 'insufficient': 16}:
        raise ValueError('calibration_counts')
    if any(type(row['score']) not in (int, float) or not math.isfinite(row['score']) for row in rows):
        raise ValueError('score_invalid')
    return math.nextafter(max(row['score'] for row in rows if row['label'] == 'insufficient'), math.inf)


def aggregate(rows, threshold):
    counts = {}
    for relation in sorted(RELATIONS):
        own = [row for row in rows if row['relation'] == relation]
        counts[relation] = {
            'positive_total': sum(row['label'] == 'sufficient' for row in own),
            'positive_hits': sum(row['label'] == 'sufficient' and row['score'] >= threshold for row in own),
            'negative_total': sum(row['label'] == 'insufficient' for row in own),
            'false_primary': sum(row['label'] == 'insufficient' and row['score'] >= threshold for row in own),
        }
    return {'case_count': len(rows), 'positive_hits': sum(c['positive_hits'] for c in counts.values()),
            'false_primary': sum(c['false_primary'] for c in counts.values()), 'relations': counts}


def public_passed(value):
    return (value['case_count'] == 64 and value['positive_hits'] >= 28 and value['false_primary'] == 0
            and all(c['positive_total'] == c['negative_total'] == 4 and c['positive_hits'] >= 3
                    and c['false_primary'] == 0 for c in value['relations'].values())
            and set(value['relations']) == RELATIONS)


def peak_rss():
    for line in Path('/proc/self/status').read_text(encoding='utf-8').splitlines():
        if line.startswith('VmHWM:'):
            return int(line.split()[1]) * 1024
    raise ValueError('memory_measurement_unavailable')


def emit(value):
    print(json.dumps(value, allow_nan=False), flush=True)


def child(args):
    before = peak_rss()
    started = perf_counter()
    cases = validate_fixture(args.fixture, args.fixture_sha256)
    verify_bundle(args.bundle)
    from tokenizers import Tokenizer
    import numpy as np
    import onnxruntime as ort
    tokenizer = Tokenizer.from_file(str(args.bundle / 'tokenizer.json'))
    tokenizer.no_truncation()
    tokenizer.no_padding()
    encodings = [tokenizer.encode(*pair_for(case), add_special_tokens=True) for case in cases]
    if any(not 0 < len(encoding.ids) <= MAX_TOKENS for encoding in encodings):
        raise ValueError('complete_input_budget')
    configuration = read_json(args.bundle / 'config.json', 32_768)
    pad = configuration.get('pad_token_id')
    if type(pad) is not int or pad < 0:
        raise ValueError('padding_configuration')
    options = ort.SessionOptions()
    options.intra_op_num_threads = 4
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.log_severity_level = 4
    model = ort.InferenceSession(str(args.bundle / 'onnx/model_int8.onnx'),
                                sess_options=options, providers=['CPUExecutionProvider'])
    names = {entry.name for entry in model.get_inputs()}
    if not {'input_ids', 'attention_mask'} <= names <= {'input_ids', 'attention_mask', 'token_type_ids'}:
        raise ValueError('model_inputs')
    if perf_counter() - started > MAX_STARTUP or peak_rss() - before > MAX_RAM:
        raise ValueError('startup_resource_budget')
    emit({'event': 'startup_ready', 'startup_ms': round((perf_counter() - started) * 1000, 3)})

    def run(indices):
        if not 1 <= len(indices) <= 30:
            raise ValueError('pool_budget')
        width = max(len(encodings[i].ids) for i in indices)
        ids = np.full((len(indices), width), pad, dtype=np.int64)
        mask = np.zeros_like(ids)
        types = np.zeros_like(ids)
        for row, index in enumerate(indices):
            encoding = encodings[index]
            count = len(encoding.ids)
            ids[row, :count] = encoding.ids
            mask[row, :count] = encoding.attention_mask
            types[row, :count] = encoding.type_ids
        payload = {'input_ids': ids, 'attention_mask': mask, 'token_type_ids': types}
        tick = perf_counter()
        outputs = model.run(None, {name: payload[name] for name in names})
        elapsed = perf_counter() - tick
        if len(outputs) != 1 or outputs[0].shape not in ((len(indices),), (len(indices), 1)):
            raise ValueError('model_outputs')
        scores = [float(value) for value in outputs[0].reshape(-1)]
        if any(not math.isfinite(value) for value in scores):
            raise ValueError('score_invalid')
        if peak_rss() - before > MAX_RAM or perf_counter() - started > MAX_SECONDS:
            raise ValueError('scoring_resource_budget')
        return scores, elapsed

    calibration_ids = [i for i, case in enumerate(cases) if case['split'] == 'calibration']
    calibration_rows = []
    for offset in range(0, len(calibration_ids), 30):
        indices = calibration_ids[offset:offset+30]
        scores, _elapsed = run(indices)
        calibration_rows.extend({'relation': relation_of(cases[i]), 'label': cases[i]['label'], 'score': score}
                                for i, score in zip(indices, scores, strict=True))
    threshold = choose_threshold(calibration_rows)
    rule = {'procedure': PROCEDURE, 'threshold': threshold, 'fixture_sha256': args.fixture_sha256,
            'calibration_count': 32, 'heldout_scored': False}
    rule_path = args.output / 'calibration-rule.json'
    with rule_path.open('x', encoding='utf-8') as handle:
        json.dump(rule, handle, allow_nan=False, indent=2)
    rule_sha = digest(rule_path)
    # Resource probes use calibration inputs only. Never inspect heldout scores
    # when choosing the threshold or the latency procedure.
    pool_times = []
    for offset in range(10):
        indices = [calibration_ids[(i + offset) % 32] for i in range(30)]
        _scores, elapsed = run(indices)
        pool_times.append(elapsed)
        if elapsed > MAX_POOL_SECONDS:
            raise ValueError('pool_latency_budget')
    heldout_rows = []
    heldout_ids = [i for i, case in enumerate(cases) if case['split'] == 'heldout']
    for offset in range(0, len(heldout_ids), 30):
        indices = heldout_ids[offset:offset+30]
        scores, _elapsed = run(indices)
        heldout_rows.extend({'relation': relation_of(cases[i]), 'label': cases[i]['label'], 'score': score}
                            for i, score in zip(indices, scores, strict=True))
    if digest(rule_path) != rule_sha or digest(args.fixture) != args.fixture_sha256:
        raise ValueError('measurement_drift')
    heldout = aggregate(heldout_rows, threshold)
    emit({'event': 'result', 'status': 'public_passed' if public_passed(heldout) else 'public_quality_rejected',
          'candidate_passed': public_passed(heldout), 'calibration': aggregate(calibration_rows, threshold),
          'heldout': heldout, 'rule_sha256': rule_sha, 'threshold': threshold,
          'max_input_tokens': max(len(e.ids) for e in encodings),
          'pool30_p95_ms': round(sorted(pool_times)[math.ceil(.95 * len(pool_times)) - 1] * 1000, 3),
          'peak_rss_increase_mib': round(max(0, peak_rss() - before) / 1024**2, 3),
          'scoring_ms': round((perf_counter() - started) * 1000, 3)})


def supervise(args):
    args.output.mkdir(parents=True, exist_ok=True)
    frozen = {'procedure': PROCEDURE, 'fixture_sha256': args.fixture_sha256,
              'script_sha256': digest(Path(__file__)), 'manifest_sha256': digest(args.bundle / 'manifest.json'),
              'repository': REPOSITORY, 'revision': REVISION, 'candidate_passed': False,
              'provider_requests': 0, 'database_writes': 0, 'release_gate_passed': False}
    with (args.output / 'audit-freeze.json').open('x', encoding='utf-8') as handle:
        json.dump(frozen, handle, indent=2)
    command = [sys.executable, str(Path(__file__)), '--child', '--bundle', str(args.bundle),
               '--fixture', str(args.fixture), '--fixture-sha256', args.fixture_sha256,
               '--output', str(args.output)]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               text=True, env={**os.environ, 'OMP_NUM_THREADS': '4', 'TOKENIZERS_PARALLELISM': 'false'})
    mailbox = queue.Queue()
    def read():
        assert process.stdout is not None
        for line in iter(lambda: process.stdout.readline(32_769), ''):
            mailbox.put(line)
        mailbox.put(None)
    thread = threading.Thread(target=read, daemon=True)
    thread.start()
    started = perf_counter()
    ready = False
    result = {**frozen, 'status': 'child_unavailable'}
    try:
        while True:
            remaining = (MAX_SECONDS if ready else MAX_STARTUP) - (perf_counter() - started)
            if remaining <= 0:
                result['status'] = 'total_timeout' if ready else 'startup_timeout'
                break
            try:
                line = mailbox.get(timeout=remaining)
            except queue.Empty:
                result['status'] = 'total_timeout' if ready else 'startup_timeout'
                break
            if line is None:
                break
            if len(line) > 32_768:
                result['status'] = 'protocol_invalid'
                break
            try:
                message = json.loads(line)
            except (TypeError, ValueError):
                result['status'] = 'protocol_invalid'
                break
            if not isinstance(message, dict):
                result['status'] = 'protocol_invalid'
                break
            if message.get('event') == 'startup_ready' and not ready:
                ready = True
                result['startup_ms'] = message['startup_ms']
            elif message.get('event') == 'result':
                result.update(message)
                break
            elif message.get('event') == 'failed':
                result['status'] = message['reason']
                break
            else:
                result['status'] = 'protocol_invalid'
                break
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=2)
    result.pop('event', None)
    if digest(Path(__file__)) != frozen['script_sha256'] or digest(args.fixture) != args.fixture_sha256:
        result.update(status='measurement_drift', candidate_passed=False)
    with (args.output / 'audit-result.json').open('x', encoding='utf-8') as handle:
        json.dump(result, handle, allow_nan=False, indent=2)
    return result


def main():
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
            reasons = {'complete_input_budget', 'padding_configuration', 'model_inputs', 'model_outputs',
                       'startup_resource_budget', 'scoring_resource_budget', 'score_invalid',
                       'pool_latency_budget', 'measurement_drift'}
            emit({'event': 'failed', 'reason': safe if safe in reasons else 'preflight_or_inference_unavailable'})
        return
    cases = validate_fixture(args.fixture, args.fixture_sha256)
    size, manifest_sha = verify_bundle(args.bundle)
    if not args.execute_approved:
        emit({'status': 'preflight_passed', 'case_count': len(cases), 'bundle_bytes': size,
              'manifest_sha256': manifest_sha, 'provider_requests': 0, 'database_writes': 0,
              'model_inferences': 0, 'candidate_passed': False, 'release_gate_passed': False})
        return
    emit(supervise(args))


if __name__ == '__main__':
    main()
