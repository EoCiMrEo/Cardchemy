"""Current private metric boundaries; all packets are synthetic/keyless."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
import score_private_source_display_v6 as scorer


def digest(value):
    return sha256(str(value).encode()).hexdigest()


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def packets():
    cases = []
    for index in range(1, 13):
        cases.append({'case_id': f'T{index:02}', 'form': scorer.FORMS[(index - 1) // 4],
            'gold_page_key': digest(f'gold-{index}'), 'require_empty': False,
            'request_sha256': digest(f'request-{index}'), 'candidates': [
                {'id': f'S{ordinal:02}', 'page_key': digest(f'page-{index}-{ordinal}'),
                 'cue_sha256': digest(f'cue-{index}-{ordinal}'), 'pdf_sha256': digest('pdf')}
                for ordinal in range(1, 5)]})
    roster = {'schema': scorer.SCHEMA + '_roster', 'policy': scorer.POLICY, 'contract': scorer.CONTRACT,
              'component': 'private_holdout', 'runtime_sha256': digest('runtime'),
              'stage1_sha256': digest('stage1'), 'frozen_at_utc': '2026-10-02T00:00:00Z', 'cases': cases}
    labels = {'schema': scorer.SCHEMA + '_labels', 'roster_sha256': '',
              'frozen_at_utc': '2026-10-02T00:01:00Z', 'independent_of_runtime_selection': True,
              'original_pdf_inspected': True, 'runtime_evaluated': False, 'cases': [
                  {'case_id': row['case_id'], 'candidates': [dict(item, page_useful='Yes', cue_useful='Yes')
                      for item in row['candidates']]} for row in cases]}
    measurements = {'schema': scorer.SCHEMA + '_measurement', 'policy': scorer.POLICY, 'contract': scorer.CONTRACT,
                    'runtime_sha256': roster['runtime_sha256'], 'roster_sha256': '', 'labels_sha256': '',
                    'executed_at_utc': '2026-10-02T00:02:00Z', 'cases': [
                        {'case_id': row['case_id'], 'state': 'related_knowledge', 'embedding_calls': 1,
                         'source_judgment_calls': 1, 'answer_calls': 0, 'verifier_calls': 0,
                         'automatic_retries': 0, 'answer_assertion_present': False, 'displayed': [
                             dict(row['candidates'][0], **{key: True for key in scorer.INTEGRITY})]}
                        for row in cases]}
    return roster, labels, measurements


def seal(roster_sha, labels_sha, freeze_time):
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    receipt = {'schema': scorer.SCHEMA + '_review_receipt', 'roster_sha256': roster_sha,
               'labels_sha256': labels_sha, 'reviewer_id': 'synthetic_independent_review',
               'frozen_at_utc': freeze_time}
    signature = private.sign(encode(receipt))
    receipt.update(reviewer_public_key_hex=public.hex(), reviewer_signature_hex=signature.hex())
    return receipt, sha256(public).hexdigest()


def bound_score(roster, labels, measured, seal_mutation=None):
    roster_raw = encode(roster)
    roster_sha = sha256(roster_raw).hexdigest()
    labels['roster_sha256'] = roster_sha
    labels_raw = encode(labels)
    labels_sha = sha256(labels_raw).hexdigest()
    measured.update(roster_sha256=roster_sha, labels_sha256=labels_sha)
    measured_raw = encode(measured)
    receipt, trusted_key_sha = seal(roster_sha, labels_sha, labels['frozen_at_utc'])
    if seal_mutation == 'signature': receipt['reviewer_signature_hex'] = '00' * 64
    elif seal_mutation == 'identity': receipt['reviewer_id'] = 'replacement_reviewer'
    elif seal_mutation == 'key': trusted_key_sha = digest('untrusted key')
    elif seal_mutation == 'labels': receipt['labels_sha256'] = digest('other labels')
    elif seal_mutation == 'time': receipt['frozen_at_utc'] = '2026-10-02T00:01:30Z'
    receipt_raw = encode(receipt)
    return scorer.score(roster_raw, labels_raw, measured_raw, roster_sha256=roster_sha,
                        labels_sha256=labels_sha, measurement_sha256=sha256(measured_raw).hexdigest(),
                        review_receipt_bytes=receipt_raw, review_receipt_sha256=sha256(receipt_raw).hexdigest(),
                        trusted_review_key_sha256=trusted_key_sha)


def test_complete_component_pass_never_opens_release():
    result = bound_score(*packets())
    assert result['component_passed'] and not result['release_gate_passed']
    assert result['useful_hit_at_3'] == 12 and result['hits_by_form'] == dict.fromkeys(scorer.FORMS, 4)
    assert result['physical_calls'] == dict(embedding_calls=12, source_judgment_calls=12,
        answer_calls=0, verifier_calls=0, automatic_retries=0)


@pytest.mark.parametrize('bad_cards,expected', [(3, True), (4, False)])
def test_every_displayed_card_counts_at_eighty_percent(bad_cards, expected):
    roster, labels, measured = packets()
    # Fifteen displayed cards, twelve useful: exactly 80% is accepted.
    for index in range(bad_cards):
        labels['cases'][index]['candidates'][1]['cue_useful'] = 'No'
        measured['cases'][index]['displayed'].append(dict(roster['cases'][index]['candidates'][1],
            **{key: True for key in scorer.INTEGRITY}))
    result = bound_score(roster, labels, measured)
    assert result['component_passed'] is expected
    assert result['displayed_cards'] == 12 + bad_cards and result['useful_cards'] == 12


def test_unknown_is_nonuseful_and_never_dropped():
    roster, labels, measured = packets()
    labels['cases'][0]['candidates'][0]['page_useful'] = 'Unsure'
    result = bound_score(roster, labels, measured)
    assert result['useful_cards'] == 11 and result['displayed_cards'] == 12 and result['unknown_cards'] == 1
    assert result['useful_hit_at_3'] == 11


def test_missing_case_cannot_pass_on_a_smaller_denominator():
    roster, labels, measured = packets()
    measured['cases'].pop()
    result = bound_score(roster, labels, measured)
    assert not result['component_passed'] and result['missing_cases'] == 1 and result['case_denominator'] == 12


def test_per_form_hit_gate_preserves_three_of_four():
    roster, labels, measured = packets()
    for index in (0, 1):
        measured['cases'][index].update(state='no_match', displayed=[])
    result = bound_score(roster, labels, measured)
    assert result['useful_hit_at_3'] == 10 and result['displayed_usefulness'] == 1
    assert not result['component_passed'] and not result['gates']['per_form_hits']


@pytest.mark.parametrize('key', scorer.INTEGRITY)
def test_single_integrity_failure_blocks_even_high_usefulness(key):
    roster, labels, measured = packets()
    measured['cases'][0]['displayed'][0][key] = False
    result = bound_score(roster, labels, measured)
    assert result['displayed_usefulness'] > .8 and result['integrity_failures'] == 1
    assert not result['component_passed']


@pytest.mark.parametrize('field,value', [
    ('embedding_calls', 2), ('source_judgment_calls', 2), ('source_judgment_calls', 0),
    ('answer_calls', 1), ('verifier_calls', 1), ('automatic_retries', 1), ('answer_assertion_present', True)])
def test_one_violating_attempt_blocks_component(field, value):
    roster, labels, measured = packets()
    measured['cases'][0][field] = value
    result = bound_score(roster, labels, measured)
    assert not result['component_passed'] and result['policy_violations'] == 1


def test_provider_failure_is_miss_not_no_match():
    roster, labels, measured = packets()
    measured['cases'][0].update(state='provider_unavailable', displayed=[])
    result = bound_score(roster, labels, measured)
    assert result['case_denominator'] == 12 and result['provider_unavailable'] == 1
    assert result['useful_hit_at_3'] == 11 and not result['component_passed']


@pytest.mark.parametrize('change', ['unknown_id', 'wrong_cue', 'duplicate', 'boolean_counter', 'wrong_runtime'])
def test_malformed_or_spliced_observation_rejected(change):
    roster, labels, measured = packets()
    item = measured['cases'][0]['displayed'][0]
    if change == 'unknown_id': item['id'] = 'S99'
    elif change == 'wrong_cue': item['cue_sha256'] = digest('spliced')
    elif change == 'duplicate': measured['cases'][0]['displayed'].append(deepcopy(item))
    elif change == 'boolean_counter': measured['cases'][0]['embedding_calls'] = True
    else: measured['runtime_sha256'] = digest('different_runtime')
    with pytest.raises(scorer.ScoreError):
        bound_score(roster, labels, measured)


@pytest.mark.parametrize('field,value', [
    ('runtime_evaluated', True), ('independent_of_runtime_selection', False),
    ('original_pdf_inspected', False), ('frozen_at_utc', '2026-10-02T00:03:00Z')])
def test_post_result_or_nonindependent_review_rejected(field, value):
    roster, labels, measured = packets()
    labels[field] = value
    with pytest.raises(scorer.ScoreError):
        bound_score(roster, labels, measured)


def test_v4_policy_does_not_execute_under_v6_measurement():
    roster, labels, measured = packets()
    roster['policy'] = 'related_knowledge_navigation_v4'
    with pytest.raises(scorer.ScoreError):
        bound_score(roster, labels, measured)


def test_no_provider_or_operator_configuration_import():
    source = Path(scorer.__file__).read_text()
    assert 'import app.' not in source and 'from app.' not in source
    assert 'httpx' not in source and 'Settings(' not in source and '.env' not in source


def seed_packets():
    roster, labels, measured = packets()
    ids = sorted(scorer.SEEDS) + ['N12', 'U01', 'N02']
    template = (deepcopy(roster['cases'][0]), deepcopy(labels['cases'][0]), deepcopy(measured['cases'][0]))
    roster['component'] = 'exposed_seed'
    roster['cases'], labels['cases'], measured['cases'] = [], [], []
    for index, cid in enumerate(ids):
        source, review, result = deepcopy(template)
        for row in (source, review, result): row['case_id'] = cid
        source['gold_page_key'] = digest(f'seed-gold-{index}')
        source['form'] = 'direct' if cid in scorer.SEEDS else 'control'
        if cid in ('U01', 'N02'):
            source.update(gold_page_key=None, require_empty=True)
            for candidate in review['candidates']:
                candidate.update(page_useful='No', cue_useful='No')
            result.update(state='no_match', displayed=[])
        roster['cases'].append(source)
        labels['cases'].append(review)
        measured['cases'].append(result)
    return roster, labels, measured


def test_seed_gate_and_n12_control():
    result = bound_score(*seed_packets())
    assert result['component_passed'] and result['gates']['n12_control']
    roster, labels, measured = seed_packets()
    next(row for row in measured['cases'] if row['case_id'] == 'N12').update(state='no_match', displayed=[])
    result = bound_score(roster, labels, measured)
    assert not result['component_passed'] and not result['gates']['n12_control']


@pytest.mark.parametrize('state', ['clarification_needed', 'provider_unavailable', 'related_knowledge'])
def test_u01_requires_conclusive_no_match_not_ambiguity_or_provider_error(state):
    roster, labels, measured = seed_packets()
    row = next(item for item in measured['cases'] if item['case_id'] == 'U01')
    row['state'] = state
    if state == 'related_knowledge':
        candidate = next(item for item in roster['cases'] if item['case_id'] == 'U01')['candidates'][0]
        row['displayed'] = [dict(candidate, **{key: True for key in scorer.INTEGRITY})]
    result = bound_score(roster, labels, measured)
    assert result['control_failures'] == 1 and not result['component_passed']


@pytest.mark.parametrize('change', ['duplicate_label', 'missing_label', 'wrong_pdf', 'unhashable_case', 'unhashable_id'])
def test_review_denominator_and_exact_identity(change):
    roster, labels, measured = packets()
    if change == 'duplicate_label': labels['cases'][0]['candidates'][1] = deepcopy(labels['cases'][0]['candidates'][0])
    elif change == 'missing_label': labels['cases'][0]['candidates'].pop()
    elif change == 'wrong_pdf': labels['cases'][0]['candidates'][0]['pdf_sha256'] = digest('wrong PDF')
    elif change == 'unhashable_case': measured['cases'][0]['case_id'] = {}
    else: measured['cases'][0]['displayed'][0]['id'] = []
    with pytest.raises(scorer.ScoreError):
        bound_score(roster, labels, measured)


def test_external_bytes_binding_is_required():
    roster, labels, measured = packets()
    raw = encode(roster)
    with pytest.raises(scorer.ScoreError, match='input_sha_invalid'):
        scorer.score(raw, encode(labels), encode(measured), roster_sha256=digest('wrong bytes'),
                     labels_sha256=sha256(encode(labels)).hexdigest(), measurement_sha256=sha256(encode(measured)).hexdigest(),
                     review_receipt_bytes=b'{}', review_receipt_sha256=digest('invalid receipt'),
                     trusted_review_key_sha256=digest('invalid key'))


def test_duplicate_json_never_silently_changes_labels():
    raw = b'{"schema":"first","schema":"second"}'
    with pytest.raises(scorer.ScoreError, match='json_invalid'):
        scorer._bound(raw, sha256(raw).hexdigest())


@pytest.mark.parametrize('change', ['signature', 'identity', 'key', 'labels', 'time'])
def test_signed_review_cannot_be_replaced_or_rebound(change):
    with pytest.raises(scorer.ScoreError):
        bound_score(*packets(), seal_mutation=change)
