"""Synthetic-only producer tests; no operator settings, real DB or quota."""
from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import evaluate_private_source_display as probe
from app.services.knowledge_retrieval import (
    KnowledgeRetrievalResult, RetrievedKnowledgeChunk,
    SOURCE_SUFFICIENCY_RETRIEVAL_POLICY,
)


def test_runtime_fingerprint_includes_structural_helper(monkeypatch):
    read_bytes = Path.read_bytes
    before = probe.runtime_fingerprint()
    touched = []

    def changed_bytes(path):
        data = read_bytes(path)
        if path.name == "source_structure.py":
            touched.append(path)
            return data + b"\n# synthetic candidate change\n"
        return data

    monkeypatch.setattr(Path, "read_bytes", changed_bytes)
    assert probe.runtime_fingerprint() != before
    assert len(touched) == 1


def roster(question="What does BLEU stand for?", history=()):
    scope = probe.Scope(uuid4(), uuid4(), (), 4, "a" * 64)
    case = probe.Case("D01", question, uuid4(), 22, True, history)
    cases = (case,)
    return probe.FrozenRoster(cases, scope, probe.roster_fingerprint(cases, scope), probe.runtime_fingerprint())


def envelope(frozen, **overrides):
    return replace(probe.Envelope("unit-test-approval-12345", frozen.roster_sha256, frozen.runtime_sha256), **overrides)


def chunk(frozen, content="BLEU means Bilingual Evaluation Understudy.", **overrides):
    values = dict(chunk_id=uuid4(), document_id=frozen.cases[0].gold_document_id,
        document_title="Synthetic source", content_revision_id=uuid4(), index_revision_id=uuid4(),
        page_number=22, section=None, content=content, token_count=10,
        embedding_space_hash=frozen.scope.space_hash, corpus_revision=4,
        vector_similarity=.95, lexical_score=.5, vector_rank=1, lexical_rank=1, fusion_score=.032)
    values.update(overrides)
    return RetrievedKnowledgeChunk(**values)


class Reader:
    def __init__(self, frozen, chunks=(), page_text=None):
        self.frozen, self.chunks, self.page_text = frozen, chunks, page_text
        self.queries, self.current_reads = [], 0
    async def authorize(self, query):
        self.queries.append(("authorize", query))
        expected = self.frozen.scope
        return SimpleNamespace(principal_id=expected.principal_id, subject_id=expected.subject_id,
            document_ids=tuple(sorted(expected.document_ids, key=str)), corpus_revision=expected.corpus_revision,
            embedding_space_hash=expected.space_hash)
    async def retrieve(self, query, vector):
        self.queries.append(("retrieve", query))
        return KnowledgeRetrievalResult(SOURCE_SUFFICIENCY_RETRIEVAL_POLICY.policy_id, self.frozen.scope.subject_id,
            self.frozen.scope.corpus_revision, self.frozen.scope.space_hash, tuple(self.chunks))
    async def neighbors(self, query, anchors, radius, max_chunks, max_pages, max_tokens):
        self.queries.append(("neighbors", radius))
        return ()
    async def page_units(self, query, chunk_ids, max_pages, max_tokens):
        self.queries.append(("page_units", max_pages, max_tokens))
        selected = [source for source in self.chunks if source.chunk_id in chunk_ids]
        return {source.chunk_id: self.page_text if self.page_text is not None else source.content
                for source in selected}
    async def current_pages(self, sources, query):
        self.current_reads += 1
        return {source.chunk_id: self.page_text if self.page_text is not None else source.content for source in sources}


class Provider:
    def __init__(self, **overrides):
        self.questions, self.closed, self.overrides = [], False, overrides
    async def embed_current(self, question):
        self.questions.append(question)
        return replace(probe.EmbeddingAttempt((1.0,) + (0.0,) * 1535, 1, 0, 10), **self.overrides)
    def attempts(self):
        return len(self.questions), 0
    async def close(self):
        self.closed = True


def approve(monkeypatch, proposed):
    monkeypatch.setenv(probe.AUTHORIZATION_ENV, proposed.digest())
    return proposed.digest()


@pytest.fixture(autouse=True)
def isolated_approval_marker(monkeypatch, tmp_path):
    # Marker injection exists only in test monkeypatching, not as a CLI option.
    monkeypatch.setattr(probe, "approval_marker", lambda _: tmp_path/"once")


