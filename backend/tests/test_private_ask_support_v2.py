"""Keyless, database-free privacy guards for the private local support probe."""

import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
from uuid import uuid4

from app.ai.local_support import NliScores
from app.services.knowledge_retrieval import RetrievedKnowledgeChunk


SCRIPT = Path(__file__).resolve().parents[2] / "scripts/evaluate_private_ask_support_v2.py"
spec = importlib.util.spec_from_file_location("private_ask_support_v2", SCRIPT)
assert spec is not None and spec.loader is not None
probe = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = probe
spec.loader.exec_module(probe)


def _chunk(content: str, *, page: int = 22) -> RetrievedKnowledgeChunk:
    return RetrievedKnowledgeChunk(
        chunk_id=uuid4(), document_id=uuid4(), document_title="private-title-sentinel",
        content_revision_id=uuid4(), index_revision_id=uuid4(),
        page_number=page, section="private-section-sentinel", content=content,
        token_count=20, embedding_space_hash="a" * 64, corpus_revision=1,
        vector_similarity=None, lexical_score=None, vector_rank=None,
        lexical_rank=None, fusion_score=0.0,
    )


def test_source_window_is_exact_contiguous_and_shortest():
    content = (
        "Other material.\n"
        "BLEU means Bilingual Evaluation Understudy.\n"
        "Long unrelated explanation follows.\n"
    )
    quote = probe.shortest_contiguous_line_window(
        content, (r"BLEU", r"Bilingual Evaluation Understudy"),
    )
    assert quote == "BLEU means Bilingual Evaluation Understudy."
    assert quote in content
    assert probe.shortest_contiguous_line_window(
        content, (r"BLEU", r"impossible"),
    ) is None


def test_selection_fails_closed_on_missing_or_ambiguous_source():
    case = probe.PROBES[0]
    match = _chunk("BLEU means Bilingual Evaluation Understudy.")
    assert probe.select_probe_source(case, ())[0] == "chunk_unavailable"
    assert probe.select_probe_source(case, (match, match))[0] == "chunk_ambiguous"
    assert probe.select_probe_source(case, (match,))[0] == "selected"
    no_short_quote = _chunk("BLEU means Bilingual Evaluation Understudy " + "x" * 1200 + ".")
    selection, row, quote = probe.select_probe_source(case, (no_short_quote,))
    assert selection == "quote_unavailable" and row is not None and quote is None


def test_verifier_exception_does_not_expose_private_source(capsys):
    class ExplodingVerifier:
        def evaluate(self, **_kwargs):
            raise RuntimeError("private-source-sentinel")

    row = _chunk("BLEU means Bilingual Evaluation Understudy.")
    claim = SimpleNamespace(
        statement="Authored claim", source=row, source_quote=row.content,
    )
    assert probe._safe_evaluate(
        ExplodingVerifier(), question="Authored question",
        claim=claim, chunk=row,
    ) == "verifier_unavailable"
    assert capsys.readouterr().out == ""


def test_full_report_contains_only_fixed_labels_and_aggregate_numbers(monkeypatch):
    import app.ai.local_support as local_support

    class FakeVerifier:
        def __init__(self, *_args):
            self._nli = object()
            self._qa = object()

        def evaluate(self, **kwargs):
            if "Basic" in kwargs["claims"][0].statement:
                return SimpleNamespace(reason_code="entailment_rejected")
            return SimpleNamespace(reason_code="supported")

    monkeypatch.setattr(probe, "create_local_support_verifier", lambda _path: FakeVerifier())
    monkeypatch.setattr(local_support, "LocalSupportVerifierV2", FakeVerifier, raising=False)
    private = "private-source-sentinel "
    row = _chunk(private + "BLEU means Bilingual Evaluation Understudy.")
    report = probe.evaluate_in_memory(
        (row,), model_dir=Path("unused"), active_space_match=True,
        canonical_pages={row.chunk_id: private + "BLEU means Bilingual Evaluation Understudy."},
    )
    rendered = probe.json.dumps(report)
    for secret in (private.strip(), row.document_title, str(row.chunk_id), str(row.document_id)):
        assert secret not in rendered
    assert report["provider_requests"] == 0
    assert report["active_space_match"] is True
    assert report["results"][0]["eligible_view"] is True
    assert report["results"][0]["wrong_question_v1"] == "supported"
    assert report["exact_quote_claim_pairs_owner_reviewed"] == 0
    assert report["wrong_question_control_informative_only_if_positive_accepted"] is True
    assert set(report["aggregate_ms"]) == {"v1", "v2"}


