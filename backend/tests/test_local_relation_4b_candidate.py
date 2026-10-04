"""Keyless boundaries for one unselected CPU 4B candidate; no real sessions."""

from hashlib import sha256
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from app.ai.local_support import LocalSupportUnavailable
from local_relation_candidate import DecisionObservation
import local_relation_4b_candidate as candidate


def metadata_value(collection, name, kind, shape):
    value = collection.add(name=name)
    value.type.tensor_type.elem_type = 7 if kind == "tensor(int64)" else 1
    for size in shape:
        dim = value.type.tensor_type.shape.dim.add()
        if isinstance(size, int):
            dim.dim_value = size
        else:
            dim.dim_param = size
    return value


def public_test_model():
    model = candidate._protobuf_types()["Model"]()
    model.ir_version = 10
    model.opset_import.add(domain="", version=21)
    model.opset_import.add(domain="com.microsoft", version=1)
    graph = model.graph
    graph.name = "public-test-graph"
    metadata_value(graph.input, "input_ids", "tensor(int64)", ("batch_size", "sequence_length"))
    metadata_value(graph.input, "attention_mask", "tensor(int64)", ("batch_size", "total_sequence_length"))
    metadata_value(graph.output, "logits", "tensor(float)", ("batch_size", "sequence_length", 151936))
    for layer in range(36):
        for kind in ("key", "value"):
            metadata_value(graph.input, f"past_key_values.{layer}.{kind}", "tensor(float)",
                           ("batch_size", 8, "past_sequence_length", 128))
            metadata_value(graph.output, f"present.{layer}.{kind}", "tensor(float)",
                           ("batch_size", 8, "total_sequence_length", 128))
    graph.node.add(op_type="Constant")
    weight = graph.initializer.add(name="public-weight", data_type=2, data_location=1)
    weight.dims.append(4)
    weight.external_data.add(key="location", value="model.onnx.data")
    weight.external_data.add(key="offset", value="0")
    weight.external_data.add(key="length", value="4")
    return model


def test_frozen_cpu_manifest_is_complete_under_approved_artifact_ceiling():
    assert candidate.REVISION == "98ddba15d05dede4435afb63f13280abcdbc2a48"
    assert candidate.REPOSITORY_DIRECTORY == "onnxruntime/cpu_and_mobile/cpu-int4-kld-block-128"
    assert candidate.ORT_VERSION == "1.30.0"
    assert len(candidate.PINS) == 8
    assert sum(size for size, _digest in candidate.PINS.values()) == 2897393599
    assert candidate.MAX_BUNDLE_BYTES == 3 * 1024**3
    assert candidate.MAX_INPUT_TOKENS == 512
    assert candidate.MAX_CHECK_SECONDS == 10
    assert all(len(digest) == 64 and set(digest) <= set("0123456789abcdef")
               for _size, digest in candidate.PINS.values())


def test_public_graph_contract_binds_every_external_tensor_without_loading():
    model = public_test_model()
    assert candidate.inspect_graph_bytes(model.SerializeToString()) == 1
    assert len(model.graph.input) == 74
    assert len(model.graph.output) == 73


@pytest.mark.parametrize("path", ("../model.onnx.data", "/model.onnx.data", "https://example.test/data",
                                  "other.data", "sub/model.onnx.data", r"C:\data", r"..\model.onnx.data"))
def test_external_location_cannot_escape_adjacent_pinned_file(path):
    model = public_test_model()
    model.graph.initializer[0].external_data[0].value = path
    with pytest.raises(LocalSupportUnavailable, match="experiment_external_data_invalid"):
        candidate.inspect_graph_bytes(model.SerializeToString())


@pytest.mark.parametrize("field,value", (("offset", "-1"), ("offset", "+1"), ("offset", "NaN"),
                                         ("length", "0"), ("length", "Infinity"),
                                         ("length", "2885434881"), ("offset", "2885434880")))