def test_cli_default_is_provider_and_database_free():
    script = Path(probe.__file__)
    code = ("import runpy,sys; sys.argv=['probe']; "
            f"runpy.run_path({str(script)!r},run_name='__main__')")
    completed = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    result = json.loads(completed.stdout)
    assert result["provider_requests"] == result["database_reads"] == result["database_writes"] == 0
    assert result["status"] == "design_preflight_unexecuted"
    assert not result["release_gate_passed"]


def test_import_and_preflight_do_not_import_application(monkeypatch, capsys):
    forbidden = []
    import builtins
    original = builtins.__import__
    def guarded(name, *args, **kwargs):
        if name == "app" or name.startswith("app."):
            forbidden.append(name)
            raise AssertionError("preflight attempted application import")
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", guarded)
    monkeypatch.setattr(sys, "argv", ["probe"])
    assert probe.main() == 0
    assert not forbidden
    assert json.loads(capsys.readouterr().out)["live_binding_and_fresh_approval_required"]


@pytest.mark.parametrize("mutation", [
    lambda frozen: replace(frozen, cases=(replace(frozen.cases[0], owner_reviewed_gold=False),)),
    lambda frozen: replace(frozen, roster_sha256="b"*64),
    lambda frozen: replace(frozen, runtime_sha256="b"*64),
])
def test_unreviewed_or_changed_roster_refused(mutation):
    with pytest.raises(probe.Refusal):
        probe.validate_roster(mutation(roster()))


@pytest.mark.parametrize("values", [{"endpoint": "https://unapproved.test"}, {"max_requests": 26},
    {"max_call_seconds": 31}, {"max_total_seconds": 901}, {"max_input_tokens": 8193},
    {"input_price_guard": Decimal("0.10")}, {"task": "RETRIEVAL_QUERY"}])
def test_envelope_has_numeric_and_remote_bounds(values):
    frozen = roster()
    with pytest.raises(probe.Refusal, match="envelope_invalid"):
        probe.validate_envelope(frozen, envelope(frozen, **values))


@pytest.mark.asyncio
async def test_missing_approval_precedes_factory_and_scope_reads(tmp_path, monkeypatch):
    monkeypatch.delenv(probe.AUTHORIZATION_ENV, raising=False)
    frozen = roster()
    def forbidden(*args):
        raise AssertionError("factory constructed without fresh approval")
    report = await probe.run_live(roster=frozen, envelope=envelope(frozen), approval_token=None,
        marker=tmp_path/"once", reader_factory=forbidden, provider_factory=forbidden)
    assert report["failure_code"] == "approval_missing"
    assert report["provider_requests"] == 0


@pytest.mark.asyncio
async def test_one_shot_marker_blocks_reexecution(tmp_path, monkeypatch):
    frozen = roster()
    proposed = envelope(frozen)
    token = approve(monkeypatch, proposed)
    marker = tmp_path/"once"
    probe.consume_approval(frozen, proposed, marker, token)
    def forbidden(*args):
        raise AssertionError("spent approval constructed factory")
    report = await probe.run_live(roster=frozen, envelope=proposed, approval_token=token,
        marker=marker, reader_factory=forbidden, provider_factory=forbidden)
    assert report["failure_code"] == "approval_consumed"


def test_different_output_marker_cannot_replay_same_approval(tmp_path, monkeypatch):
    frozen = roster()
    proposed = envelope(frozen)
    token = approve(monkeypatch, proposed)
    with pytest.raises(probe.Refusal, match="envelope_invalid"):
        probe.consume_approval(frozen, proposed, tmp_path/"different", token)


@pytest.mark.asyncio
async def test_exact_current_question_only_and_page_open_stays_pending(tmp_path, monkeypatch):
    frozen = roster("What does it stand for?", (("user", "Where is BLEU discussed?"),))
    proposed = envelope(frozen)
    token = approve(monkeypatch, proposed)
    provider = Provider()
    reader = Reader(frozen, (chunk(frozen),))
    report = await probe.run_live(roster=frozen, envelope=proposed, approval_token=token,
        marker=tmp_path/"once", reader_factory=lambda: reader, provider_factory=lambda _: provider)
    assert provider.questions == ["What does it stand for?"]
    assert ("retrieve", "What does BLEU stand for?") in reader.queries
    assert reader.current_reads == 2
    row = report["observations"][0]
    assert row["result_kind"] == "related_knowledge"
    assert row["gold_page_rank"] == 1
    assert row["embedding_calls"] == 1 and row["answer_calls"] == row["automatic_retries"] == 0
    assert not row["owner_reviewed_windows"]
    assert row["windows"][0]["canonical_page_aligned"]
    assert not row["windows"][0]["opened_current_page"]
    assert not row["windows"][0]["question_relevant"]
    assert provider.closed and not report["release_gate_passed"]
    assert report["estimated_cost_usd"] == "0.000002"
    serialized = json.dumps(probe.aggregate(report))
    assert "BLEU" not in serialized and "Bilingual" not in serialized