def test_owner_review_packet_has_page_pointer_without_private_content():
    private = "private-source-sentinel "
    row = _chunk(private + "BLEU means Bilingual Evaluation Understudy.")
    packet = probe.prepare_owner_review_packet(
        (row,), {row.chunk_id: row.content}, {row.document_id: 3},
    )
    first = packet["cases"][0]
    assert first == {
        "topic": "bleu_acronym", "document_slot": 3,
        "page": 22, "selection": "selected",
        "quote_exact_in_chunk": True,
        "quote_exact_in_canonical_page": True,
        "canonical_page_alignment": "exact",
        "owner_review": "pending_exact_quote_question_claim_review",
    }
    assert packet["exact_quote_claim_pairs_owner_reviewed"] == 0
    assert packet["database_writes"] == 0
    rendered = probe.json.dumps(packet)
    for secret in (private.strip(), row.document_title, str(row.chunk_id), str(row.document_id)):
        assert secret not in rendered


def test_owner_review_packet_classifies_page_whitespace_without_rewriting_quote():
    row = _chunk("BLEU means Bilingual Evaluation Understudy.\nFurther details.")
    page = "BLEU means Bilingual Evaluation Understudy.\r\nFurther details."
    packet = probe.prepare_owner_review_packet(
        (row,), {row.chunk_id: page}, {row.document_id: 1},
    )
    assert packet["cases"][0]["canonical_page_alignment"] == "exact"

    row = _chunk("BLEU means Bilingual Evaluation Understudy.")
    page = "BLEU means\nBilingual Evaluation Understudy."
    packet = probe.prepare_owner_review_packet(
        (row,), {row.chunk_id: page}, {row.document_id: 1},
    )
    assert packet["cases"][0]["canonical_page_alignment"] == "whitespace_normalized"

    packet = probe.prepare_owner_review_packet(
        (row,), {row.chunk_id: "Unrelated canonical page."}, {row.document_id: 1},
    )
    assert packet["cases"][0]["canonical_page_alignment"] == "not_found"


def test_owner_review_packet_skips_model_loading(monkeypatch, capsys):
    row = _chunk("BLEU means Bilingual Evaluation Understudy.")

    async def eligible(*, with_pages=False):
        assert with_pages is True
        return (row,), True, {row.chunk_id: row.content}, {row.document_id: 1}

    async def close():
        pass

    def load_model(_path):
        raise AssertionError("model must not load for a review packet")

    monkeypatch.setattr(probe, "_eligible_owner_chunks", eligible)
    monkeypatch.setattr(probe, "close_database", close)
    monkeypatch.setattr(probe, "create_local_support_verifier", load_model)
    monkeypatch.setattr(sys, "argv", ["evaluate_private_ask_support_v2.py", "--owner-review-packet"])
    assert probe.main() == 0
    rendered = capsys.readouterr().out
    assert "private" not in rendered
    assert probe.json.loads(rendered)["cases"][0]["selection"] == "selected"


def _six_review_rows():
    contents = (
        'BLEU means Bilingual Evaluation Understudy <script>alert("source-sentinel")</script>.',
        "BLEU measures n-gram overlap with a reference translation.",
        "Cosine similarity compares angle rather than magnitude.",
        "Bag-of-Words ignores word order.",
        "Logistic regression uses sigmoid to output probability.",
        "Topic modeling applies to legal and medical documents.",
    )
    rows = tuple(
        _chunk(content, page=case.page)
        for case, content in zip(probe.PROBES, contents, strict=True)
    )
    pages = {row.chunk_id: row.content for row in rows}
    slots = {row.document_id: index for index, row in enumerate(rows, 1)}
    return rows, pages, slots