def test_external_ranges_are_finite_positive_and_inside_pinned_length(field, value):
    model = public_test_model()
    for item in model.graph.initializer[0].external_data:
        if item.key == field:
            item.value = value
    with pytest.raises(LocalSupportUnavailable, match="experiment_external_data_invalid"):
        candidate.inspect_graph_bytes(model.SerializeToString())


@pytest.mark.parametrize("change", ("duplicate_key", "unknown_key", "inline_plus_external", "unset_external_marker"))
def test_external_descriptors_are_unambiguous(change):
    model = public_test_model()
    tensor = model.graph.initializer[0]
    if change == "duplicate_key":
        tensor.external_data.add(key="location", value="model.onnx.data")
    elif change == "unknown_key":
        tensor.external_data.add(key="basepath", value="/tmp")
    elif change == "inline_plus_external":
        tensor.raw_data = b"inline"
    else:
        tensor.data_location = 0
    with pytest.raises(LocalSupportUnavailable, match="experiment_external_data_invalid"):
        candidate.inspect_graph_bytes(model.SerializeToString())


def test_external_attribute_tensor_is_checked_before_any_session():
    model = public_test_model()
    tensor = model.graph.node[0].attribute.add(name="value", type=4).t
    tensor.CopyFrom(model.graph.initializer[0])
    tensor.external_data[0].value = "../hidden.data"
    with pytest.raises(LocalSupportUnavailable, match="experiment_external_data_invalid"):
        candidate.inspect_graph_bytes(model.SerializeToString())


@pytest.mark.parametrize("structure", ("subgraph", "functions", "training", "configuration", "sparse", "unknown"))
def test_unsupported_graph_bearing_or_unknown_structures_fail_closed(structure):
    model = public_test_model()
    if structure == "subgraph":
        model.graph.node[0].attribute.add(name="hidden", type=5, g=b"graph")
    elif structure == "functions":
        model.functions.append(b"function")
    elif structure == "training":
        model.training_info.append(b"training")
    elif structure == "configuration":
        model.configuration.append(b"configuration")
    elif structure == "sparse":
        model.graph.sparse_initializer.append(b"sparse")
    body = model.SerializeToString()
    if structure == "unknown":
        body += bytes((0x98, 0x06, 0x01))  # Unknown Model field 99.
    with pytest.raises(LocalSupportUnavailable):
        candidate.inspect_graph_bytes(body)


@pytest.mark.parametrize("change", ("position_ids", "float16_cache", "wrong_layer", "last_only_logits", "wrong_opset", "wrong_op"))
def test_actual_public_graph_cpu_contract_is_exact(change):
    model = public_test_model()
    if change == "position_ids":
        metadata_value(model.graph.input, "position_ids", "tensor(int64)", ("batch_size", "sequence_length"))
    elif change == "float16_cache":
        model.graph.input[2].type.tensor_type.elem_type = 10
    elif change == "wrong_layer":
        model.graph.input[2].name = "past_key_values.99.key"
    elif change == "last_only_logits":
        model.graph.output[0].type.tensor_type.shape.dim[1].ClearField("dim_param")
        model.graph.output[0].type.tensor_type.shape.dim[1].dim_value = 1
    elif change == "wrong_opset":
        model.opset_import[0].version = 20
    else:
        model.graph.node[0].op_type = "UnreviewedOperator"
    with pytest.raises(LocalSupportUnavailable):
        candidate.inspect_graph_bytes(model.SerializeToString())


@pytest.mark.parametrize("body", (b"", b"\x3a\xff", b"not-protobuf"))
def test_malformed_graph_metadata_is_a_safe_unavailable_result(body):
    with pytest.raises(LocalSupportUnavailable, match="experiment_graph_invalid"):
        candidate.inspect_graph_bytes(body)