@pytest.mark.asyncio
async def test_canonical_page_window_reports_exact_page_slice_without_chunk_claim(tmp_path, monkeypatch):
    frozen = roster()
    proposed = envelope(frozen)
    page = "BLEU\nstands for Bilingual Evaluation Understudy."
    source = chunk(frozen, "stands for Bilingual Evaluation Understudy.", section="BLEU")
    reader = Reader(frozen, (source,), page_text=page)
    report = await probe.run_live(
        roster=frozen, envelope=proposed,
        approval_token=approve(monkeypatch, proposed), marker=tmp_path/"once",
        reader_factory=lambda: reader, provider_factory=lambda _: Provider(),
    )
    assert report["status"] == "observed_pending_window_review_and_page_open"
    window = report["observations"][0]["windows"][0]
    assert window["source_kind"] == "canonical_page"
    assert window["exact_source_slice"] and not window["exact_chunk_slice"]
    assert window["canonical_page_aligned"] and window["current_authorized"]
    assert not window["opened_current_page"] and not window["question_relevant"]
    private = report["private_review"][0]["displayed_windows"][0]
    assert private["quote"] == page
    assert private["reference_start"] == 0 and private["reference_end"] == len(page)
    assert reader.current_reads == 2
    assert any(query[0] == "page_units" for query in reader.queries)


@pytest.mark.asyncio
async def test_canonical_page_drift_before_measurement_discards_bundle(tmp_path, monkeypatch):
    frozen = roster()
    proposed = envelope(frozen)
    page = "BLEU\nstands for Bilingual Evaluation Understudy."
    source = chunk(frozen, "stands for Bilingual Evaluation Understudy.", section="BLEU")
    class PageDriftReader(Reader):
        async def current_pages(self, sources, query):
            current = await super().current_pages(sources, query)
            return {key: value.replace("BLEU", "ROUGE") for key, value in current.items()}
    reader = PageDriftReader(frozen, (source,), page_text=page)
    report = await probe.run_live(
        roster=frozen, envelope=proposed,
        approval_token=approve(monkeypatch, proposed), marker=tmp_path/"once",
        reader_factory=lambda: reader, provider_factory=lambda _: Provider(),
    )
    assert report["failure_code"] == "source_changed"
    assert "observations" not in report and "private_review" not in report


@pytest.mark.asyncio
async def test_ambiguous_followup_calls_no_provider(tmp_path, monkeypatch):
    frozen = roster("What does it stand for?", (("user", "Compare BLEU and BERT."),))
    proposed = envelope(frozen)
    provider, reader = Provider(), Reader(frozen)
    report = await probe.run_live(roster=frozen, envelope=proposed, approval_token=approve(monkeypatch, proposed),
        marker=tmp_path/"once", reader_factory=lambda: reader, provider_factory=lambda _: provider)
    row = report["observations"][0]
    assert row["result_kind"] == "no_match" and not row["windows"]
    assert not provider.questions and row["embedding_calls"] == 0


@pytest.mark.asyncio
async def test_mid_read_source_drift_discards_private_bundle(tmp_path, monkeypatch):
    frozen = roster()
    proposed = envelope(frozen)
    provider = Provider()
    class DriftingReader(Reader):
        async def current_pages(self, sources, query):
            result = await super().current_pages(sources, query)
            if self.current_reads == 2:
                raise probe.Refusal("source_changed")
            return result
    reader = DriftingReader(frozen, (chunk(frozen),))
    report = await probe.run_live(roster=frozen, envelope=proposed, approval_token=approve(monkeypatch, proposed),
        marker=tmp_path/"once", reader_factory=lambda: reader, provider_factory=lambda _: provider)
    assert report["failure_code"] == "source_changed"
    assert "observations" not in report and "private_review" not in report
    assert report["previous_attempt_cost"] == "unknown"


@pytest.mark.asyncio
async def test_physical_retry_or_second_attempt_is_refused(tmp_path, monkeypatch):
    frozen = roster()
    proposed = envelope(frozen)
    provider = Provider(requests=2, retries=1)
    report = await probe.run_live(roster=frozen, envelope=proposed, approval_token=approve(monkeypatch, proposed),
        marker=tmp_path/"once", reader_factory=lambda: Reader(frozen), provider_factory=lambda _: provider)
    assert report["failure_code"] == "provider_contract_invalid"
    assert len(provider.questions) == 1


