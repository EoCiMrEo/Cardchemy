"""Keyless, database-free contracts for the local owner review packet."""

import asyncio
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from uuid import UUID

import pytest


SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import build_private_lane6_review_packet as packet  # noqa: E402


_CONTENTS = (
    "BLEU means Bilingual Evaluation Understudy.",
    "BLEU evaluates n-grams against a reference translation.",
    "Cosine similarity compares vector angle rather than magnitude.",
    "Bag-of-words ignores word order.",
    "Logistic regression uses a sigmoid to produce probabilities.",
    "Topic modeling can analyze legal documents.",
)


def _sources(*, first_content: str = _CONTENTS[0], page_matches: bool = True):
    contents = (first_content, *_CONTENTS[1:])
    chunks = tuple(SimpleNamespace(
        chunk_id=UUID(int=index + 1), document_id=UUID(int=index + 101),
        page_number=probe.page, section="Synthetic heading",
        content=content,
    ) for index, (probe, content) in enumerate(zip(packet.PROBES, contents, strict=True)))
    pages = {chunk.chunk_id: chunk.content for chunk in chunks}
    if not page_matches:
        pages[chunks[0].chunk_id] = "Synthetic page without the quote."
    slots = {chunk.document_id: index for index, chunk in enumerate(chunks, 1)}
    return chunks, pages, slots


def _allow_local_output(monkeypatch, tmp_path):
    monkeypatch.setattr(packet, "IN_ANSWER_CONTAINER", False)
    monkeypatch.setenv(packet.OUTPUT_ROOT_ENV, str(tmp_path))
    monkeypatch.setattr(packet.tempfile, "gettempdir", lambda: str(tmp_path))
    return packet.validated_output_root()


def test_packet_has_exactly_twenty_predeclared_cases_without_invented_access_sources():
    assert len(packet.CASES) == 20
    assert len({case.case_id for case in packet.CASES}) == 20
    assert {case.category for case in packet.CASES} == {
        "direct", "paraphrase", "resolvable_followup", "ambiguous_followup",
        "conflicting_claim", "unsupported_question", "unpublished_boundary",
        "cross_subject_boundary", "provider_unavailable_control",
        "malformed_output_control", "feasible_generation_source",
        "sparse_generation_source",
    }
    assert sum(case.category == "direct" for case in packet.CASES) == 6
    assert sum(case.category == "paraphrase" for case in packet.CASES) == 4
    assert all(case.source_probe is None for case in packet.CASES if case.category in {
        "unpublished_boundary", "cross_subject_boundary", "provider_unavailable_control",
        "malformed_output_control", "feasible_generation_source", "sparse_generation_source",
    })


def test_review_html_uses_only_bound_source_text_and_escapes_it():
    private_sentinel = "<script>private-source-sentinel</script>"
    chunks, pages, slots = _sources(
        first_content=_CONTENTS[0] + " " + private_sentinel,
    )
    html, counts = packet.render_packet(chunks, pages, slots)
    assert counts == {"case_count": 20, "source_bound_case_count": 12,
                      "planned_separate_control_count": 8,
                      "source_missing_case_count": 0}
    assert "&lt;script&gt;private-source-sentinel&lt;/script&gt;" in html
    assert private_sentinel not in html
    assert chunks[0].document_id.hex not in html
    assert "owner assessment (not saved" in html.casefold()
    assert 'name="H01"' in html
    assert 'name="H02"' not in html
    assert "form-action &#39;none&#39;" in html
    assert "No other Subject source is selected" in html
    assert "No source has been nominated" in html


def test_planned_controls_are_not_shown_as_errors_or_owner_review_questions():
    html, counts = packet.render_packet(*_sources())
    for case_id in ("H02", "B01", "B02", "F01", "F02", "G01", "G02"):
        section = html.split(f"<h2>{case_id}", 1)[1].split("</section>", 1)[0]
        assert "Planned separate control — no owner review needed here." in section
        assert "Source/control unavailable" not in section
        assert f'name="{case_id}"' not in section
    unsupported = html.split("<h2>N02", 1)[1].split("</section>", 1)[0]
    assert "Corpus-wide unsupported case pending separate evaluation." in unsupported
    assert 'name="N02"' not in unsupported
    conflict = html.split("<h2>N01", 1)[1].split("</section>", 1)[0]
    assert 'name="N01"' in conflict
    assert "Choose No if it lacks counter-evidence" in conflict
    assert counts["planned_separate_control_count"] == 8


