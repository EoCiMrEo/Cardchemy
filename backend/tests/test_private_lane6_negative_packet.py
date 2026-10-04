"""Keyless, database-free contracts for the optional private negative packet."""

import asyncio
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from uuid import UUID

import pytest


SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import build_private_lane6_negative_packet as packet  # noqa: E402


def _sources(*, page_matches=True):
    first = "BLEU measures n-gram overlap against a reference translation."
    second = "Bag-of-Words does not preserve word order."
    chunks = (
        SimpleNamespace(chunk_id=UUID(int=1), document_id=UUID(int=101),
                        page_number=22, section="BLEU evaluation", content=first),
        SimpleNamespace(chunk_id=UUID(int=2), document_id=UUID(int=102),
                        page_number=9, section="Bag-of-Words", content=second),
    )
    pages = {chunks[0].chunk_id: first, chunks[1].chunk_id: second}
    if not page_matches:
        pages[chunks[0].chunk_id] = "Unrelated canonical page."
    slots = {chunks[0].document_id: 1, chunks[1].document_id: 2}
    return chunks, pages, slots


def test_cases_require_explicit_refutation_or_separate_relevance_label():
    assert [case.case_id for case in packet.CASES] == ["N11", "N12", "U01"]
    assert [case.category for case in packet.CASES] == [
        "explicit_contradiction", "explicit_contradiction", "unrelated_question",
    ]
    assert all(case.source_probe is not None for case in packet.CASES)
    assert "acronym" not in {case.source_probe for case in packet.CASES}


def test_exact_source_packet_escapes_private_text_and_never_claims_a_label():
    chunks, pages, slots = _sources()
    sentinel = "<script>private-sentinel</script>"
    chunks[0].content += " " + sentinel
    pages[chunks[0].chunk_id] = chunks[0].content
    html, counts = packet.render_packet(chunks, pages, slots)
    assert counts == {"case_count": 3, "source_bound_case_count": 3,
                      "source_missing_case_count": 0}
    assert sentinel not in html
    assert "&lt;script&gt;private-sentinel&lt;/script&gt;" in html
    assert 'name="N11_refutes"' in html
    assert 'name="N12_refutes"' in html
    assert 'name="U01_source"' in html
    assert 'name="U01_relevance"' in html
    assert "Radio choices are not saved" in html
    assert "form-action &#39;none&#39;" in html
    assert str(chunks[0].chunk_id) not in html


def test_missing_canonical_page_refuses_negative_label_even_with_chunk():
    html, counts = packet.render_packet(*_sources(page_matches=False))
    assert counts == {"case_count": 3, "source_bound_case_count": 1,
                      "source_missing_case_count": 2}
    assert 'name="N11_refutes"' not in html
    assert 'name="U01_source"' not in html
    assert 'name="U01_relevance"' not in html
    assert 'name="N12_refutes"' in html
    assert "No current source-bound negative label can be recorded" in html


def test_default_cli_never_reads_database(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["negative-packet"])

    async def forbidden(**_kwargs):
        raise AssertionError("default mode must not read private data")

    monkeypatch.setattr(packet, "_eligible_owner_chunks", forbidden)
    assert packet.main() == 0
    assert json.loads(capsys.readouterr().out) == {
        "status": "preflight_ready", "case_count": 3,
        "provider_requests": 0, "database_reads": 0, "database_writes": 0,
    }


def test_invalid_temp_root_stops_before_private_read(monkeypatch):
    def forbidden():
        raise packet.ProbeUnavailable("review_output_root_unavailable")

    async def forbidden_read(**_kwargs):
        raise AssertionError("invalid output root must stop before DB read")

    monkeypatch.setattr(packet, "validated_output_root", forbidden)
    monkeypatch.setattr(packet, "_eligible_owner_chunks", forbidden_read)
    with pytest.raises(packet.ProbeUnavailable, match="review_output_root_unavailable"):
        asyncio.run(packet.build_packet())


def test_build_is_read_only_closes_database_and_outputs_only_neutral_metadata(monkeypatch, tmp_path):
    chunks, pages, slots = _sources()
    monkeypatch.setattr(packet, "validated_output_root", lambda: tmp_path)
    calls = []

    async def read(*, with_pages):
        calls.append(("read", with_pages))
        return chunks, True, pages, slots

    async def close():
        calls.append(("close",))

    monkeypatch.setattr(packet, "_eligible_owner_chunks", read)
    monkeypatch.setattr(packet, "close_database", close)
    monkeypatch.setattr(packet, "write_packet", lambda _html, *, output_root: output_root / "review.html")
    result = asyncio.run(packet.build_packet())
    assert calls == [("read", True), ("close",)]
    assert result["reviewed_new_labels"] == 0
    assert result["provider_requests"] == result["database_writes"] == 0
    assert result["source_bound_case_count"] == 3
    assert "BLEU" not in json.dumps(result)


def test_scope_change_stops_packet_and_closes_database(monkeypatch, tmp_path):
    monkeypatch.setattr(packet, "validated_output_root", lambda: tmp_path)
    chunks, pages, slots = _sources()

    async def read(*, with_pages):
        return chunks, False, pages, slots

    closed = []

    async def close():
        closed.append(True)

    monkeypatch.setattr(packet, "_eligible_owner_chunks", read)
    monkeypatch.setattr(packet, "close_database", close)
    monkeypatch.setattr(packet, "write_packet", lambda _html, *, output_root: pytest.fail("must not write"))
    with pytest.raises(packet.ProbeUnavailable, match="scope_changed"):
        asyncio.run(packet.build_packet())
    assert closed == [True]
