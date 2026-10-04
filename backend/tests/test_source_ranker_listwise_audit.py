"""No-inference safety and contract tests for the public listwise audit."""
from __future__ import annotations

import ast
from collections import Counter
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT/'scripts/audit_source_ranker_listwise.py'
BUILDER = ROOT/'scripts/build_source_ranker_listwise_fixture.py'
FIXTURE = ROOT/'backend/tests/fixtures/rag_eval/source_ranker_listwise_public_v1.json'
sys.path.insert(0, str(ROOT/'scripts'))
spec = importlib.util.spec_from_file_location('listwise_audit_test', SCRIPT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
builder_spec = importlib.util.spec_from_file_location('listwise_builder_test', BUILDER)
builder = importlib.util.module_from_spec(builder_spec)
builder_spec.loader.exec_module(builder)


def packet():
    return json.loads(FIXTURE.read_text(encoding='utf-8'))


def write_fixture(tmp_path, value):
    path = tmp_path/'packet.json'
    path.write_text(json.dumps(value), encoding='utf-8')
    return path, audit.digest(path)


def synthetic_rows(groups, split):
    rows = []
    for group in groups:
        if group['split'] != split:
            continue
        candidates = []
        for slot, source in enumerate(group['candidates']):
            score = (2.0 if source['useful'] else -slot/10.0)
            candidates.append({'candidate_id': source['candidate_id'],
                               'useful': source['useful'], 'score': score})
        rows.append({'group_id': group['group_id'], 'relation': group['relation'],
                     'useful_available': group['useful_available'], 'candidates': candidates})
    return rows


def test_public_fixture_is_reproducible_and_source_template_separated():
    expected = json.dumps(builder.build(), indent=2, ensure_ascii=False)+'\n'
    assert FIXTURE.read_text(encoding='utf-8') == expected
    groups = audit.validate_fixture(FIXTURE, audit.digest(FIXTURE))
    assert len(groups) == 48
    assert sum(len(group['candidates']) for group in groups) == 192
    assert Counter((group['split'], group['useful_available']) for group in groups) == {
        ('calibration', True): 16, ('calibration', False): 8,
        ('heldout', True): 16, ('heldout', False): 8,
    }
    for split in ('calibration', 'heldout'):
        positions = Counter(next(index for index, candidate in enumerate(group['candidates'], 1)
                                 if candidate['useful'])
                            for group in groups if group['split'] == split
                            and group['useful_available'])
        assert positions == {1: 4, 2: 4, 3: 4, 4: 4}
    assert {g['source_family'] for g in groups if g['split'] == 'calibration'}.isdisjoint(
        {g['source_family'] for g in groups if g['split'] == 'heldout'})
    assert {g['template_family'] for g in groups if g['split'] == 'calibration'}.isdisjoint(
        {g['template_family'] for g in groups if g['split'] == 'heldout'})


@pytest.mark.parametrize('mutation', [
    lambda groups: groups.pop(),
    lambda groups: groups[0]['candidates'][0].update(start_offset=True),
    lambda groups: groups[0]['candidates'][0].update(end_offset=481),
    lambda groups: groups[0]['candidates'][0].update(useful=False),
    lambda groups: groups[0].update(source_family='heldout-invented-handbook'),
    lambda groups: groups[0].update(group_id=groups[1]['group_id']),
    lambda groups: groups[0].update(relation='unknown'),
    lambda groups: groups[0]['candidates'].pop(),
])
def test_corrupt_or_leaked_fixture_rejected_before_model(tmp_path, mutation):
    value = packet()
    mutation(value['groups'])
    path, sha = write_fixture(tmp_path, value)
    with pytest.raises(ValueError):
        audit.validate_fixture(path, sha)


def test_hash_identity_and_exact_displayed_window(tmp_path):
    groups = audit.validate_fixture(FIXTURE, audit.digest(FIXTURE))
    group, candidate = groups[0], groups[0]['candidates'][0]
    question, window = audit.pair_for(group, candidate)
    assert question == group['question']
    assert window == candidate['page_text'][candidate['start_offset']:candidate['end_offset']]
    path, sha = write_fixture(tmp_path, packet())
    path.write_text(path.read_text(encoding='utf-8')+' ', encoding='utf-8')
    with pytest.raises(ValueError, match='fixture_identity'):
        audit.validate_fixture(path, sha)


def test_calibration_only_margin_fixes_cardinality_and_heldout_pass():
    groups = packet()['groups']
    calibration = synthetic_rows(groups, 'calibration')
    heldout = synthetic_rows(groups, 'heldout')
    rule = audit.choose_rule(calibration)
    assert rule['max_displayed_pages'] == 1
    assert rule['heldout_scored'] is False
    assert rule['top_two_margin_threshold'] > 0
    result = audit.summarize(heldout, rule)
    assert result['displayed_useful_top_one'] == 16
    assert result['displayed_useful_hit_at_three'] == 16
    assert result['no_useful_false_primary'] == 0
    assert result['all_card_useful_precision'] == 1
    assert audit.public_passed(result)


def test_false_no_useful_primary_or_weak_rank_fails_public_gate():
    groups = packet()['groups']
    rule = audit.choose_rule(synthetic_rows(groups, 'calibration'))
    heldout = synthetic_rows(groups, 'heldout')
    absent = next(row for row in heldout if not row['useful_available'])
    absent['candidates'][0]['score'] = 4
    result = audit.summarize(heldout, rule)
    assert result['no_useful_false_primary'] == 1
    assert not audit.public_passed(result)
    heldout = synthetic_rows(groups, 'heldout')
    for row in [row for row in heldout if row['useful_available']][:3]:
        next(candidate for candidate in row['candidates'] if candidate['useful'])['score'] = -5
        next(candidate for candidate in row['candidates'] if not candidate['useful'])['score'] = 5
    result = audit.summarize(heldout, rule)
    assert result['displayed_useful_top_one'] <= 13
    assert not audit.public_passed(result)


def test_no_displayed_cards_is_a_failure_not_division_error():
    groups = packet()['groups']
    rule = {'top_two_margin_threshold': 10.0}
    result = audit.summarize(synthetic_rows(groups, 'heldout'), rule)
    assert result['displayed_cards'] == 0
    assert result['all_card_useful_precision'] == 0
    assert not audit.public_passed(result)


def test_one_shot_supervisor_freeze_and_startup_timeout(tmp_path, monkeypatch):
    output = tmp_path/'output'
    bundle = tmp_path/'bundle'
    bundle.mkdir()
    (bundle/'manifest.json').write_text('{}', encoding='utf-8')
    args = SimpleNamespace(fixture=FIXTURE, fixture_sha256=audit.digest(FIXTURE),
                           bundle=bundle, output=output)
    original = subprocess.Popen
    children = []

    def launch(*_args, **kwargs):
        child = original([sys.executable, '-c', 'import time; time.sleep(10)'], **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(audit.subprocess, 'Popen', launch)
    monkeypatch.setattr(audit, 'MAX_STARTUP_SECONDS', .1)
    result = audit.supervise(args)
    assert result['status'] == 'startup_timeout' and result['candidate_passed'] is False
    assert children[0].poll() is not None
    frozen = (output/'audit-freeze.json').read_bytes()
    with pytest.raises(FileExistsError):
        audit.supervise(args)
    assert (output/'audit-freeze.json').read_bytes() == frozen
    assert len(children) == 1


def test_malformed_child_protocol_fails_closed(tmp_path, monkeypatch):
    output = tmp_path/'output'
    bundle = tmp_path/'bundle'
    bundle.mkdir()
    (bundle/'manifest.json').write_text('{}', encoding='utf-8')
    args = SimpleNamespace(fixture=FIXTURE, fixture_sha256=audit.digest(FIXTURE),
                           bundle=bundle, output=output)
    original = subprocess.Popen

    def launch(*_args, **kwargs):
        return original([sys.executable, '-c', "print('not-json', flush=True)"], **kwargs)

    monkeypatch.setattr(audit.subprocess, 'Popen', launch)
    result = audit.supervise(args)
    assert result['status'] == 'protocol_invalid'
    assert result['candidate_passed'] is False
    assert json.loads((output/'audit-result.json').read_text(encoding='utf-8'))['status'] == 'protocol_invalid'


def test_no_network_app_database_or_answer_imports():
    for source in (SCRIPT, BUILDER):
        module = ast.parse(source.read_text(encoding='utf-8'))
        names = []
        for node in ast.walk(module):
            if isinstance(node, ast.Import):
                names.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                names.append(node.module or '')
        assert not any(name.split('.')[0] in {
            'app', 'httpx', 'requests', 'urllib', 'sqlalchemy', 'transformers',
            'sentence_transformers', 'socket',
        } for name in names)
