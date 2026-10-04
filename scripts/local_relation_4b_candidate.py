"""One pinned CPU Qwen3-4B experiment; no runtime factory selects this module.

Metadata was read from the digest-checked public graph, without weights or
inference: IR10 / ONNX21, float32 KV and full-sequence float32 logits. External
data is validated before ORT can open it. No downloads or dependency installation
occur in this module. The frozen small-candidate prompt and observation contract
are shared; this module never generates text or changes their decision rule.
"""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import re
import threading
from time import perf_counter

from app.ai.local_support import LocalSupportUnavailable
from local_relation_candidate import DecisionObservation, MAX_INPUT_TOKENS

REPOSITORY = "onnx-community/Qwen3-4B-ONNX"
REVISION = "98ddba15d05dede4435afb63f13280abcdbc2a48"
REPOSITORY_DIRECTORY = "onnxruntime/cpu_and_mobile/cpu-int4-kld-block-128"
ORT_VERSION = "1.30.0"
MAX_BUNDLE_BYTES = 3 * 1024**3
MAX_CHECK_SECONDS = 10.0
PINS = {
    "model.onnx": (519634, "b4547cf9327bd532cb81703cf013f958117ba5a3e5a81c7c79a33aba534ff337"),
    "model.onnx.data": (2885434880, "d6003acd70841b99a44ce4c21d13dc42244e3ec3b7c12d70919f9b55440bbc45"),
    "tokenizer.json": (11422648, "979d160e081df25a1bf7f4e2e8f4c441b5dfdc9a8e84aec9f32e80445e1b59b8"),
    "config.json": (9567, "0bfeedcfa808cb8404e75d32cef3cdb6c566631acdb7c0edbe9e6945763c6989"),
    "genai_config.json": (1520, "dcb9aa8dd93b1acc17a2df193811c200ab540932c20a98ce4d4d23ce88a69b7d"),
    "tokenizer_config.json": (663, "bfd13b57b2e0c2cb582f311c0895f077d16a868c0dc61e4dbbba544a835341d6"),
    "chat_template.jinja": (4168, "a55ee1b1660128b7098723e0abcd92caa0788061051c62d51cbe87d9cf1974d8"),
    "README.md": (519, "22e42c1d314131050e6f5faa57766cf40691afedffff867bb77fa13a366c74f4"),
}
_EXPECTED_MODEL = {
    "model_type": "qwen3", "num_hidden_layers": 36,
    "num_key_value_heads": 8, "head_dim": 128, "vocab_size": 151936,
    "num_attention_heads": 32, "hidden_size": 2560,
}
_INPUTS = {"input_ids": ("tensor(int64)", ("batch_size", "sequence_length")),
           "attention_mask": ("tensor(int64)", ("batch_size", "total_sequence_length"))}
_INPUTS.update({f"past_key_values.{layer}.{kind}":
               ("tensor(float)", ("batch_size", 8, "past_sequence_length", 128))
               for layer in range(36) for kind in ("key", "value")})
_OUTPUTS = {"logits": ("tensor(float)", ("batch_size", "sequence_length", 151936))}
_OUTPUTS.update({f"present.{layer}.{kind}":
                ("tensor(float)", ("batch_size", 8, "total_sequence_length", 128))
                for layer in range(36) for kind in ("key", "value")})
_OPERATORS = frozenset({
    ("", "Cast"), ("", "Constant"), ("", "Gather"), ("", "Mul"),
    ("", "ReduceSum"), ("", "Reshape"), ("", "Shape"), ("", "Sigmoid"),
    ("", "SimplifiedLayerNormalization"), ("", "Sub"),
    ("com.microsoft", "GatherBlockQuantized"), ("com.microsoft", "GroupQueryAttention"),
    ("com.microsoft", "MatMulNBits"), ("com.microsoft", "SkipSimplifiedLayerNormalization"),
})


def _unavailable(code):
    raise LocalSupportUnavailable(code)


