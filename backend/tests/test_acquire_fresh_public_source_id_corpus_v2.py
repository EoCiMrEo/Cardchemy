"""Keyless fake-transport contracts for the fresh eight-PDF source corpus."""

from __future__ import annotations

import io
import json
from pathlib import Path
import sys

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import acquire_fresh_public_source_id_corpus_v2 as corpus


class Response:
    def __init__(self, body=b"", status=200, headers=None, blocks=None):
        self.body = body
        self.status_code = status
        self.headers = headers or {}
        self.blocks = blocks
        self.streamed = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def iter_content(self, _size):
        self.streamed = True
        yield from self.blocks if self.blocks is not None else (self.body,)


class Session:
    def __init__(self, answers):
        self.answers = list(answers)
        self.requests = []

    def get(self, url, *, timeout, stream, allow_redirects, headers):
        self.requests.append((url, timeout, stream, allow_redirects, headers))
        response = self.answers.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def schedule_bytes():
    return ("<html>" + "".join(
        f'<a href="{corpus.pdf_url(number)}">lecture</a>'
        for _, number, _ in corpus.ROSTER) + "</html>").encode()


def pdf_bytes(pages, identity, license_text="CC BY 4.0", chars=85):
    writer = PdfWriter()
    for number in range(pages):
        page = writer.add_blank_page(width=612, height=792)
        line = (f"{license_text} " if number == 0 else "") + f"{identity} " + "A" * chars
        content = DecodedStreamObject()
        content.set_data(f"BT /F1 12 Tf 20 700 Td ({line}) Tj ET".encode("ascii"))
        page[NameObject("/Contents")] = writer._add_object(content)
        page[NameObject("/Resources")] = DictionaryObject({
            NameObject("/Font"): DictionaryObject({
                NameObject("/F1"): writer._add_object(DictionaryObject({
                    NameObject("/Type"): NameObject("/Font"),
                    NameObject("/Subtype"): NameObject("/Type1"),
                    NameObject("/BaseFont"): NameObject("/Helvetica"),
                }))
            })
        })
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def comparisons(tmp_path, monkeypatch):
    result = {}
    sets = {
        "ece448_sp2020": ("illinois-ece448-sp2020-reading-usefulness-v4", [
            {"url": f"https://{corpus.HOST}/ece448/sp2020/slides/lec{i + 1:02d}.pdf",
             "sha256": f"{i + 101:064x}"} for i in range(14)]),
        "reserved_illinois": ("illinois-ece448-sp2020-reserved", [
            {"url": url, "sha256": digest}
            for url, digest in corpus.RESERVED_HASHES.items()]),
    }
    for role, (identity, documents) in sets.items():
        path = tmp_path / f"{role}.json"
        path.write_bytes(corpus.canonical_bytes({"corpus_id": identity,
                                                "documents": documents}))
        result[role] = path
    monkeypatch.setattr(corpus, "SP2020_MANIFEST_SHA256",
                        corpus.sha256(result["ece448_sp2020"].read_bytes()))
    return result


@pytest.fixture(scope="module")
def pdf_roster():
    return [pdf_bytes(pages, f"lecture{number:02d}")
            for _, number, pages in corpus.ROSTER]


def test_default_is_inert_and_preregistration_literal_is_frozen(capsys, monkeypatch):
    monkeypatch.setattr(corpus.requests, "Session", lambda: pytest.fail("network"))
    assert corpus.main([]) == 0
    preflight = json.loads(capsys.readouterr().out)
    assert preflight["network_requests"] == 0
    assert preflight["preregistration_sha256"] == corpus.sha256(
        corpus.canonical_bytes(corpus.preregistration()))
    assert [(row["split"], row["pages"]) for row in preflight["preregistration"]["documents"]] == [
        (split, pages) for split, _, pages in corpus.ROSTER]


