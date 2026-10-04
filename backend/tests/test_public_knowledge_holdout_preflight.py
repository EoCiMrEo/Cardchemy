"""The public source preflight must refuse drift before any paid operation."""

import hashlib
import json
from pathlib import Path
import tempfile

import pytest

from app.ai.contracts import ExtractedDocument, ExtractedPage
from app.config import Settings
from scripts import preflight_public_knowledge_holdout as preflight


def _manifest(tmp_path: Path) -> tuple[Path, str]:
    rows = []
    for index in (1, 2):
        name = f"lecture-{index}.pdf"
        raw = f"%PDF-1.7\nfixture-{index}".encode()
        (tmp_path / name).write_bytes(raw)
        rows.append({
            "file": name,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "source_url": f"https://example.org/{name}",
            "license_url": "https://creativecommons.org/licenses/by/4.0/",
            "attribution": "Fixture author, CC BY 4.0",
        })
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"schema": preflight.SCHEMA, "sources": rows}), encoding="utf-8")
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def _holdout(tmp_path: Path, sources: list[dict[str, str]]) -> tuple[Path, str]:
    rows = []
    for index, group in enumerate(("direct", "paraphrase", "follow_up") * 4):
        rows.append({
            "id": f"T{index + 1:02d}", "group": group,
            "document_sha256": sources[index % 2]["sha256"],
            "question": f"What does source {index + 1} describe?",
            "prior_question": "Tell me about this topic." if group == "follow_up" else "",
            "gold_physical_page": 1,
            "gold_window_exact_extracted_text": "One public source detail.",
        })
    path = tmp_path / "holdout.json"
    path.write_text(json.dumps({
        "schema": "cardchemy_public_original_pdf_holdout_v2", "cases": rows,
    }), encoding="utf-8")
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def test_preflight_counts_only_and_never_needs_provider_or_database(tmp_path, monkeypatch):
    assert Path(tempfile.gettempdir()).resolve() in tmp_path.resolve().parents
    path, digest = _manifest(tmp_path)
    monkeypatch.setattr(
        preflight.PDFProcessor, "extract_text_in_subprocess",
        lambda *args, **kwargs: ExtractedDocument(pages=[
            ExtractedPage(page_number=1, text="Heading\n\nOne public source detail."),
            ExtractedPage(page_number=2, text="Another public source detail."),
        ]),
    )
    directory, sources, actual = preflight.load_manifest(path, digest)
    holdout, holdout_digest = _holdout(directory, sources)
    cases, query_tokens, _ = preflight.load_holdout(
        holdout, holdout_digest, directory=directory,
        source_hashes={source["sha256"] for source in sources},
    )
    report = preflight.inspect_sources(directory, sources, cases)
    assert actual == digest
    assert len(cases) == 12 and 0 < query_tokens <= 1024
    assert report["provider_requests"] == 0
    assert report["database_writes"] == 0
    assert report["estimated_document_requests"] == 2
    assert [row["pages"] for row in report["sources"]] == [2, 2]
    assert "source_url" not in json.dumps(report)
    assert "public source detail" not in json.dumps(report)


def test_preflight_rejects_manifest_and_source_drift(tmp_path, monkeypatch):
    path, digest = _manifest(tmp_path)
    with pytest.raises(preflight.Refusal, match="manifest_changed"):
        preflight.load_manifest(path, "0" * 64)
    directory, sources, _ = preflight.load_manifest(path, digest)
    (directory / sources[0]["file"]).write_bytes(b"%PDF-1.7\nchanged")
    with pytest.raises(preflight.Refusal, match="pdf_changed"):
        preflight.inspect_sources(directory, sources)