@lru_cache(maxsize=1)
def _protobuf_types():
    """Narrow closed metadata descriptors from ONNX's public proto2 schema.

    https://github.com/onnx/onnx/blob/main/onnx/onnx.proto
    Unsupported graph-bearing structures are represented as opaque bytes and
    rejected, rather than ignored. Standard metadata/scalar fields are parsed.
    Existing google.protobuf is used; the onnx package is not required.
    """
    from google.protobuf import descriptor_pb2, descriptor_pool, message_factory
    descriptor = descriptor_pb2.FileDescriptorProto(
        name="cardchemy_qwen4b_metadata.proto", package="cardchemy_qwen4b", syntax="proto2",
    )
    def message(name, fields):
        definition = descriptor.message_type.add(name=name)
        for field_name, number, kind, repeated in fields:
            field = definition.field.add(name=field_name, number=number, label=3 if repeated else 1)
            if isinstance(kind, str):
                field.type, field.type_name = 11, ".cardchemy_qwen4b." + kind
            else:
                field.type = kind
    message("Entry", [("key", 1, 9, False), ("value", 2, 9, False)])
    message("Dim", [("dim_value", 1, 3, False), ("dim_param", 2, 9, False), ("denotation", 3, 9, False)])
    message("Shape", [("dim", 1, "Dim", True)])
    message("TensorType", [("elem_type", 1, 5, False), ("shape", 2, "Shape", False)])
    message("Type", [("tensor_type", 1, "TensorType", False), ("sequence_type", 4, 12, False),
                     ("map_type", 5, 12, False), ("denotation", 6, 9, False),
                     ("opaque_type", 7, 12, False), ("sparse_tensor_type", 8, 12, False),
                     ("optional_type", 9, 12, False)])
    message("Value", [("name", 1, 9, False), ("type", 2, "Type", False),
                      ("doc_string", 3, 9, False), ("metadata_props", 4, "Entry", True)])
    message("Tensor", [
        ("dims", 1, 3, True), ("data_type", 2, 5, False), ("segment", 3, 12, False),
        ("float_data", 4, 2, True), ("int32_data", 5, 5, True), ("string_data", 6, 12, True),
        ("int64_data", 7, 3, True), ("name", 8, 9, False), ("raw_data", 9, 12, False),
        ("double_data", 10, 1, True), ("uint64_data", 11, 4, True), ("doc_string", 12, 9, False),
        ("external_data", 13, "Entry", True), ("data_location", 14, 5, False),
        ("metadata_props", 16, "Entry", True),
    ])
    message("Attribute", [
        ("name", 1, 9, False), ("f", 2, 2, False), ("i", 3, 3, False), ("s", 4, 12, False),
        ("t", 5, "Tensor", False), ("g", 6, 12, False), ("floats", 7, 2, True),
        ("ints", 8, 3, True), ("strings", 9, 12, True), ("tensors", 10, "Tensor", True),
        ("graphs", 11, 12, True), ("doc_string", 13, 9, False), ("tp", 14, 12, False),
        ("type_protos", 15, 12, True), ("type", 20, 5, False), ("ref_attr_name", 21, 9, False),
        ("sparse_tensor", 22, 12, False), ("sparse_tensors", 23, 12, True),
    ])
    message("Node", [
        ("input", 1, 9, True), ("output", 2, 9, True), ("name", 3, 9, False),
        ("op_type", 4, 9, False), ("attribute", 5, "Attribute", True), ("doc_string", 6, 9, False),
        ("domain", 7, 9, False), ("overload", 8, 9, False), ("metadata_props", 9, "Entry", True),
        ("device_configurations", 10, 12, True),
    ])
    message("Graph", [
        ("node", 1, "Node", True), ("name", 2, 9, False), ("initializer", 5, "Tensor", True),
        ("doc_string", 10, 9, False), ("input", 11, "Value", True), ("output", 12, "Value", True),
        ("value_info", 13, "Value", True), ("quantization_annotation", 14, 12, True),
        ("sparse_initializer", 15, 12, True), ("metadata_props", 16, "Entry", True),
    ])
    message("Opset", [("domain", 1, 9, False), ("version", 2, 3, False)])
    message("Model", [
        ("ir_version", 1, 3, False), ("producer_name", 2, 9, False), ("producer_version", 3, 9, False),
        ("domain", 4, 9, False), ("model_version", 5, 3, False), ("doc_string", 6, 9, False),
        ("graph", 7, "Graph", False), ("opset_import", 8, "Opset", True),
        ("metadata_props", 14, "Entry", True), ("training_info", 20, 12, True),
        ("functions", 25, 12, True), ("configuration", 26, 12, True),
    ])
    pool = descriptor_pool.DescriptorPool()
    pool.Add(descriptor)
    return {item.name: message_factory.GetMessageClass(
        pool.FindMessageTypeByName("cardchemy_qwen4b." + item.name))
        for item in descriptor.message_type}


