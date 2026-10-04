"""The public ranker admission must verify the bundle without scoring a pair."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import preflight_reading_usefulness_bundle as preflight


def _bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    files = {
        preflight.MODEL: b"public pinned model fixture",
        "config.json": b"{}",
        "tokenizer.json": b"{}",
        "README.md": b"license: apache-2.0",
        "LICENSE": b"Apache License\nVersion 2.0",
    }
    monkeypatch.setattr(preflight, "MODEL_SHA256", hashlib.sha256(files[preflight.MODEL]).hexdigest())
    manifest = {
        "schema": "reading_usefulness_bundle_v1",
        "repository": preflight.REPOSITORY,
        "revision": preflight.REVISION,
        "files": {},
    }
    for name, content in files.items():
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        manifest["files"][name] = {
            "size": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return tmp_path


def test_bundle_manifest_and_every_file_must_match(tmp_path, monkeypatch):
    bundle = _bundle(tmp_path, monkeypatch)
    assert preflight.verify_bundle(bundle)["files"] == 5
    (bundle / "config.json").write_bytes(b"[]")
    with pytest.raises(ValueError, match="artifact_identity"):
        preflight.verify_bundle(bundle)


def test_bundle_cannot_silently_add_unapproved_artifact(tmp_path, monkeypatch):
    bundle = _bundle(tmp_path, monkeypatch)
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"]["remote-code.py"] = {"size": 1, "sha256": hashlib.sha256(b"x").hexdigest()}
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="manifest_identity"):
        preflight.verify_bundle(bundle)


def test_model_session_loads_without_run(tmp_path, monkeypatch):
    bundle = _bundle(tmp_path, monkeypatch)
    calls = {"loads": 0, "runs": 0}

    class Tokenizer:
        @classmethod
        def from_file(cls, path):
            assert Path(path) == bundle / "tokenizer.json"
            return cls()

        def no_truncation(self):
            pass

        def no_padding(self):
            pass

        def encode(self, question, passage, *, add_special_tokens):
            assert add_special_tokens
            assert question and passage
            return SimpleNamespace(ids=[1] * 17)

    class Session:
        def __init__(self, path, *, sess_options, providers):
            assert Path(path) == bundle / preflight.MODEL
            assert providers == ["CPUExecutionProvider"]
            assert sess_options.intra_op_num_threads == 4
            calls["loads"] += 1

        def get_inputs(self):
            return [SimpleNamespace(name="input_ids"), SimpleNamespace(name="attention_mask")]

        def get_outputs(self):
            return [SimpleNamespace(name="logits")]

        def run(self, *_args, **_kwargs):
            calls["runs"] += 1
            raise AssertionError("load-only must never score")

    monkeypatch.setitem(sys.modules, "onnxruntime", SimpleNamespace(
        SessionOptions=SimpleNamespace,
        ExecutionMode=SimpleNamespace(ORT_SEQUENTIAL="sequential"),
        InferenceSession=Session,
    ))
    monkeypatch.setitem(sys.modules, "tokenizers", SimpleNamespace(Tokenizer=Tokenizer))
    monkeypatch.setattr(preflight, "peak_rss", lambda: 1234)
    result = preflight.load_only(bundle)
    assert result["model_run_calls"] == result["network_requests"] == 0
    assert result["pair_tokens"] == 17
    assert calls == {"loads": 1, "runs": 0}