def test_owner_review_html_escapes_private_quote_and_contains_six_checks():
    rows, pages, slots = _six_review_rows()
    rendered = probe.render_owner_review_html(rows, pages, slots)
    assert rendered.count('<section class="case">') == 6
    assert "&lt;script&gt;" in rendered
    assert "<script" not in rendered
    assert "Content-Security-Policy" in rendered
    assert "<form" not in rendered
    assert "https://" not in rendered
    assert rendered.count('value="yes"') == 18
    assert rendered.count('value="no"') == 18
    for row in rows:
        assert str(row.chunk_id) not in rendered
        assert str(row.document_id) not in rendered
        assert row.document_title not in rendered


def test_owner_review_html_refuses_missing_canonical_page():
    rows, pages, slots = _six_review_rows()
    pages.pop(rows[0].chunk_id)
    try:
        probe.render_owner_review_html(rows, pages, slots)
    except probe.ProbeUnavailable as exc:
        assert exc.code == "review_source_unavailable"
    else:
        raise AssertionError("review sheet must require canonical page alignment")


def test_owner_review_html_cli_writes_only_explicit_external_file(
    monkeypatch, capsys, tmp_path,
):
    rows, pages, slots = _six_review_rows()
    destination = tmp_path / "review.html"
    calls = []

    async def eligible(*, with_pages=False):
        calls.append(("read", with_pages))
        return rows, True, pages, slots

    async def close():
        calls.append(("close", None))

    def no_model(_path):
        raise AssertionError("owner review must not load a model")

    monkeypatch.setattr(probe, "_eligible_owner_chunks", eligible)
    monkeypatch.setattr(probe, "close_database", close)
    monkeypatch.setattr(probe, "create_local_support_verifier", no_model)
    monkeypatch.setattr(sys, "argv", [
        "evaluate_private_ask_support_v2.py", "--owner-review-html",
        str(destination),
    ])
    assert probe.main() == 0
    assert calls == [("read", True), ("close", None)]
    assert probe.json.loads(capsys.readouterr().out) == {
        "status": "written", "cases": 6,
    }
    assert destination.is_file()
    assert "&lt;script&gt;" in destination.read_text(encoding="utf-8")
    assert probe.main() == 1
    assert probe.json.loads(capsys.readouterr().out) == {
        "status": "unavailable", "reason": "output_exists",
    }


def test_owner_review_html_rejects_repo_path_without_writing(tmp_path):
    rows, pages, slots = _six_review_rows()
    for destination in (
        Path("relative.html"),
        SCRIPT.parents[1] / "tracked-review.html",
        tmp_path / "review.txt",
    ):
        try:
            probe.write_owner_review_html(destination, rows, pages, slots)
        except probe.ProbeUnavailable as exc:
            assert exc.code == "invalid_output_path"
        else:
            raise AssertionError("unsafe review destination must be rejected")
        assert not destination.exists()


def test_owner_review_html_cli_rejects_invalid_path_before_database(
    monkeypatch, capsys,
):
    async def no_read(**_kwargs):
        raise AssertionError("invalid path must fail before opening the database")

    monkeypatch.setattr(probe, "_eligible_owner_chunks", no_read)
    monkeypatch.setattr(sys, "argv", [
        "evaluate_private_ask_support_v2.py", "--owner-review-html",
        "relative.html",
    ])
    assert probe.main() == 1
    assert probe.json.loads(capsys.readouterr().out) == {
        "status": "unavailable", "reason": "invalid_output_path",
    }


def test_owner_review_html_cli_rejects_other_modes_before_database(
    monkeypatch, capsys, tmp_path,
):
    async def no_read(**_kwargs):
        raise AssertionError("incompatible modes must fail before database")

    monkeypatch.setattr(probe, "_eligible_owner_chunks", no_read)
    monkeypatch.setattr(sys, "argv", [
        "evaluate_private_ask_support_v2.py", "--owner-review-html",
        str(tmp_path / "review.html"), "--replay-answer-contract-v2",
    ])
    assert probe.main() == 1
    assert probe.json.loads(capsys.readouterr().out) == {
        "status": "unavailable", "reason": "invalid_options",
    }