@pytest.mark.asyncio
async def test_token_preflight_precedes_factories(tmp_path, monkeypatch):
    frozen = roster()
    proposed = envelope(frozen, max_input_tokens=1)
    def forbidden(*args):
        raise AssertionError("over-budget factory construction")
    report = await probe.run_live(roster=frozen, envelope=proposed, approval_token=approve(monkeypatch, proposed),
        marker=tmp_path/"once", reader_factory=forbidden, provider_factory=forbidden)
    assert report["failure_code"] == "token_budget_exceeded"


def test_private_output_escapes_text_and_refuses_repository_path(tmp_path):
    report = {"private_review": [{"case_id": "D01", "question": "<script>alert(1)</script>",
        "history": [["user", "Where is <BERT> discussed?"]],
        "displayed_windows": [{"quote": "<img src=x onerror=alert(2)>", "page_number": 1,
                               "document_title": "<Synthetic lecture>"}]}]}
    observations, packet = probe.write_private_packet(report, tmp_path/"review")
    html = packet.read_text(encoding="utf-8")
    assert "<script>" not in html and "<img" not in html
    assert "&lt;script&gt;" in html and "default-src" in html
    assert "Previous user turn:" in html and "Where is &lt;BERT&gt; discussed?" in html
    assert "&lt;Synthetic lecture&gt;" in html
    assert observations.exists()
    with pytest.raises(probe.Refusal, match="private_output_invalid"):
        probe.write_private_packet(report, probe.ROOT/"private-probe")


def test_canonical_read_adapter_is_explicit_and_read_only():
    source = Path(probe.__file__).read_text(encoding="utf-8")
    assert "REPEATABLE READ READ ONLY" in source
    assert "read_current_sources" in source and "KnowledgeRetriever.authorize" in source
    assert "get_settings(" not in source and "_env_file=None" in source
    assert "config.get_settings = lambda: settings" in source
    assert "answering" not in source and "local_support" not in source
    assert "await db.commit()" not in source and "db.add(" not in source


def native_settings(**overrides):
    from app.config import Settings
    values = dict(environment="test", database_url="sqlite+aiosqlite:///:memory:",
        secret_key="test-only-secret-key-with-adequate-entropy-1234567890",
        generation_source_encryption_key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        rag_enabled=True, rag_embedding_provider_enabled=True,
        rag_embedding_api_key="synthetic-test-key", rag_embedding_quota_bucket="unit-test-project",
        rag_embedding_provider_max_retries=3)
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.mark.asyncio
async def test_native_sdk_sends_exactly_one_current_question_with_no_history_or_lecture():
    requests = []
    current = "What does it stand for?"
    def handler(request):
        requests.append(request)
        assert request.method == "POST"
        assert str(request.url) == probe.ENDPOINT + "/v1beta/models/gemini-embedding-001:batchEmbedContents"
        body = json.loads(request.content)
        assert len(body["requests"]) == 1
        item = body["requests"][0]
        assert item["content"]["parts"] == [{"text": current}]
        assert item["taskType"] == "QUESTION_ANSWERING"
        assert item["outputDimensionality"] == 1536
        return httpx.Response(200, json={"embeddings": [{"values": [1.0] + [0.0]*1535}]})
    frozen = roster()
    proposed = envelope(frozen, max_requests=1)
    original = native_settings()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        native = probe.NativeGeminiQueryProvider(original, proposed, http_client=client)
        try:
            result = await native.embed_current(current)
            assert result.requests == 1 and result.retries == 0 and len(result.vector) == 1536
            assert native.attempts() == (1, 0)
            assert native.provider.profile.max_retries == 0
            assert native.provider.profile.requests_per_minute == original.rag_embedding_requests_per_minute
            assert native.provider.profile.input_tokens_per_minute == original.rag_embedding_input_tokens_per_minute
            with pytest.raises(probe.Refusal, match="provider_contract_invalid"):
                await native.embed_current(current)
            assert len(requests) == 1
        finally:
            await native.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [400, 429, 500])