def test_missing_or_misaligned_source_stays_unavailable_and_is_not_printed():
    chunks, pages, slots = _sources(page_matches=False)
    status, pointer, quote = packet._source_for_case(packet.CASES[0], chunks, pages, slots)
    assert (status, pointer, quote) == (
        "canonical_page_mismatch", "No source selected", "",
    )
    html, counts = packet.render_packet(chunks, pages, slots)
    assert counts["source_bound_case_count"] == 8  # Direct, paraphrase, follow-up and conflict lose one source.
    assert counts["source_missing_case_count"] == 4
    assert "canonical page mismatch" in html
    assert "<pre>BLEU means Bilingual Evaluation Understudy.</pre>" not in html
    assert packet._source_for_case(packet.CASES[0], (), {}, {})[0] == "chunk_unavailable"


def test_write_creates_two_new_neutral_temp_packets_without_overwriting(monkeypatch, tmp_path):
    output_root = _allow_local_output(monkeypatch, tmp_path)
    first = packet.write_packet("first", output_root=output_root)
    second = packet.write_packet("second", output_root=output_root)
    assert first != second
    assert first.parent.parent == tmp_path.resolve()
    assert first.name == second.name == "review.html"
    assert first.read_text(encoding="utf-8") == "first"
    assert second.read_text(encoding="utf-8") == "second"


def test_default_cli_performs_no_database_read_or_write(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["packet"])
    async def forbidden(**_kwargs):
        raise AssertionError("preflight must not read the database")
    monkeypatch.setattr(packet, "_eligible_owner_chunks", forbidden)
    assert packet.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result == {"status": "preflight_ready", "case_count": 20,
                      "provider_requests": 0, "database_reads": 0,
                      "database_writes": 0}


def test_build_uses_current_scoped_sources_without_exposing_them_in_result(monkeypatch, tmp_path):
    _allow_local_output(monkeypatch, tmp_path)
    chunks, pages, slots = _sources(first_content=_CONTENTS[0] + " private-source-sentinel")
    read_calls = []
    close_calls = []
    async def read(*, with_pages):
        read_calls.append(with_pages)
        return chunks, True, pages, slots
    async def close():
        close_calls.append(True)
    monkeypatch.setattr(packet, "_eligible_owner_chunks", read)
    monkeypatch.setattr(packet, "close_database", close)
    monkeypatch.setattr(packet, "write_packet", lambda html, *, output_root: output_root / "review.html")
    result = asyncio.run(packet.build_packet())
    assert read_calls == close_calls == [True]
    assert result["status"] == "packet_written"
    assert result["reviewed_new_labels"] == result["provider_requests"] == result["database_writes"] == 0
    assert "private-source-sentinel" not in json.dumps(result)


def test_failed_scoped_read_does_not_write_packet_and_closes_database(monkeypatch, tmp_path):
    _allow_local_output(monkeypatch, tmp_path)
    chunks, _pages, slots = _sources()
    async def read(*, with_pages):
        assert with_pages
        return chunks, False, {}, slots
    closed = []
    async def close():
        closed.append(True)
    monkeypatch.setattr(packet, "_eligible_owner_chunks", read)
    monkeypatch.setattr(packet, "close_database", close)
    monkeypatch.setattr(packet, "write_packet", lambda _html, *, output_root: pytest.fail("must not write"))
    with pytest.raises(packet.ProbeUnavailable, match="scope_changed"):
        asyncio.run(packet.build_packet())
    assert closed == [True]


def test_missing_output_root_blocks_database_before_create(monkeypatch):
    monkeypatch.delenv(packet.OUTPUT_ROOT_ENV, raising=False)
    async def forbidden(**_kwargs):
        raise AssertionError("invalid output root must block before private DB read")
    monkeypatch.setattr(packet, "_eligible_owner_chunks", forbidden)
    with pytest.raises(packet.ProbeUnavailable, match="review_output_root_unavailable"):
        asyncio.run(packet.build_packet())


def test_tempfile_fallback_or_missing_container_mount_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setenv(packet.OUTPUT_ROOT_ENV, str(tmp_path))
    monkeypatch.setattr(packet.tempfile, "gettempdir", lambda: str(tmp_path.parent))
    monkeypatch.setattr(packet, "IN_ANSWER_CONTAINER", False)
    with pytest.raises(packet.ProbeUnavailable, match="review_output_root_unavailable"):
        packet.validated_output_root()

    monkeypatch.setattr(packet.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(packet, "IN_ANSWER_CONTAINER", True)
    monkeypatch.setattr(packet, "CONTAINER_REVIEW_MOUNT", tmp_path)
    monkeypatch.setattr(packet.os.path, "ismount", lambda _path: False)
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    with pytest.raises(packet.ProbeUnavailable, match="review_output_root_unavailable"):
        packet.validated_output_root()