def _reject_unknown(message):
    from google.protobuf.unknown_fields import UnknownFieldSet
    if len(UnknownFieldSet(message)):
        _unavailable("experiment_graph_unknown_structure")
    for field, value in message.ListFields():
        if field.type == field.TYPE_MESSAGE:
            for child in value if field.is_repeated else (value,):
                _reject_unknown(child)


def _value_contract(value):
    if not value.name or not value.HasField("type") or not value.type.HasField("tensor_type"):
        _unavailable("experiment_onnx_contract")
    if any(value.type.HasField(field) for field in (
        "sequence_type", "map_type", "opaque_type", "sparse_tensor_type", "optional_type",
    )):
        _unavailable("experiment_onnx_contract")
    tensor = value.type.tensor_type
    if tensor.elem_type not in (1, 7) or not tensor.HasField("shape"):
        _unavailable("experiment_onnx_contract")
    shape = []
    for dim in tensor.shape.dim:
        if dim.HasField("dim_value") == dim.HasField("dim_param"):
            _unavailable("experiment_onnx_contract")
        if dim.HasField("dim_value"):
            if dim.dim_value <= 0:
                _unavailable("experiment_onnx_contract")
            shape.append(dim.dim_value)
        elif not dim.dim_param or len(dim.dim_param) > 64:
            _unavailable("experiment_onnx_contract")
        else:
            shape.append(dim.dim_param)
    return ("tensor(float)" if tensor.elem_type == 1 else "tensor(int64)", tuple(shape))


def _validate_tensor(tensor):
    if tensor.HasField("segment") or tensor.data_location not in (0, 1):
        _unavailable("experiment_external_data_invalid")
    if not tensor.external_data:
        if tensor.data_location == 1:
            _unavailable("experiment_external_data_invalid")
        return 0
    if tensor.data_location != 1 or any(tensor.HasField(field) for field in ("raw_data",)) or any(
        getattr(tensor, field) for field in ("float_data", "int32_data", "string_data",
                                           "int64_data", "double_data", "uint64_data")
    ):
        _unavailable("experiment_external_data_invalid")
    entries = {}
    for entry in tensor.external_data:
        if (not entry.HasField("key") or not entry.HasField("value")
            or entry.key in entries or entry.key not in ("location", "offset", "length")):
            _unavailable("experiment_external_data_invalid")
        entries[entry.key] = entry.value
    if entries.get("location") != "model.onnx.data":
        _unavailable("experiment_external_data_invalid")
    for field in ("offset", "length"):
        if field in entries and re.fullmatch(r"[0-9]{1,20}", entries[field]) is None:
            _unavailable("experiment_external_data_invalid")
    size = PINS["model.onnx.data"][0]
    offset = int(entries.get("offset", "0"))
    length = int(entries.get("length", str(size - offset)))
    if offset < 0 or length <= 0 or offset + length > size:
        _unavailable("experiment_external_data_invalid")
    return 1