def test_main_hides_internal_error_and_closes_database(monkeypatch, capsys):
    async def unavailable():
        raise RuntimeError("private-source-sentinel")

    closed = []

    async def close():
        closed.append(True)

    monkeypatch.setattr(probe, "_eligible_owner_chunks", unavailable)
    monkeypatch.setattr(probe, "close_database", close)
    monkeypatch.setattr(sys, "argv", ["evaluate_private_ask_support_v2.py"])
    assert probe.main() == 1
    captured = capsys.readouterr()
    assert captured.out.strip() == '{"status":"unavailable","reason":"probe_failed"}'
    assert captured.err == ""
    assert closed == [True]


def test_page_span_requires_exact_heading_to_answer_line():
    case = probe.PROBES[2]
    row = _chunk("They compare angles rather than magnitudes.", page=13)
    row = probe.RetrievedKnowledgeChunk(
        **{name: getattr(row, name) for name in row.__dataclass_fields__
           if name != "section"}, section="Cosine Similarity",
    )
    page = (
        "Unrelated section.\n"
        "Cosine Similarity\n"
        "They compare angles rather than magnitudes.\n"
        "Another section.\n"
    )
    kind, span = probe.nearest_heading_page_span(page, case, row)
    assert kind == "section"
    assert span == "Cosine Similarity\nThey compare angles rather than magnitudes."
    assert span in page
    assert probe.nearest_heading_page_span(
        "They compare angles rather than magnitudes.", case, row,
    ) == ("heading_unavailable", None)


def test_quote_pair_probe_limits_tokens_and_hides_scores_for_unavailable_model():
    class FakeTokenizer:
        def encode(self, *_args):
            return SimpleNamespace(ids=[1] * 385)

    verifier = SimpleNamespace(_nli=SimpleNamespace(_tokenizer=FakeTokenizer()))
    over = probe._quote_pair_probe(
        verifier, question="Authored question", statement="Authored statement",
        quote="private-source-sentinel",
    )
    assert over["reason"] == "model_token_limit"
    assert over["entailment"] is None

    class PassingTokenizer:
        def encode(self, *_args):
            return SimpleNamespace(ids=[1] * 25)

    model = SimpleNamespace(
        _nli=SimpleNamespace(
            _tokenizer=PassingTokenizer(),
            score=lambda *_args: NliScores(.01, .98, .01),
        ),
        _qa=SimpleNamespace(answer=lambda *_args: "answer"),
    )
    result = probe._quote_pair_probe(
        model, question="Authored question", statement="The answer is given.",
        quote="The answer is given in private-source-sentinel.",
    )
    assert result["reason"] == "quote_gate_pass"
    assert result["qa_span_present"] is True
    assert result["qa_span_in_claim"] is True
    assert "private-source-sentinel" not in probe.json.dumps(result)


def test_v2_contract_replay_uses_complete_issued_units_and_server_quote():
    row = _chunk(
        "Earlier fact.\n"
        "BLEU means Bilingual Evaluation Understudy; the metric has details.\n"
        "Later fact."
    )
    selection = "BLEU means Bilingual Evaluation Understudy"
    status, derived, count = probe._answer_contract_v2_claim(
        chunk=row, quote=selection,
        statement="BLEU stands for Bilingual Evaluation Understudy.",
        question="What does BLEU stand for?",
    )
    assert status == "server_derived"
    assert count == 1
    assert derived is not None
    assert derived.source == row
    assert derived.source_quote == (
        "BLEU means Bilingual Evaluation Understudy; the metric has details."
    )
    assert selection in derived.source_quote


def test_v2_contract_replay_refuses_ambiguous_and_overlong_unit_ranges():
    repeated = _chunk("Repeat.\nRepeat.")
    assert probe._answer_contract_v2_claim(
        chunk=repeated, quote="Repeat.", statement="A repeat exists.",
        question="What repeats?",
    ) == ("range_ambiguous", None, 0)

    many_lines = _chunk("\n".join(f"Fact {number}." for number in range(7)))
    status, derived, count = probe._answer_contract_v2_claim(
        chunk=many_lines, quote=many_lines.content, statement="Six facts exist.",
        question="How many facts exist?",
    )
    assert (status, derived, count) == ("range_over_limit", None, 7)