def make_fake_bundle(tmp_path, monkeypatch):
    bodies = {
        "model.onnx": public_test_model().SerializeToString(),
        "model.onnx.data": b"public-data",
        "config.json": json.dumps(candidate._EXPECTED_MODEL).encode(),
        "genai_config.json": json.dumps({"model": {"vocab_size": 151936, "decoder": {
            "filename": "model.onnx", "num_hidden_layers": 36, "num_key_value_heads": 8,
            "head_size": 128, "session_options": {"provider_options": []}}}}).encode(),
        "tokenizer.json": b"public-tokenizer", "tokenizer_config.json": b"{}",
        "chat_template.jinja": b"public-template", "README.md": b"public-test-notice",
    }
    for name, body in bodies.items():
        (tmp_path / name).write_bytes(body)
    monkeypatch.setattr(candidate, "PINS", {
        name: (len(body), sha256(body).hexdigest()) for name, body in bodies.items()
    })
    return bodies


def test_artifact_hash_and_graph_guard_precede_session_loading(tmp_path, monkeypatch):
    bodies = make_fake_bundle(tmp_path, monkeypatch)
    assert candidate.verify_artifacts(tmp_path) == sum(map(len, bodies.values()))
    (tmp_path / "tokenizer.json").write_bytes(b"modified")
    with pytest.raises(LocalSupportUnavailable, match="experiment_artifact_invalid"):
        candidate.verify_artifacts(tmp_path)


def test_runtime_only_diagnostic_requires_only_readme_to_be_absent(tmp_path, monkeypatch):
    bodies = make_fake_bundle(tmp_path, monkeypatch)
    (tmp_path / "README.md").unlink()
    with pytest.raises(LocalSupportUnavailable, match="experiment_artifact_invalid"):
        candidate.verify_artifacts(tmp_path)
    assert candidate.verify_artifacts(tmp_path, runtime_only_diagnostic=True) == (
        sum(map(len, bodies.values())) - len(bodies["README.md"])
    )
    (tmp_path / "README.md").write_bytes(bodies["README.md"])
    with pytest.raises(LocalSupportUnavailable, match="experiment_diagnostic_requires_missing_readme"):
        candidate.verify_artifacts(tmp_path, runtime_only_diagnostic=True)


@pytest.mark.parametrize("change", ("missing_graph", "corrupt_tokenizer", "readme_symlink"))
def test_runtime_only_diagnostic_still_rejects_bad_pinned_artifacts(tmp_path, monkeypatch, change):
    make_fake_bundle(tmp_path, monkeypatch)
    (tmp_path / "README.md").unlink()
    if change == "missing_graph":
        (tmp_path / "model.onnx").unlink()
    elif change == "corrupt_tokenizer":
        (tmp_path / "tokenizer.json").write_bytes(b"x" * len(b"public-tokenizer"))
    else:
        link = tmp_path / "README.md"
        original = Path.is_symlink
        monkeypatch.setattr(Path, "is_symlink", lambda path: path == link or original(path))
    with pytest.raises(LocalSupportUnavailable):
        candidate.verify_artifacts(tmp_path, runtime_only_diagnostic=True)


def test_same_size_artifact_tampering_rejects_digest(tmp_path, monkeypatch):
    bodies = make_fake_bundle(tmp_path, monkeypatch)
    (tmp_path / "README.md").write_bytes(b"x" * len(bodies["README.md"]))
    with pytest.raises(LocalSupportUnavailable, match="experiment_artifact_digest"):
        candidate.verify_artifacts(tmp_path)


def test_unverified_bundle_never_constructs_an_ort_session(tmp_path, monkeypatch):
    import onnxruntime as ort
    monkeypatch.setattr(ort, "InferenceSession", lambda *args, **kwargs: pytest.fail("no session may load"))
    with pytest.raises(LocalSupportUnavailable, match="experiment_artifact_invalid"):
        candidate.Onnx4BDecisionScorer(tmp_path)


def test_unreviewed_runtime_version_never_constructs_a_session(monkeypatch):
    import onnxruntime as ort
    monkeypatch.setattr(candidate, "verify_artifacts", lambda root: 1)
    monkeypatch.setattr(ort, "__version__", "unreviewed")
    monkeypatch.setattr(ort, "InferenceSession", lambda *args, **kwargs: pytest.fail("no session may load"))
    with pytest.raises(LocalSupportUnavailable, match="experiment_runtime_contract"):
        candidate.Onnx4BDecisionScorer(Path("public-bundle"))


