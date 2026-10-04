"""Safety boundaries for the approved offline audit, without loading a model."""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts/audit_source_ranker.py'
spec = importlib.util.spec_from_file_location('audit_source_ranker_test', SCRIPT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def fixture():
    cases = []
    for split, count in [('calibration', 2), ('heldout', 4)]:
        for relation in sorted(audit.RELATIONS):
            for label in ['sufficient', 'insufficient']:
                for index in range(count):
                    cases.append({'case_id': f'{split}-{relation}-{label}-{index}',
                                  'split': split, 'relation': relation, 'label': label,
                                  'question': 'What does A do?', 'previous_question': None,
                                  'page_text': 'A releases a latch.', 'start_offset': 0,
                                  'end_offset': 19, 'rationale': 'Public test only.'})
    return {'schema': 'source_ranker_public_audit_v1', 'cases': cases}


def write_fixture(tmp_path, value):
    path = tmp_path / 'fixture.json'
    path.write_text(json.dumps(value), encoding='utf-8')
    return path, audit.digest(path)


@pytest.mark.parametrize('mutation', [
    lambda cases: cases[0].update(end_offset=481),
    lambda cases: cases[0].update(start_offset=True),
    lambda cases: cases[0].update(question=''),
    lambda cases: cases[0].update(previous_question=''),
    lambda cases: cases[0].update(label='unknown'),
    lambda cases: cases[0].update(split='heldout'),
    lambda cases: cases[0].update(case_id=cases[1]['case_id']),
    lambda cases: cases[0].update(relation='unknown'),
])
def test_corrupt_or_unbalanced_fixture_rejected_before_scoring(tmp_path, mutation):
    value = fixture()
    mutation(value['cases'])
    path, digest = write_fixture(tmp_path, value)
    with pytest.raises(ValueError):
        audit.validate_fixture(path, digest)


def test_exact_window_and_local_user_history_keep_conditions(tmp_path):
    value = fixture()
    value['cases'][0].update(previous_question='Which latch remains closed without power?',
                             question='Why does it stay closed when the alarm is off?')
    path, digest = write_fixture(tmp_path, value)
    cases = audit.validate_fixture(path, digest)
    query, window = audit.pair_for(cases[0])
    assert 'without power?' in query and 'when the alarm is off?' in query
    assert window == cases[0]['page_text'][0:19]
    path.write_text(path.read_text() + ' ', encoding='utf-8')
    with pytest.raises(ValueError, match='fixture_identity'):
        audit.validate_fixture(path, digest)


def test_hyphenated_acronym_relation_in_frozen_packet_is_canonicalized_in_memory(tmp_path):
    value = fixture()
    for case in value['cases']:
        if case['relation'] == 'acronym_expansion':
            case['relation'] = 'acronym-expansion'
    path, digest = write_fixture(tmp_path, value)
    cases = audit.validate_fixture(path, digest)
    assert sum(audit.relation_of(case) == 'acronym_expansion' for case in cases) == 12
    assert path.read_bytes() == json.dumps(value).encode()


def test_threshold_strictly_excludes_every_calibration_negative():
    rows = [{'label': label, 'score': score} for label, score in
            [('sufficient', 4.0)] * 16 + [('insufficient', 3.0)] * 16]
    threshold = audit.choose_threshold(rows)
    assert threshold > 3 and threshold <= 4
    rows[0]['score'] = math.nan
    with pytest.raises(ValueError, match='score_invalid'):
        audit.choose_threshold(rows)


def test_overlapping_positive_scores_do_not_relax_threshold():
    rows = [{'label': label, 'score': score} for label, score in
            [('sufficient', -5.0)] * 16 + [('insufficient', 3.0)] * 16]
    assert audit.choose_threshold(rows) > 3


def test_public_gate_requires_zero_false_primary_and_each_relation():
    rows = [{'relation': relation, 'label': label, 'score': 2 if label == 'sufficient' else 0}
            for relation in audit.RELATIONS for label in ('sufficient', 'insufficient') for _ in range(4)]
    assert audit.public_passed(audit.aggregate(rows, 1))
    negative = next(row for row in rows if row['label'] == 'insufficient')
    negative['score'] = 2
    assert not audit.public_passed(audit.aggregate(rows, 1))
    negative['score'] = 0
    relation = rows[0]['relation']
    positives = [row for row in rows if row['relation'] == relation and row['label'] == 'sufficient']
    positives[0]['score'] = positives[1]['score'] = 0
    assert not audit.public_passed(audit.aggregate(rows, 1))


def test_bundle_hash_and_path_guards(tmp_path, monkeypatch):
    files = {}
    for name in audit.FILES:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'public offline test')
        files[name] = {'size': path.stat().st_size, 'sha256': audit.digest(path)}
    manifest = {'repository': audit.REPOSITORY, 'revision': audit.REVISION, 'files': files}
    (tmp_path / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    monkeypatch.setattr(audit, 'MODEL_SHA256', files['onnx/model_int8.onnx']['sha256'])
    assert audit.verify_bundle(tmp_path)[0] == 5 * len(b'public offline test')
    (tmp_path / 'tokenizer.json').write_bytes(b'changed')
    with pytest.raises(ValueError, match='bundle_hash'):
        audit.verify_bundle(tmp_path)


def test_startup_hang_is_killed_and_one_shot_freeze_preserved(tmp_path, monkeypatch):
    source, digest = write_fixture(tmp_path, fixture())
    bundle = tmp_path / 'bundle'
    bundle.mkdir()
    (bundle / 'manifest.json').write_text('{}')
    output = tmp_path / 'output'
    args = SimpleNamespace(fixture=source, fixture_sha256=digest, bundle=bundle, output=output)
    original = subprocess.Popen
    children = []
    def launch(*_args, **kwargs):
        child = original([sys.executable, '-c', 'import time; time.sleep(10)'], **kwargs)
        children.append(child)
        return child
    monkeypatch.setattr(audit.subprocess, 'Popen', launch)
    monkeypatch.setattr(audit, 'MAX_STARTUP', .1)
    result = audit.supervise(args)
    assert result['status'] == 'startup_timeout' and not result['candidate_passed']
    assert children[0].poll() is not None
    frozen = (output / 'audit-freeze.json').read_bytes()
    with pytest.raises(FileExistsError):
        audit.supervise(args)
    assert (output / 'audit-freeze.json').read_bytes() == frozen and len(children) == 1


def test_malformed_child_protocol_fails_closed_and_preserves_result(tmp_path, monkeypatch):
    source, digest = write_fixture(tmp_path, fixture())
    bundle = tmp_path / 'bundle'
    bundle.mkdir()
    (bundle / 'manifest.json').write_text('{}')
    output = tmp_path / 'output'
    args = SimpleNamespace(fixture=source, fixture_sha256=digest, bundle=bundle, output=output)
    original = subprocess.Popen
    def launch(*_args, **kwargs):
        return original([sys.executable, '-c', "print('not-json', flush=True)"], **kwargs)
    monkeypatch.setattr(audit.subprocess, 'Popen', launch)
    result = audit.supervise(args)
    assert result['status'] == 'protocol_invalid' and result['candidate_passed'] is False
    assert json.loads((output / 'audit-result.json').read_text())['status'] == 'protocol_invalid'


def test_audit_has_no_application_network_database_or_retired_answer_import():
    import ast
    module = ast.parse(SCRIPT.read_text(encoding='utf-8'))
    imports = []
    for node in ast.walk(module):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or '')
    assert not any(name.split('.')[0] in {'app', 'httpx', 'requests', 'urllib', 'sqlalchemy',
                                         'transformers', 'sentence_transformers'} for name in imports)