async def test_native_transport_errors_never_retry(status):
    from app.ai.providers import AIProviderError
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(status, json={"error": {"code": status, "message": "synthetic failure"}})
    frozen = roster()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        native = probe.NativeGeminiQueryProvider(native_settings(), envelope(frozen), http_client=client)
        try:
            with pytest.raises(AIProviderError):
                await native.embed_current("What does BLEU mean?")
            assert len(requests) == 1 and native.attempts() == (1, 0)
        finally:
            await native.close()


@pytest.mark.parametrize("overrides", [{"rag_embedding_model": "gemini-embedding-2"},
    {"rag_embedding_provider_enabled": False}, {"rag_embedding_api_key": None}])
def test_native_incompatible_or_keyless_profile_constructs_no_client(monkeypatch, overrides):
    from google import genai
    def forbidden(*args, **kwargs):
        raise AssertionError("incompatible profile constructed client")
    monkeypatch.setattr(genai, "Client", forbidden)
    frozen = roster()
    with pytest.raises(probe.Refusal):
        probe.NativeGeminiQueryProvider(native_settings().model_copy(update=overrides), envelope(frozen))


def private_inputs(tmp_path, frozen, proposed, profile):
    from dataclasses import asdict
    files = [tmp_path/"roster.json", tmp_path/"envelope.json", tmp_path/"profile.json"]
    payloads = [{"schema": "source_only_display_roster_v1", "frozen": True,
        "scope": asdict(frozen.scope), "cases": [asdict(case) for case in frozen.cases],
        "roster_sha256": frozen.roster_sha256, "runtime_sha256": frozen.runtime_sha256},
        asdict(proposed), profile]
    for path, payload in zip(files, payloads, strict=True):
        path.write_text(json.dumps(payload, default=str), encoding="utf-8")
    return files


def nonsecret_profile():
    settings = native_settings()
    # Round-trip through JSON exactly as an explicit owner-private profile file.
    return json.loads(json.dumps({field: getattr(settings, field) for field in probe.PROFILE_FIELDS}, default=str))


def test_private_input_preflight_binds_profile_and_never_creates_db_or_client(tmp_path, monkeypatch, capsys):
    frozen = roster()
    profile = nonsecret_profile()
    proposed = envelope(frozen, profile_sha256=probe._digest(profile))
    paths = private_inputs(tmp_path, frozen, proposed, profile)
    def forbidden(*args):
        raise AssertionError("preflight constructed settings/database")
    monkeypatch.setattr(probe, "explicit_bindings", forbidden)
    monkeypatch.setattr(sys, "argv", ["probe", "--roster", str(paths[0]),
        "--envelope", str(paths[1]), "--profile", str(paths[2])])
    assert probe.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "frozen_preflight_ready"
    assert result["envelope_sha256"] == proposed.digest()
    assert result["provider_requests"] == result["database_reads"] == 0
    assert frozen.cases[0].question not in json.dumps(result)


def test_cli_execute_without_fresh_approval_constructs_no_bindings(tmp_path, monkeypatch, capsys):
    frozen = roster()
    profile = nonsecret_profile()
    proposed = envelope(frozen, profile_sha256=probe._digest(profile))
    paths = private_inputs(tmp_path, frozen, proposed, profile)
    monkeypatch.delenv(probe.AUTHORIZATION_ENV, raising=False)
    def forbidden(*args):
        raise AssertionError("CLI constructed bindings before approval")
    monkeypatch.setattr(probe, "explicit_bindings", forbidden)
    monkeypatch.setattr(sys, "argv", ["probe", "--execute", "--roster", str(paths[0]),
        "--envelope", str(paths[1]), "--profile", str(paths[2]),
        "--output-directory", str(tmp_path/"new-output")])
    assert probe.main() == 1
    result = json.loads(capsys.readouterr().out)
    assert result["failure_code"] == "approval_missing" and result["provider_requests"] == 0
    assert not (tmp_path/"once").exists()


def test_profile_change_or_negative_gold_prevents_cli_execution(tmp_path):
    frozen = roster()
    profile = nonsecret_profile()
    proposed = envelope(frozen, profile_sha256=probe._digest(profile))
    paths = private_inputs(tmp_path, frozen, proposed, profile)
    changed = dict(profile, rag_embedding_model="gemini-embedding-2")
    paths[2].write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(probe.Refusal, match="profile_incompatible"):
        probe.load_frozen_inputs(*paths)
    paths = private_inputs(tmp_path, frozen, proposed, profile)
    payload = json.loads(paths[0].read_text())
    payload["cases"][0]["owner_reviewed_gold"] = False
    paths[0].write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(probe.Refusal, match="roster_not_frozen"):
        probe.load_frozen_inputs(*paths)