@pytest.mark.parametrize("target", ("root", "ancestor", "file"))
def test_symlink_guards_without_os_symlink_privilege(tmp_path, monkeypatch, target):
    root = tmp_path / "bundle"
    root.mkdir()
    make_fake_bundle(root, monkeypatch)
    link = root if target == "root" else tmp_path if target == "ancestor" else root / "README.md"
    original = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda path: path == link or original(path))
    with pytest.raises(LocalSupportUnavailable):
        candidate.verify_artifacts(root)


def test_root_or_artifact_symlinks_fail_closed(tmp_path, monkeypatch):
    root = tmp_path / "bundle"
    root.mkdir()
    make_fake_bundle(root, monkeypatch)
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(root, target_is_directory=True)
    except OSError:
        pytest.skip("This Windows runner cannot create a test symlink")
    with pytest.raises(LocalSupportUnavailable, match="experiment_artifacts_unavailable"):
        candidate.verify_artifacts(alias)
    file = root / "README.md"
    file.unlink()
    file.symlink_to(root / "tokenizer.json")
    with pytest.raises(LocalSupportUnavailable, match="experiment_artifact_invalid"):
        candidate.verify_artifacts(root)


def fake_session():
    def metadata(expected):
        return [SimpleNamespace(name=name, type=kind, shape=list(shape))
                for name, (kind, shape) in expected.items()]
    return SimpleNamespace(
        get_inputs=lambda: metadata(candidate._INPUTS),
        get_outputs=lambda: metadata(candidate._OUTPUTS),
        get_providers=lambda: ["CPUExecutionProvider"],
    )


def test_session_metadata_matches_all_input_and_output_types_shapes():
    candidate.validate_session_metadata(fake_session())


@pytest.mark.parametrize("change", ("cuda", "input_dtype", "output_shape", "duplicate_input"))
def test_unexpected_session_metadata_or_provider_is_rejected(change):
    session = fake_session()
    if change == "cuda":
        session.get_providers = lambda: ["CUDAExecutionProvider", "CPUExecutionProvider"]
    elif change == "input_dtype":
        values = session.get_inputs()
        values[0].type = "tensor(float)"
        session.get_inputs = lambda: values
    elif change == "output_shape":
        values = session.get_outputs()
        values[0].shape[1] = 1
        session.get_outputs = lambda: values
    else:
        values = session.get_inputs()
        values.append(values[0])
        session.get_inputs = lambda: values
    with pytest.raises(LocalSupportUnavailable):
        candidate.validate_session_metadata(session)


class FakeInferenceSession:
    def __init__(self, output):
        self.output = output
        self.feed = None

    def run(self, outputs, feed, run_options):
        self.feed = feed
        assert outputs == ["logits"]
        return [self.output]


class FakeTimer:
    def __init__(self, delay, callback):
        self.delay, self.callback = delay, callback
    def start(self):
        pass
    def cancel(self):
        pass


def fake_scorer(monkeypatch, *, winner=1, tokens=(4, 5), output=None):
    scorer = object.__new__(candidate.Onnx4BDecisionScorer)
    scorer.np = np
    scorer.ort = SimpleNamespace(RunOptions=lambda: SimpleNamespace(terminate=False))
    scorer.tokenizer = SimpleNamespace(encode=lambda *args, **kwargs: SimpleNamespace(ids=list(tokens)))
    scorer.label_ids = {1: "A", 2: "B", 3: "C"}
    if output is None:
        output = np.zeros((1, len(tokens), 151936), dtype=np.float32)
        output[0, -1, winner] = 20
    scorer.session = FakeInferenceSession(output)
    monkeypatch.setattr(candidate.threading, "Timer", FakeTimer)
    monkeypatch.setattr(candidate, "perf_counter", lambda: 100.0)
    return scorer


