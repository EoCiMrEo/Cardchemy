"""Keyless safety contracts for the isolated larger-verifier evaluator."""

import importlib.util
import json
from pathlib import Path
import sys

import pytest

from app.ai.local_support import LocalSupportUnavailable, NliScores


def _module():
    scripts = Path(__file__).resolve().parents[2] / 'scripts'
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location('larger_support_experiment', scripts / 'evaluate_larger_local_support.py')
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_public_nli_output_order_maps_to_runtime_score_contract():
    module = _module()
    class RawExport:
        def score(self, premise, hypothesis):
            assert (premise, hypothesis) == ('source', 'claim')
            # Candidate's export order: entailment, neutral, contradiction.
            return NliScores(.91, .06, .03)
    reordered = module.ReorderedNli(RawExport()).score('source', 'claim')
    assert reordered == NliScores(.03, .91, .06)


def test_missing_artifacts_do_not_start_inference(tmp_path):
    module = _module()
    with pytest.raises(ValueError, match='experiment_artifacts_unavailable'):
        module.verified_manifest(tmp_path / 'absent')


@pytest.mark.parametrize('bad_name,bad_role', [('../secret', 'nli'), ('model.onnx', 'other')])
def test_manifest_refuses_paths_or_roles_outside_public_pins(tmp_path, bad_name, bad_role):
    module = _module()
    rows = [{'role': bad_role, 'file': bad_name}] * 8
    (tmp_path / 'manifest.json').write_text(json.dumps(rows), encoding='utf-8')
    with pytest.raises(ValueError, match='experiment_manifest_invalid'):
        module.verified_manifest(tmp_path)


def test_experimental_budget_does_not_replace_release_budget():
    module = _module()
    from inspect import signature
    from app.config import ASK_REQUIRED_RELEASE_POLICY_VERSION
    from app.workers.rag_answer import RagAnswerWorker
    assert module.MAX_BUNDLE_BYTES == 1024**3
    assert module.MAX_RSS_BYTES == 2 * 1024**3
    assert ASK_REQUIRED_RELEASE_POLICY_VERSION == 'related_knowledge_navigation_v8'
    assert 'local_support_verifier' not in signature(RagAnswerWorker).parameters


def test_unavailable_verifier_is_safe_and_not_a_successful_negative():
    module = _module()
    from evaluate_local_support import _chunk
    chunk = _chunk({'source_quote': 'Paris is the capital of France.'})

    class Unavailable:
        def evaluate(self, **kwargs):
            raise LocalSupportUnavailable('private error must not escape')

    timings = []
    outcome = module.verdict(
        Unavailable(), 'What is the capital of France?', 'Paris.',
        chunk.content, chunk, timings,
    )
    assert outcome == (False, 'verifier_unavailable')
    assert len(timings) == 1 and timings[0] >= 0
    assert not module.case_passes([outcome], False)
    assert not module.case_passes([], False)
    assert module.case_passes([(False, 'entailment_rejected')], False)
    assert not module.case_passes([
        (False, 'entailment_rejected'), (True, 'supported'),
    ], False)