def inspect_graph_bytes(body: bytes) -> int:
    """Validate closed metadata and every supported external tensor before load."""
    if not isinstance(body, bytes) or not 0 < len(body) <= PINS["model.onnx"][0]:
        _unavailable("experiment_graph_invalid")
    try:
        model = _protobuf_types()["Model"]()
        model.ParseFromString(body)
        _reject_unknown(model)
        if (model.ir_version != 10 or not model.HasField("graph") or model.training_info
            or model.functions or model.configuration):
            _unavailable("experiment_graph_structure")
        opsets = [(item.domain, item.version) for item in model.opset_import]
        if sorted(opsets) != [("", 21), ("com.microsoft", 1)]:
            _unavailable("experiment_graph_structure")
        graph = model.graph
        if (graph.sparse_initializer or graph.quantization_annotation
            or not graph.node or len(graph.node) > 16384 or len(graph.initializer) > 16384):
            _unavailable("experiment_graph_structure")
        for values, expected in ((graph.input, _INPUTS), (graph.output, _OUTPUTS)):
            names = [value.name for value in values]
            if len(names) != len(set(names)) or set(names) != set(expected):
                _unavailable("experiment_onnx_contract")
            if any(_value_contract(value) != expected[value.name] for value in values):
                _unavailable("experiment_onnx_contract")
        names = [tensor.name for tensor in graph.initializer]
        if any(not name for name in names) or len(set(names)) != len(names):
            _unavailable("experiment_graph_structure")
        external = sum(_validate_tensor(tensor) for tensor in graph.initializer)
        for node in graph.node:
            if (node.domain, node.op_type) not in _OPERATORS or node.overload or node.device_configurations:
                _unavailable("experiment_graph_structure")
            for attr in node.attribute:
                if (any(attr.HasField(field) for field in ("g", "tp", "sparse_tensor"))
                    or attr.graphs or attr.type_protos or attr.sparse_tensors or attr.ref_attr_name):
                    _unavailable("experiment_graph_structure")
                if attr.HasField("t"):
                    external += _validate_tensor(attr.t)
                external += sum(_validate_tensor(tensor) for tensor in attr.tensors)
        if not external:
            _unavailable("experiment_external_data_invalid")
        return external
    except LocalSupportUnavailable:
        raise
    except Exception:
        _unavailable("experiment_graph_invalid")


def verify_artifacts(root: Path, *, runtime_only_diagnostic: bool = False) -> int:
    """Verify the pinned bundle; a separate diagnostic may omit only README.

    The model card is not read by ORT or the tokenizer. This exception is only
    for an explicitly selected, incomplete-bundle public experiment; normal
    callers still require and hash all eight files.
    """
    if not isinstance(root, Path) or root.is_symlink() or not root.is_dir():
        _unavailable("experiment_artifacts_unavailable")
    absolute = root.absolute()
    if any(parent.is_symlink() for parent in absolute.parents):
        _unavailable("experiment_artifacts_unavailable")
    total = 0
    readme_missing = False
    for name, (size, digest) in PINS.items():
        path = root / name
        if (runtime_only_diagnostic and name == "README.md"
            and not path.is_symlink() and not path.exists()):
            readme_missing = True
            continue
        if path.is_symlink() or not path.is_file() or path.stat().st_size != size:
            _unavailable("experiment_artifact_invalid")
        with path.open("rb") as source:
            if hashlib.file_digest(source, "sha256").hexdigest() != digest:
                _unavailable("experiment_artifact_digest")
        total += size
    if runtime_only_diagnostic and not readme_missing:
        _unavailable("experiment_diagnostic_requires_missing_readme")
    if total > MAX_BUNDLE_BYTES:
        _unavailable("experiment_artifact_budget")
    try:
        config = json.loads((root / "config.json").read_text(encoding="utf-8"))
        genai = json.loads((root / "genai_config.json").read_text(encoding="utf-8"))
        if any(config.get(key) != value for key, value in _EXPECTED_MODEL.items()):
            _unavailable("experiment_model_contract")
        decoder = genai["model"]["decoder"]
        if (genai["model"]["vocab_size"] != 151936 or decoder["filename"] != "model.onnx"
            or decoder["num_hidden_layers"] != 36 or decoder["num_key_value_heads"] != 8
            or decoder["head_size"] != 128 or decoder["session_options"]["provider_options"] != []):
            _unavailable("experiment_model_contract")
    except LocalSupportUnavailable:
        raise
    except Exception:
        _unavailable("experiment_model_contract")
    inspect_graph_bytes((root / "model.onnx").read_bytes())
    return total