def test_comparison_preflight_needs_no_approval_and_makes_no_request(
        tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(corpus, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(corpus.requests, "Session", lambda: pytest.fail("network"))
    old = comparisons(tmp_path, monkeypatch)
    argv = ["--preflight", "--output-name", "fresh-v2-probe",
            "--comparison-sp2020", str(old["ece448_sp2020"]),
            "--comparison-reserved-illinois", str(old["reserved_illinois"])]
    assert corpus.main(argv) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "offline_preflight_ready"
    assert report["network_requests"] == 0
    assert report["output_available"] is True
    assert not (tmp_path / "fresh-v2-probe").exists()
    (tmp_path / "fresh-v2-probe").mkdir()
    assert corpus.main(argv) == 1
    assert "output_path_already_exists" in capsys.readouterr().err


@pytest.mark.parametrize("url", [
    "http://courses.grainger.illinois.edu/ece448/sp2022/lectures.html",
    "https://courses.grainger.illinois.edu.evil/ece448/sp2022/lectures.html",
    "https://user@courses.grainger.illinois.edu/ece448/sp2022/lectures.html",
    "https://courses.grainger.illinois.edu:443/ece448/sp2022/lectures.html",
    corpus.SCHEDULE_URL + "?x=1", corpus.SCHEDULE_URL + "#part",
    "https://courses.grainger.illinois.edu/ece448/sp2022/slides/lec10.pdf",
])
def test_url_restrictions_reject_unapproved_url(url):
    with pytest.raises(corpus.AcquisitionError, match="source_url_rejected"):
        corpus.checked_url(url, {Path(corpus.SCHEDULE_URL).as_posix(),
                                 "/ece448/sp2022/lectures.html"})


def test_success_exact_roster_manifest_and_independent_rehash(tmp_path, pdf_roster,
                                                             monkeypatch):
    old = comparisons(tmp_path, monkeypatch)
    session = Session([Response(schedule_bytes()),
                       *(Response(raw) for raw in pdf_roster)])
    root = tmp_path / "new"
    result = corpus.acquire(root, session, old, clock=lambda: 1)
    assert result["status"] == "acquired_unlabeled"
    assert result["requests"] == len(session.requests) == 9
    manifest = json.loads((root / "manifest.json").read_text())
    assert manifest["schema"] == corpus.SCHEMA
    assert manifest["schedule"]["sha256"] == corpus.sha256(schedule_bytes())
    assert [(row["split"], row["url"], row["pages"])
            for row in manifest["documents"]] == [
                (split, corpus.pdf_url(number), pages)
                for split, number, pages in corpus.ROSTER]
    assert manifest["labels_written"] is False
    assert corpus.verify_manifest(root, old)["manifest_sha256"] == result["manifest_sha256"]
    (root / "lec04.pdf").write_bytes(b"%PDF-corrupt")
    with pytest.raises(corpus.AcquisitionError, match="pdf_hash_mismatch"):
        corpus.verify_manifest(root, old)


def test_missing_prior_manifest_blocks_before_any_request(tmp_path, monkeypatch):
    old = comparisons(tmp_path, monkeypatch)
    old["ece448_sp2020"] = tmp_path / "missing.json"
    session = Session([])
    with pytest.raises(corpus.AcquisitionError, match="metadata_missing_or_symlink"):
        corpus.acquire(tmp_path / "new", session, old)
    assert not session.requests
    assert not (tmp_path / "new").exists()


def test_old_hash_collision_fails_without_success_manifest(tmp_path, pdf_roster,
                                                            monkeypatch):
    old = comparisons(tmp_path, monkeypatch)
    legacy = json.loads(old["ece448_sp2020"].read_text())
    legacy["documents"][0]["sha256"] = corpus.sha256(pdf_roster[0])
    old["ece448_sp2020"].write_bytes(corpus.canonical_bytes(legacy))
    monkeypatch.setattr(corpus, "SP2020_MANIFEST_SHA256",
                        corpus.sha256(old["ece448_sp2020"].read_bytes()))
    session = Session([Response(schedule_bytes()), Response(pdf_roster[0])])
    root = tmp_path / "new"
    with pytest.raises(corpus.AcquisitionError, match="source_duplicate_hash"):
        corpus.acquire(root, session, old, clock=lambda: 0)
    assert len(session.requests) == 2
    assert not (root / "manifest.json").exists()
    assert json.loads((root / "failure.json").read_text())["reason"] == "source_duplicate_hash"


def test_redirect_bounds_and_no_body_streaming():
    schedule_path = "/ece448/sp2022/lectures.html"
    first = Response(b"do not stream", 302, {"Location": corpus.SCHEDULE_URL})
    second = Response(b"do not stream", 307, {"Location": corpus.SCHEDULE_URL})
    session = Session([first, second, Response(b"ok")])
    fetcher = corpus.BoundedFetcher(session, clock=lambda: 0)
    assert fetcher.fetch(corpus.SCHEDULE_URL, 10) == b"ok"
    assert fetcher.gets == 3 and fetcher.received_bytes == 2
    assert first.streamed is second.streamed is False
    bad = Session([Response(status=302, headers={"Location": corpus.pdf_url(4)})])
    with pytest.raises(corpus.AcquisitionError, match="redirect_file_substitution_rejected"):
        corpus.BoundedFetcher(bad, clock=lambda: 0).fetch(corpus.SCHEDULE_URL, 10)
    assert len(bad.requests) == 1
    third = Session([Response(status=302, headers={"Location": corpus.SCHEDULE_URL})
                     for _ in range(3)])
    with pytest.raises(corpus.AcquisitionError, match="per_fetch_redirect_limit"):
        corpus.BoundedFetcher(third, clock=lambda: 0).fetch(corpus.SCHEDULE_URL, 10)
    assert len(third.requests) == 3


def test_streamed_declared_aggregate_get_and_time_budgets(monkeypatch):
    session = Session([Response(blocks=[b"abc", b"def"],
                                headers={"Content-Length": "2"})])
    fetcher = corpus.BoundedFetcher(session, clock=lambda: 0)
    monkeypatch.setattr(corpus, "MAX_RECEIVED_BYTES", 5)
    with pytest.raises(corpus.AcquisitionError, match="streamed_byte_limit"):
        fetcher.fetch(corpus.SCHEDULE_URL, 10)
    assert fetcher.gets == 1 and fetcher.received_bytes == 6
    monkeypatch.setattr(corpus, "MAX_RECEIVED_BYTES", 84_410_368)
    session = Session([Response(b"x") for _ in range(13)])
    fetcher = corpus.BoundedFetcher(session, clock=lambda: 0)
    for _ in range(13):
        assert fetcher.fetch(corpus.SCHEDULE_URL, 10) == b"x"
    with pytest.raises(corpus.AcquisitionError, match="physical_get_limit"):
        fetcher.fetch(corpus.SCHEDULE_URL, 10)
    assert len(session.requests) == 13
    ticks = iter([0, 0, 0, 1800])
    timer = corpus.BoundedFetcher(Session([Response(b"x")]), clock=lambda: next(ticks))
    with pytest.raises(corpus.AcquisitionError, match="whole_run_time_limit"):
        timer.fetch(corpus.SCHEDULE_URL, 10)


def test_pdf_signature_page_license_and_text_guards():
    valid = pdf_bytes(32, "valid")
    assert corpus.pdf_metrics(valid, 32)["first_page_license"] == "CC BY 4.0"
    with pytest.raises(corpus.AcquisitionError, match="not_pdf"):
        corpus.pdf_metrics(b"not a pdf", 32)
    with pytest.raises(corpus.AcquisitionError, match="pdf_page_count"):
        corpus.pdf_metrics(valid, 33)
    with pytest.raises(corpus.AcquisitionError, match="pdf_missing_first_page_cc_by_4"):
        corpus.pdf_metrics(pdf_bytes(32, "bad", license_text="CC BY 3.0"), 32)
    with pytest.raises(corpus.AcquisitionError, match="pdf_text_quality"):
        corpus.pdf_metrics(pdf_bytes(32, "short", chars=1), 32)
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.encrypt("secret")
    buf = io.BytesIO()
    writer.write(buf)
    with pytest.raises(corpus.AcquisitionError, match="pdf_encrypted"):
        corpus.pdf_metrics(buf.getvalue(), 1)


def test_failure_receipt_no_retry_and_one_use_approval(tmp_path, monkeypatch):
    old = comparisons(tmp_path, monkeypatch)
    session = Session([requests.ConnectionError("opaque")])
    root = tmp_path / "new"
    with pytest.raises(corpus.AcquisitionError, match="transport_failed_no_retry"):
        corpus.acquire(root, session, old, clock=lambda: 0)
    assert len(session.requests) == 1
    assert not (root / "manifest.json").exists()
    assert json.loads((root / "failure.json").read_text())["requests"] == 1
    monkeypatch.setattr(corpus, "gettempdir", lambda: str(tmp_path))
    approval = tmp_path / "approval.json"
    approval.write_bytes(corpus.canonical_bytes({
        "schema": "cardchemy_public_source_id_fresh_acquisition_approval_v1",
        "corpus_id": corpus.CORPUS_ID,
        "preregistration_sha256": corpus.PREREGISTRATION_SHA256,
        "authorization": "I_APPROVE_ONE_PUBLIC_PDF_ACQUISITION",
        "max_gets_including_redirects": 13,
        "approval_id": "a" * 32,
    }))
    corpus.approved_once(approval)
    with pytest.raises(corpus.AcquisitionError, match="approval_already_used"):
        corpus.approved_once(approval)
    assert corpus.provider_credentials_present({"RAG_SOURCE_JUDGE_API_KEY": "secret"})
    assert not corpus.provider_credentials_present({})