@pytest.mark.parametrize("field,value", [
    ("file", "../different.pdf"),
    ("license_url", "http://example.org/license"),
    ("source_url", "https://user:password@example.org/file.pdf"),
    ("sha256", "f" * 63),
])
def test_preflight_requires_safe_attributed_manifest(tmp_path, field, value):
    path, _ = _manifest(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["sources"][0][field] = value
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(preflight.Refusal, match="manifest_invalid"):
        preflight.load_manifest(path, hashlib.sha256(path.read_bytes()).hexdigest())


def test_preflight_rejects_more_than_two_document_batches(tmp_path, monkeypatch):
    path, digest = _manifest(tmp_path)
    monkeypatch.setattr(
        preflight.PDFProcessor, "extract_text_in_subprocess",
        lambda *args, **kwargs: ExtractedDocument(pages=[
            ExtractedPage(page_number=index, text=f"Page {index} explains a unique detail.")
            for index in range(1, 34)
        ]),
    )
    directory, sources, _ = preflight.load_manifest(path, digest)
    with pytest.raises(preflight.Refusal, match="paid_envelope_exceeded"):
        preflight.inspect_sources(directory, sources)


def test_preflight_refuses_changed_code_profile(monkeypatch):
    preflight._check_code_defaults()
    monkeypatch.setattr(Settings.model_fields["rag_embedding_batch_size"], "default", 16)
    with pytest.raises(preflight.Refusal, match="profile_default_changed"):
        preflight._check_code_defaults()


def test_preflight_rejects_changed_or_unrelated_holdout(tmp_path):
    manifest, digest = _manifest(tmp_path)
    directory, sources, _ = preflight.load_manifest(manifest, digest)
    holdout, holdout_digest = _holdout(directory, sources)
    with pytest.raises(preflight.Refusal, match="holdout_changed"):
        preflight.load_holdout(
            holdout, "0" * 64, directory=directory,
            source_hashes={source["sha256"] for source in sources},
        )
    data = json.loads(holdout.read_text(encoding="utf-8"))
    data["cases"][0]["document_sha256"] = "a" * 64
    holdout.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(preflight.Refusal, match="holdout_invalid"):
        preflight.load_holdout(
            holdout, hashlib.sha256(holdout.read_bytes()).hexdigest(),
            directory=directory,
            source_hashes={source["sha256"] for source in sources},
        )


def test_preflight_refuses_retired_nonliteral_window_roster(tmp_path):
    manifest, digest = _manifest(tmp_path)
    directory, sources, _ = preflight.load_manifest(manifest, digest)
    holdout, _ = _holdout(directory, sources)
    data = json.loads(holdout.read_text(encoding="utf-8"))
    data["schema"] = "cardchemy_public_original_pdf_holdout_v1"
    holdout.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(preflight.Refusal, match="holdout_invalid"):
        preflight.load_holdout(
            holdout, hashlib.sha256(holdout.read_bytes()).hexdigest(),
            directory=directory,
            source_hashes={source["sha256"] for source in sources},
        )


def test_preflight_accepts_null_prior_only_for_standalone_questions(tmp_path):
    manifest, digest = _manifest(tmp_path)
    directory, sources, _ = preflight.load_manifest(manifest, digest)
    holdout, _ = _holdout(directory, sources)
    data = json.loads(holdout.read_text(encoding="utf-8"))
    data["cases"][0]["prior_question"] = None
    holdout.write_text(json.dumps(data), encoding="utf-8")
    preflight.load_holdout(
        holdout, hashlib.sha256(holdout.read_bytes()).hexdigest(),
        directory=directory, source_hashes={source["sha256"] for source in sources},
    )
    data["cases"][2]["prior_question"] = None
    holdout.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(preflight.Refusal, match="holdout_invalid"):
        preflight.load_holdout(
            holdout, hashlib.sha256(holdout.read_bytes()).hexdigest(),
            directory=directory, source_hashes={source["sha256"] for source in sources},
        )


def test_preflight_rejects_nonliteral_gold_window(tmp_path, monkeypatch):
    manifest, digest = _manifest(tmp_path)
    directory, sources, _ = preflight.load_manifest(manifest, digest)
    holdout, holdout_digest = _holdout(directory, sources)
    rows, _, _ = preflight.load_holdout(
        holdout, holdout_digest, directory=directory,
        source_hashes={source["sha256"] for source in sources},
    )
    rows[0]["gold_window_exact_extracted_text"] = "A paraphrased claim."
    monkeypatch.setattr(
        preflight.PDFProcessor, "extract_text_in_subprocess",
        lambda *args, **kwargs: ExtractedDocument(pages=[
            ExtractedPage(page_number=1, text="One public source detail."),
        ]),
    )
    with pytest.raises(preflight.Refusal, match="gold_window_invalid"):
        preflight.inspect_sources(directory, sources, rows)