def validate_session_metadata(session) -> None:
    for values, expected in ((session.get_inputs(), _INPUTS), (session.get_outputs(), _OUTPUTS)):
        names = [item.name for item in values]
        if len(names) != len(set(names)) or set(names) != set(expected):
            _unavailable("experiment_onnx_contract")
        if any((item.type, tuple(item.shape)) != expected[item.name] for item in values):
            _unavailable("experiment_onnx_contract")
    if session.get_providers() != ["CPUExecutionProvider"]:
        _unavailable("experiment_provider_contract")


class Onnx4BDecisionScorer:
    def __init__(self, root: Path, *, runtime_only_diagnostic: bool = False):
        self.bundle_bytes = (verify_artifacts(root, runtime_only_diagnostic=True)
                             if runtime_only_diagnostic else verify_artifacts(root))
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer
        if ort.__version__ != ORT_VERSION:
            _unavailable("experiment_runtime_contract")
        self.np, self.ort = np, ort
        ort.disable_telemetry_events()
        options = ort.SessionOptions()
        options.intra_op_num_threads, options.inter_op_num_threads = 4, 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        options.log_severity_level = 4
        try:
            self.tokenizer = Tokenizer.from_file(str(root / "tokenizer.json"))
            self.session = ort.InferenceSession(
                str(root / "model.onnx"), providers=["CPUExecutionProvider"], sess_options=options,
            )
            validate_session_metadata(self.session)
            self.label_ids = {}
            for label in ("A", "B", "C"):
                encoded = self.tokenizer.encode(label, add_special_tokens=False).ids
                if len(encoded) != 1 or not 0 <= encoded[0] < 151936 or encoded[0] in self.label_ids:
                    _unavailable("experiment_label_contract")
                self.label_ids[encoded[0]] = label
        except LocalSupportUnavailable:
            raise
        except Exception:
            _unavailable("experiment_session_unavailable")

    def observe(self, prompt: str, *, deadline: float) -> DecisionObservation:
        np = self.np
        started = perf_counter()
        if (type(deadline) not in (int, float) or not math.isfinite(deadline)
            or not isinstance(prompt, str) or not prompt or len(prompt) > 14000):
            _unavailable("experiment_input_invalid")
        deadline = min(deadline, started + MAX_CHECK_SECONDS)
        try:
            ids = self.tokenizer.encode(prompt, add_special_tokens=False).ids
        except Exception:
            _unavailable("experiment_input_invalid")
        if (not ids or len(ids) > MAX_INPUT_TOKENS
            or any(type(token) is not int or not 0 <= token < 151936 for token in ids)):
            _unavailable("experiment_input_budget")
        remaining = deadline - perf_counter()
        if remaining <= 0:
            _unavailable("experiment_latency_budget")
        feed = {
            "input_ids": np.asarray([ids], dtype=np.int64),
            "attention_mask": np.ones((1, len(ids)), dtype=np.int64),
        }
        feed.update({name: np.empty((1, 8, 0, 128), dtype=np.float32)
                     for name in _INPUTS if name.startswith("past_key_values.")})
        run_options = self.ort.RunOptions()
        timer = threading.Timer(remaining, lambda: setattr(run_options, "terminate", True))
        timer.daemon = True
        timer.start()
        try:
            output = self.session.run(["logits"], feed, run_options)[0]
        except Exception:
            _unavailable("experiment_inference_unavailable")
        finally:
            timer.cancel()
        if perf_counter() > deadline:
            _unavailable("experiment_latency_budget")
        if (not isinstance(output, np.ndarray) or output.dtype != np.float32
            or output.shape != (1, len(ids), 151936) or not np.isfinite(output).all()):
            _unavailable("experiment_output_invalid")
        logits = output[0, -1].astype(np.float64)
        if not np.isfinite(logits).all():
            _unavailable("experiment_output_invalid")
        winner = int(np.argmax(logits))
        probabilities = np.exp(logits - np.max(logits))
        probabilities /= probabilities.sum()
        confidence = float(probabilities[winner])
        mass = float(sum(probabilities[token] for token in self.label_ids))
        runner_up = float(np.partition(probabilities, -2)[-2])
        if perf_counter() > deadline:
            _unavailable("experiment_latency_budget")
        return DecisionObservation(self.label_ids.get(winner), confidence, mass,
                                   confidence - runner_up, len(ids))