def test_observation_uses_global_vocabulary_and_exact_cpu_feeds(monkeypatch):
    scorer = fake_scorer(monkeypatch)
    observation = scorer.observe("public prompt", deadline=110.0)
    assert isinstance(observation, DecisionObservation)
    assert observation.label == "A" and observation.input_tokens == 2
    assert observation.confidence > .99
    feed = scorer.session.feed
    assert "position_ids" not in feed and len(feed) == 74
    assert feed["input_ids"].dtype == np.int64
    assert feed["attention_mask"].shape == (1, 2)
    assert all(array.shape == (1, 8, 0, 128) and array.dtype == np.float32
               for name, array in feed.items() if name.startswith("past_key_values."))


def test_nonlabel_global_winner_is_preserved_as_uncertainty(monkeypatch):
    scorer = fake_scorer(monkeypatch, winner=6)
    observation = scorer.observe("public prompt", deadline=110.0)
    assert observation.label is None and observation.label_mass < .01


@pytest.mark.parametrize("tokens", ((), tuple(range(513)), (-1,), (151936,), (True,)))
def test_empty_oversized_or_malformed_token_ids_never_start_inference(monkeypatch, tokens):
    scorer = fake_scorer(monkeypatch, tokens=tokens, output=np.zeros((1, 1, 151936), dtype=np.float32))
    with pytest.raises(LocalSupportUnavailable, match="experiment_input_budget"):
        scorer.observe("public prompt", deadline=110.0)
    assert scorer.session.feed is None


@pytest.mark.parametrize("change", ("shape", "dtype", "nan_last", "nan_unused"))
def test_invalid_full_sequence_output_cannot_be_observed(monkeypatch, change):
    output = np.zeros((1, 2, 151936), dtype=np.float32)
    if change == "shape":
        output = output[:, :1]
    elif change == "dtype":
        output = output.astype(np.float16)
    elif change == "nan_last":
        output[0, -1, 1] = np.nan
    else:
        output[0, 0, 1] = np.nan
    scorer = fake_scorer(monkeypatch, output=output)
    with pytest.raises(LocalSupportUnavailable, match="experiment_output_invalid"):
        scorer.observe("public prompt", deadline=110.0)


@pytest.mark.parametrize("deadline", (float("nan"), float("inf"), True))
def test_malformed_deadline_rejects_without_inference(monkeypatch, deadline):
    scorer = fake_scorer(monkeypatch)
    with pytest.raises(LocalSupportUnavailable, match="experiment_input_invalid"):
        scorer.observe("public prompt", deadline=deadline)
    assert scorer.session.feed is None


def test_expired_deadline_prevents_inference(monkeypatch):
    scorer = fake_scorer(monkeypatch)
    with pytest.raises(LocalSupportUnavailable, match="experiment_latency_budget"):
        scorer.observe("public prompt", deadline=100.0)
    assert scorer.session.feed is None


def test_post_inference_deadline_is_rechecked(monkeypatch):
    scorer = fake_scorer(monkeypatch)
    ticks = iter((100.0, 100.0, 110.1))
    monkeypatch.setattr(candidate, "perf_counter", lambda: next(ticks))
    with pytest.raises(LocalSupportUnavailable, match="experiment_latency_budget"):
        scorer.observe("public prompt", deadline=110.0)


def test_public_experiment_prompt_remains_outside_source_only_runtime():
    from inspect import signature
    from app.config import ASK_REQUIRED_RELEASE_POLICY_VERSION
    from app.workers.rag_answer import RagAnswerWorker
    from local_relation_candidate import render_prompt

    assert ASK_REQUIRED_RELEASE_POLICY_VERSION == "related_knowledge_navigation_v8"
    assert "local_support_verifier" not in signature(RagAnswerWorker).parameters
    assert render_prompt("joint", {"public": "data"}).endswith("<think>\n\n</think>\n\n")