def test_v2_contract_replay_binds_adjacent_units_without_joining_snippets():
    row = _chunk(
        "Leading note.\r\n"
        "BLEU means Bilingual Evaluation Understudy.\r\n"
        "It compares n-grams with a reference.\r\n"
        "Trailing note."
    )
    selected = (
        "BLEU means Bilingual Evaluation Understudy.\r\n"
        "It compares n-grams with a reference."
    )
    status, derived, count = probe._answer_contract_v2_claim(
        chunk=row, quote=selected,
        statement="BLEU compares n-grams with a reference.",
        question="How does BLEU compare with a reference?",
    )
    assert status == "server_derived"
    assert count == 2
    assert derived is not None
    assert derived.source_quote == selected
    assert derived.source_quote in row.content


def test_v2_contract_replay_report_is_keyless_private_and_not_model_replay(monkeypatch):
    private = "private-source-sentinel "
    row = _chunk(private + "BLEU means Bilingual Evaluation Understudy.")

    class FakeVerifier:
        def evaluate(self, **kwargs):
            claim = kwargs["claims"][0]
            assert claim.source_quote == row.content
            return SimpleNamespace(reason_code="supported")

    monkeypatch.setattr(probe, "create_local_support_verifier", lambda _path: FakeVerifier())
    report = probe.evaluate_answer_contract_v2_in_memory(
        (row,), model_dir=Path("unused"), active_space_match=True,
    )
    rendered = probe.json.dumps(report)
    for secret in (private.strip(), row.document_title, str(row.chunk_id), str(row.document_id)):
        assert secret not in rendered
    assert report["provider_requests"] == 0
    assert report["database_writes"] == 0
    assert report["model_answer_replay_measured"] is False
    assert report["exact_quote_claim_pairs_owner_reviewed"] == 0
    assert report["results"][0]["contract_binding"] == "server_derived"
    assert report["results"][0]["positive"] == "supported"
    assert report["results"][0]["negative"] == "supported"


def test_v2_contract_replay_cli_reads_only_and_closes_database(monkeypatch, capsys):
    row = _chunk("BLEU means Bilingual Evaluation Understudy.")
    calls = []

    async def eligible(*, with_pages=False):
        calls.append(("read", with_pages))
        return (row,), True, {}, {}

    async def close():
        calls.append(("close", None))

    class FakeVerifier:
        def evaluate(self, **_kwargs):
            return SimpleNamespace(reason_code="supported")

    monkeypatch.setattr(probe, "_eligible_owner_chunks", eligible)
    monkeypatch.setattr(probe, "close_database", close)
    monkeypatch.setattr(probe, "get_settings", lambda: SimpleNamespace(
        rag_local_support_model_dir=Path("unused"),
    ))
    monkeypatch.setattr(probe, "create_local_support_verifier", lambda _path: FakeVerifier())
    monkeypatch.setattr(sys, "argv", [
        "evaluate_private_ask_support_v2.py", "--replay-answer-contract-v2",
    ])
    assert probe.main() == 0
    report = probe.json.loads(capsys.readouterr().out)
    assert calls == [("read", False), ("close", None)]
    assert report["provider_requests"] == 0
    assert report["database_writes"] == 0


def test_v2_contract_replay_cli_rejects_incompatible_modes_without_database(monkeypatch, capsys):
    async def no_read(**_kwargs):
        raise AssertionError("database should not be opened")

    monkeypatch.setattr(probe, "_eligible_owner_chunks", no_read)
    monkeypatch.setattr(sys, "argv", [
        "evaluate_private_ask_support_v2.py", "--owner-review-packet",
        "--replay-answer-contract-v2",
    ])
    assert probe.main() == 1
    assert capsys.readouterr().out.strip() == (
        '{"status":"unavailable","reason":"invalid_options"}'
    )
