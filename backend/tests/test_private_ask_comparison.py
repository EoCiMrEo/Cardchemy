"""Keyless guards for the opt-in private BLEU comparison runner."""

import asyncio
from contextlib import asynccontextmanager
from decimal import Decimal
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.ai.answering import AnswerClaim, GroundedAnswerOutput
from app.ai.embeddings import EmbeddingResponse
from app.ai.providers import (
    AIProviderError, ProviderAttemptTelemetry, ProviderResponse, ProviderUsage,
    current_attempt_scope,
)
from app.config import Settings
from app.ai.gemini_catalog import CATALOG_VERSION, SCHEMA_POLICY_VERSION
from app.ai.local_support import LOCAL_SUPPORT_POLICY_VERSION, NliScores
from app.models.knowledge import embedding_space_hash
from app.config import ASK_REQUIRED_RELEASE_POLICY_VERSION


SCRIPT = Path(__file__).resolve().parents[2] / "scripts/compare_private_ask_once.py"
spec = importlib.util.spec_from_file_location("private_ask_comparison", SCRIPT)
assert spec is not None and spec.loader is not None
comparison = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = comparison
spec.loader.exec_module(comparison)


def settings(**overrides) -> Settings:
    values = {
        "environment": "test",
        "database_url": "sqlite+aiosqlite:///:memory:",
        "secret_key": "test-only-secret-key-with-adequate-entropy-1234567890",
        "generation_source_encryption_key": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "rag_enabled": True,
        "rag_ask_enabled": True,
        "rag_ai_provider_enabled": True,
        "rag_embedding_provider_enabled": True,
        "rag_local_support_enabled": True,
        "rag_local_support_model_dir": Path("test-only-local-support-bundle"),
        "rag_ai_model": "gemini-3.6-flash",
        "rag_embedding_model": "gemini-embedding-001",
        "rag_ai_api_key": "not-used",
        "rag_embedding_api_key": "not-used",
        "rag_ai_quota_bucket": "test-answer",
        "rag_embedding_quota_bucket": "test-embedding",
    }
    return Settings(_env_file=None, **(values | overrides))


def authorize(monkeypatch) -> None:
    monkeypatch.setenv("RUN_PRIVATE_ASK_COMPARISON", "1")
    monkeypatch.setenv(
        "PRIVATE_ASK_COMPARISON_AUTHORIZED",
        "I_ACCEPT_PROVIDER_CHARGES_AND_PRIVATE_EVIDENCE",
    )


def test_private_live_guard_requires_three_independent_opt_ins(monkeypatch):
    monkeypatch.delenv("RUN_PRIVATE_ASK_COMPARISON", raising=False)
    monkeypatch.delenv("PRIVATE_ASK_COMPARISON_AUTHORIZED", raising=False)
    with pytest.raises(comparison.DiagnosticRefusal) as missing:
        comparison.require_live_envelope(settings(), execute=False)
    assert missing.value.code == "authorization_missing"
    authorize(monkeypatch)
    with pytest.raises(comparison.DiagnosticRefusal) as missing_execute:
        comparison.require_live_envelope(settings(), execute=False)
    assert missing_execute.value.code == "authorization_missing"


def test_private_main_without_opt_in_never_reads_configuration(monkeypatch, capsys):
    monkeypatch.delenv("RUN_PRIVATE_ASK_COMPARISON", raising=False)
    monkeypatch.delenv("PRIVATE_ASK_COMPARISON_AUTHORIZED", raising=False)
    monkeypatch.setattr(comparison, "get_settings", lambda: pytest.fail("No configuration read"))
    monkeypatch.setattr(
        sys, "argv",
        ["compare_private_ask_once.py", "--operator-latest-bleu", "--answer-from", "candidate"],
    )
    assert comparison.main() == 1
    assert '"reason":"authorization_missing"' in capsys.readouterr().out


def test_private_main_closes_database_in_same_event_loop(monkeypatch, capsys):
    authorize(monkeypatch)
    # Exercise historical orchestration with an inert injected envelope only.
    monkeypatch.setattr(comparison, "require_live_envelope", lambda configured, **_: configured)
    monkeypatch.setattr(
        sys, "argv",
        ["compare_private_ask_once.py", "--execute", "--operator-latest-bleu", "--answer-from", "candidate"],
    )
    monkeypatch.setattr(comparison, "get_settings", settings)
    observed = []

    async def select(*args, **kwargs):
        observed.append(("select", asyncio.get_running_loop()))
        return _case()

    async def execute(*args, **kwargs):
        observed.append(("execute", asyncio.get_running_loop()))
        return {"status": "completed", "answer_requests": 0}

    async def close():
        observed.append(("close", asyncio.get_running_loop()))

    monkeypatch.setattr(comparison, "select_case", select)
    monkeypatch.setattr(comparison, "execute_once", execute)
    monkeypatch.setattr(comparison, "close_database", close)
    assert comparison.main() == 0
    assert [step for step, _loop in observed] == ["select", "execute", "close"]
    assert len({id(loop) for _step, loop in observed}) == 1
    assert '"status":"completed"' in capsys.readouterr().out


def test_private_main_suppresses_close_errors_without_traceback(monkeypatch, capsys):
    authorize(monkeypatch)
    # Exercise historical orchestration with an inert injected envelope only.
    monkeypatch.setattr(comparison, "require_live_envelope", lambda configured, **_: configured)
    monkeypatch.setattr(
        sys, "argv",
        ["compare_private_ask_once.py", "--execute", "--operator-latest-bleu", "--answer-from", "candidate"],
    )
    monkeypatch.setattr(comparison, "get_settings", settings)

    async def select(*args, **kwargs):
        raise comparison.DiagnosticRefusal("job_unavailable")

    async def close():
        raise RuntimeError("private database detail")

    monkeypatch.setattr(comparison, "select_case", select)
    monkeypatch.setattr(comparison, "close_database", close)
    assert comparison.main() == 1
    captured = capsys.readouterr()
    assert '"reason":"job_unavailable"' in captured.out
    assert "private" not in captured.out and captured.err == ""


def test_private_answer_generation_is_retired_even_with_old_opt_ins(monkeypatch):
    authorize(monkeypatch)
    monkeypatch.setattr(comparison, "get_ai_provider", lambda *a, **kw: pytest.fail("No answer provider"))
    with pytest.raises(comparison.DiagnosticRefusal) as refusal:
        comparison.require_live_envelope(settings(), execute=True)
    assert refusal.value.code == "answer_generation_retired"


def test_private_live_cost_and_token_admission_is_before_provider_use(monkeypatch):
    assert comparison.admitted_cost(512, 12_000) < Decimal("0.04")
    for embedding, answer in ((513, 0), (0, 12_001)):
        with pytest.raises(comparison.DiagnosticRefusal):
            comparison.admitted_cost(embedding, answer)
    monkeypatch.setattr(comparison, "MAX_COST_USD", Decimal("0.001"))
    with pytest.raises(comparison.DiagnosticRefusal) as cost:
        comparison.admitted_cost(512, 12_000)
    assert cost.value.code == "cost_limit"


def test_private_case_snapshot_rejects_legacy_or_drifted_job():
    configured = settings()
    job = SimpleNamespace(
        status="completed", support_rejection_count=1,
        answer_policy_version=ASK_REQUIRED_RELEASE_POLICY_VERSION,
        support_policy_version=LOCAL_SUPPORT_POLICY_VERSION,
        retrieval_policy="hybrid_exact_v1", ai_provider="gemini",
        ai_base_url=comparison.ENDPOINT, ai_model=comparison.ANSWER_MODEL,
        ai_catalog_version=CATALOG_VERSION,
        ai_schema_policy_version=SCHEMA_POLICY_VERSION,
        embedding_space_hash=embedding_space_hash(configured.rag_embedding_space_identity),
    )
    comparison._check_snapshot(job, configured)
    for field, value in (
        ("answer_policy_version", "legacy_three_call_v1"),
        ("retrieval_policy", "other_retrieval"),
        ("ai_model", "gemini-3.5-flash"),
        ("embedding_space_hash", "b" * 64),
    ):
        changed = SimpleNamespace(**{**vars(job), field: value})
        with pytest.raises(comparison.DiagnosticRefusal) as rejected:
            comparison._check_snapshot(changed, configured)
        assert rejected.value.code == "snapshot_mismatch"


@pytest.mark.asyncio
async def test_private_live_database_boundary_sets_read_only_and_rolls_back():
    events = []

    class FakeSession:
        async def execute(self, statement):
            events.append(str(statement))

        async def rollback(self):
            events.append("ROLLBACK")

        async def commit(self):
            pytest.fail("The private comparison must not commit")

    @asynccontextmanager
    async def factory():
        events.append("OPEN")
        yield FakeSession()
        events.append("CLOSE")

    async with comparison.read_only_session(factory) as session:
        assert isinstance(session, FakeSession)
        events.append("SELECT")
    assert events == ["OPEN", "SET TRANSACTION READ ONLY", "SELECT", "ROLLBACK", "CLOSE"]


@pytest.mark.asyncio
async def test_latest_selector_filters_bleu_and_stand_before_limit(monkeypatch):
    @asynccontextmanager
    async def fake_session(_factory):
        class FakeSession:
            async def scalars(self, query):
                sql = str(query.compile(compile_kwargs={"literal_binds": True}))
                assert "%BLEU%" in sql and "%stand%" in sql
                assert "DISTINCT" in sql and "LIMIT 2" in sql
                return SimpleNamespace(all=lambda: [])

            async def scalar(self, query):
                pytest.fail("No latest job should be selected without a matching owner")

        yield FakeSession()

    monkeypatch.setattr(comparison, "read_only_session", fake_session)
    with pytest.raises(comparison.DiagnosticRefusal) as unavailable:
        await comparison.select_case(settings(), job_id=None, operator_latest=True)
    assert unavailable.value.code == "job_unavailable"


@pytest.mark.asyncio
async def test_latest_selector_scopes_final_job_to_single_matching_owner(monkeypatch):
    owner_id = uuid4()

    @asynccontextmanager
    async def fake_session(_factory):
        class FakeSession:
            async def scalars(self, query):
                return SimpleNamespace(all=lambda: [owner_id])

            async def scalar(self, query):
                sql = str(query.compile(compile_kwargs={"literal_binds": True}))
                assert "%BLEU%" in sql and "%stand%" in sql
                assert owner_id.hex in sql and "ORDER BY" in sql and "LIMIT 1" in sql
                return None

        yield FakeSession()

    monkeypatch.setattr(comparison, "read_only_session", fake_session)
    with pytest.raises(comparison.DiagnosticRefusal) as unavailable:
        await comparison.select_case(settings(), job_id=None, operator_latest=True)
    assert unavailable.value.code == "job_unavailable"


def test_private_main_rejects_ambiguous_owners_before_provider(monkeypatch, capsys):
    authorize(monkeypatch)
    # Exercise historical orchestration with an inert injected envelope only.
    monkeypatch.setattr(comparison, "require_live_envelope", lambda configured, **_: configured)
    monkeypatch.setattr(
        sys, "argv",
        ["compare_private_ask_once.py", "--execute", "--operator-latest-bleu", "--answer-from", "baseline"],
    )
    monkeypatch.setattr(comparison, "get_settings", settings)

    @asynccontextmanager
    async def fake_session(_factory):
        class FakeSession:
            async def scalars(self, query):
                return SimpleNamespace(all=lambda: [uuid4(), uuid4()])

            async def scalar(self, query):
                pytest.fail("An ambiguous latest job must not be selected")

        yield FakeSession()

    async def close():
        return None

    monkeypatch.setattr(comparison, "read_only_session", fake_session)
    monkeypatch.setattr(comparison, "close_database", close)
    monkeypatch.setattr(comparison, "execute_once", lambda *args, **kwargs: pytest.fail("No provider execution"))
    monkeypatch.setattr(comparison, "get_embedding_provider", lambda *args: pytest.fail("No embedding provider"))
    monkeypatch.setattr(comparison, "get_ai_provider", lambda *args, **kwargs: pytest.fail("No answer provider"))
    assert comparison.main() == 1
    captured = capsys.readouterr()
    assert '"reason":"owner_selection_ambiguous"' in captured.out
    assert "private" not in captured.out and captured.err == ""


class FakeEmbeddingProvider:
    def __init__(self, *, estimated=False):
        self.count = 0
        self.estimated = estimated

    async def embed_query(self, text):
        self.count += 1
        scope = current_attempt_scope(self)
        assert scope is not None
        scope.record_request("embedding_query", retry=False, waited_seconds=0)
        return EmbeddingResponse(
            vectors=((1.0,),),
            usage=ProviderUsage(input_tokens=8, output_tokens=0, estimated=self.estimated),
        )

    def telemetry_snapshot(self):
        return ProviderAttemptTelemetry(self.count, 0, 0.0, {"embedding_query": self.count})


@pytest.mark.asyncio
@pytest.mark.parametrize("reason,expected", [
    ("transport_protocol", "transport_protocol"),
    ("private provider content", "unclassified"),
])
async def test_private_live_failure_reports_only_allowlisted_provider_reason(
    monkeypatch, reason, expected,
):
    class FailingEmbeddingProvider(FakeEmbeddingProvider):
        async def embed_query(self, text):
            self.count += 1
            scope = current_attempt_scope(self)
            assert scope is not None
            scope.record_request("embedding_query", retry=False, waited_seconds=0)
            raise AIProviderError(
                "embedding_provider_unavailable", "private model response",
                retryable=True, reason_code=reason,
            )

    embedding = FailingEmbeddingProvider()
    monkeypatch.setattr(comparison, "create_local_support_verifier", lambda _: object())
    monkeypatch.setattr(comparison, "get_embedding_provider", lambda _: embedding)
    report = await comparison.execute_once(settings(), _case(), answer_from="candidate")
    assert report["status"] == "failed"
    assert report["reason"] == "embedding_provider_unavailable"
    assert report["provider_reason_code"] == expected
    assert report["embedding_requests"] == 1 and report["answer_requests"] == 0
    assert report["previous_attempt_cost_unknown"] is True
    assert "private" not in str(report)


@pytest.mark.parametrize(
    "raw_status,expected",
    [(500, 500), (502, 502), (503, 503), (504, 504), (429, None), ("503", None)],
)
def test_private_live_sdk_http_status_is_strictly_allowlisted(raw_status, expected):
    raw = RuntimeError("private provider response")
    raw.code = raw_status
    normalized = AIProviderError(
        "ai_provider_unavailable", "safe provider failure", retryable=True,
        reason_code="http_server_error",
    )
    normalized.__cause__ = raw
    assert comparison._safe_server_http_status(normalized) == expected
    normalized.reason_code = "http_rate_limited"
    assert comparison._safe_server_http_status(normalized) is None


@pytest.mark.asyncio
async def test_private_live_reports_server_status_without_sdk_exception_text(monkeypatch):
    class FailingEmbeddingProvider(FakeEmbeddingProvider):
        async def embed_query(self, text):
            self.count += 1
            scope = current_attempt_scope(self)
            assert scope is not None
            scope.record_request("embedding_query", retry=False, waited_seconds=0)
            raw = RuntimeError("private provider response")
            raw.status_code = 503
            raise AIProviderError(
                "embedding_provider_unavailable", "safe provider failure",
                retryable=True, reason_code="http_server_error",
            ) from raw

    monkeypatch.setattr(comparison, "create_local_support_verifier", lambda _: object())
    monkeypatch.setattr(comparison, "get_embedding_provider", lambda _: FailingEmbeddingProvider())
    report = await comparison.execute_once(settings(), _case(), answer_from="candidate")
    assert report["status"] == "failed"
    assert report["provider_reason_code"] == "http_server_error"
    assert report["provider_http_status"] == 503
    assert "private" not in str(report).casefold()


class FakeAnswerProvider:
    def __init__(self):
        self.count = 0

    async def generate_structured(self, **kwargs):
        self.count += 1
        scope = current_attempt_scope(self)
        assert scope is not None
        scope.record_request("rag_answer", retry=False, waited_seconds=0)
        return ProviderResponse(
            data=GroundedAnswerOutput(outcome="abstain", answer="", claims=[]),
            usage=ProviderUsage(input_tokens=100, output_tokens=5, estimated=False),
            finish_reason="STOP",
        )

    def telemetry_snapshot(self):
        return ProviderAttemptTelemetry(self.count, 0, 0.0, {"rag_answer": self.count})


def _case():
    from uuid import uuid4

    return comparison.SelectedCase(
        job_id=uuid4(), question="What does BLEU stand for?",
        user_id=uuid4(), subject_id=uuid4(), document_ids=(uuid4(),),
        corpus_revision=1, embedding_space_hash="a" * 64,
    )


def _retrieval(*, anchor):
    chunk = SimpleNamespace(
        content="private lecture phrase: Bilingual Evaluation Understudy" if anchor else "private unrelated lecture",
        vector_rank=1, lexical_rank=2,
    )
    return {
        key: SimpleNamespace(policy_id=key, chunks=(chunk,), insufficient=False)
        for key in ("baseline", "candidate")
    }


@pytest.mark.asyncio
async def test_private_live_stops_after_one_embedding_when_evidence_is_missing(monkeypatch):
    embedding = FakeEmbeddingProvider()
    answer = FakeAnswerProvider()
    monkeypatch.setattr(comparison, "create_local_support_verifier", lambda _: object())
    monkeypatch.setattr(comparison, "get_embedding_provider", lambda _: embedding)
    monkeypatch.setattr(comparison, "get_ai_provider", lambda *args, **kwargs: answer)

    async def retrieve(*args):
        return _retrieval(anchor=False)

    monkeypatch.setattr(comparison, "retrieve_comparison", retrieve)
    report = await comparison.execute_once(settings(), _case(), answer_from="candidate")
    assert report["status"] == "failed" and report["reason"] == "usable_evidence_missing"
    assert report["embedding_requests"] == 1 and report["answer_requests"] == 0
    assert answer.count == 0 and report["previous_attempt_cost_unknown"] is False
    assert "private" not in str(report)


@pytest.mark.asyncio
async def test_private_live_estimated_embedding_usage_keeps_cost_unknown_without_answer(monkeypatch):
    embedding = FakeEmbeddingProvider(estimated=True)
    answer = FakeAnswerProvider()
    monkeypatch.setattr(comparison, "create_local_support_verifier", lambda _: object())
    monkeypatch.setattr(comparison, "get_embedding_provider", lambda _: embedding)
    monkeypatch.setattr(comparison, "get_ai_provider", lambda *args, **kwargs: answer)

    async def retrieve(*args):
        return _retrieval(anchor=False)

    monkeypatch.setattr(comparison, "retrieve_comparison", retrieve)
    report = await comparison.execute_once(settings(), _case(), answer_from="candidate")
    assert report["status"] == "failed" and report["reason"] == "usable_evidence_missing"
    assert report["embedding_requests"] == 1 and report["answer_requests"] == 0
    assert report["usage_estimated"] is True
    assert report["previous_attempt_cost_unknown"] is True
    assert answer.count == 0


@pytest.mark.asyncio
async def test_private_live_answer_receipt_does_not_hide_estimated_embedding_usage(monkeypatch):
    class FailingAnswerProvider(FakeAnswerProvider):
        async def generate_structured(self, **kwargs):
            self.count += 1
            scope = current_attempt_scope(self)
            assert scope is not None
            scope.record_request("rag_answer", retry=False, waited_seconds=0)
            raise AIProviderError(
                "invalid_ai_output", "safe invalid output", retryable=False,
                reason_code="output_unfinished",
                usage=ProviderUsage(input_tokens=100, output_tokens=5, estimated=False),
                finish_reason="MAX_TOKENS",
            )

    embedding = FakeEmbeddingProvider(estimated=True)
    answer = FailingAnswerProvider()
    monkeypatch.setattr(comparison, "create_local_support_verifier", lambda _: object())
    monkeypatch.setattr(comparison, "get_embedding_provider", lambda _: embedding)
    monkeypatch.setattr(comparison, "get_ai_provider", lambda *args, **kwargs: answer)

    async def retrieve(*args):
        return _retrieval(anchor=True)

    async def reauthorize(*args):
        return None

    monkeypatch.setattr(comparison, "retrieve_comparison", retrieve)
    monkeypatch.setattr(comparison, "reauthorize_sources", reauthorize)
    monkeypatch.setattr(comparison, "render_answer_prompts", lambda **kwargs: ("system", "user"))
    report = await comparison.execute_once(settings(), _case(), answer_from="candidate")
    assert report["status"] == "failed" and report["reason"] == "invalid_ai_output"
    assert report["embedding_requests"] == report["answer_requests"] == 1
    assert report["finish_reason"] == "MAX_TOKENS"
    assert report["input_tokens"] == 108
    assert report["usage_estimated"] is True
    assert report["previous_attempt_cost_unknown"] is True


@pytest.mark.asyncio
async def test_private_live_summary_omits_question_evidence_and_model_text(monkeypatch):
    embedding = FakeEmbeddingProvider()
    answer = FakeAnswerProvider()
    monkeypatch.setattr(comparison, "create_local_support_verifier", lambda _: object())
    monkeypatch.setattr(comparison, "get_embedding_provider", lambda _: embedding)
    monkeypatch.setattr(comparison, "get_ai_provider", lambda *args, **kwargs: answer)

    async def retrieve(*args):
        return _retrieval(anchor=True)

    async def reauthorize(*args):
        return None

    monkeypatch.setattr(comparison, "retrieve_comparison", retrieve)
    monkeypatch.setattr(comparison, "reauthorize_sources", reauthorize)
    monkeypatch.setattr(
        comparison, "render_answer_prompts",
        lambda **kwargs: ("private system prompt", "private user prompt"),
    )
    report = await comparison.execute_once(settings(), _case(), answer_from="candidate")
    assert report["status"] == "completed" and report["outcome"] == "model_abstained"
    assert report["embedding_requests"] == report["answer_requests"] == 1
    assert report["previous_attempt_cost_unknown"] is False
    assert "private" not in str(report).casefold()
    assert "BLEU" not in str(report)


@pytest.mark.asyncio
async def test_private_live_rejects_overpacked_prompt_before_answer(monkeypatch):
    embedding = FakeEmbeddingProvider()
    answer = FakeAnswerProvider()
    monkeypatch.setattr(comparison, "create_local_support_verifier", lambda _: object())
    monkeypatch.setattr(comparison, "get_embedding_provider", lambda _: embedding)
    monkeypatch.setattr(comparison, "get_ai_provider", lambda *args, **kwargs: answer)

    async def retrieve(*args):
        return _retrieval(anchor=True)

    async def reauthorize(*args):
        return None

    monkeypatch.setattr(comparison, "retrieve_comparison", retrieve)
    monkeypatch.setattr(comparison, "reauthorize_sources", reauthorize)
    monkeypatch.setattr(comparison, "render_answer_prompts", lambda **kwargs: ("x" * 100_000, ""))
    report = await comparison.execute_once(settings(), _case(), answer_from="candidate")
    assert report["status"] == "failed" and report["reason"] == "answer_input_limit"
    assert report["embedding_requests"] == 1 and report["answer_requests"] == 0
    assert answer.count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("probe_fails", [False, True])
async def test_private_live_first_claim_probe_is_content_free_and_cannot_replace_verdict(
    monkeypatch, probe_fails,
):
    chunk_id = uuid4()
    quote = "In a synthetic lesson, BLEU stands for Bilingual Evaluation Understudy."
    statement = "BLEU stands for Bilingual Evaluation Understudy."

    class ClaimAnswerProvider(FakeAnswerProvider):
        async def generate_structured(self, **kwargs):
            self.count += 1
            scope = current_attempt_scope(self)
            assert scope is not None
            scope.record_request("rag_answer", retry=False, waited_seconds=0)
            return ProviderResponse(
                data=GroundedAnswerOutput(
                    outcome="answer", answer=statement,
                    claims=[AnswerClaim(
                        statement=statement, source_chunk_id=chunk_id, source_quote=quote,
                    )],
                ),
                usage=ProviderUsage(input_tokens=100, output_tokens=20, estimated=False),
                finish_reason="STOP",
            )

    class StubTokenizer:
        def encode(self, premise, hypothesis):
            assert premise == quote and hypothesis == statement
            if probe_fails:
                raise ValueError("private tokenizer failure")
            return SimpleNamespace(ids=range(27))

    class StubNli:
        _tokenizer = StubTokenizer()

        def score(self, premise, hypothesis):
            assert premise == quote and hypothesis == statement
            if probe_fails:
                raise ValueError("private NLI failure")
            return NliScores(contradiction=0.01234, entailment=0.32109, neutral=0.66657)

    class StubQa:
        def answer(self, question, context):
            assert question == "What does BLEU stand for?" and context == quote
            if probe_fails:
                raise ValueError("private QA failure")
            return "Bilingual Evaluation Understudy"

    class StubVerifier:
        _nli = StubNli()
        _qa = StubQa()

        def evaluate(self, **kwargs):
            assert kwargs["claims"][0].source_quote == quote
            return SimpleNamespace(supported=False, reason_code="entailment_rejected")

    async def retrieve(*args):
        chunk = SimpleNamespace(
            chunk_id=chunk_id, content=quote, vector_rank=1, lexical_rank=1,
        )
        return {
            label: SimpleNamespace(policy_id=label, chunks=(chunk,), insufficient=False)
            for label in ("baseline", "candidate")
        }

    async def reauthorize(*args):
        return None

    embedding = FakeEmbeddingProvider()
    answer = ClaimAnswerProvider()
    monkeypatch.setattr(comparison, "create_local_support_verifier", lambda _: StubVerifier())
    monkeypatch.setattr(comparison, "get_embedding_provider", lambda _: embedding)
    monkeypatch.setattr(comparison, "get_ai_provider", lambda *args, **kwargs: answer)
    monkeypatch.setattr(comparison, "retrieve_comparison", retrieve)
    monkeypatch.setattr(comparison, "reauthorize_sources", reauthorize)
    monkeypatch.setattr(comparison, "render_answer_prompts", lambda **kwargs: ("system", "user"))

    report = await comparison.execute_once(settings(), _case(), answer_from="baseline")
    assert report["status"] == "completed"
    assert report["outcome"] == "support_rejected"
    assert report["support_reason"] == "entailment_rejected"
    assert report["embedding_requests"] == report["answer_requests"] == 1
    probe = report["first_claim_probe"]
    assert probe == {
        "expected_expansion_in_claim": True,
        "expected_expansion_in_quote": True,
        "bleu_in_claim": True,
        "bleu_in_quote": True,
        "nli_token_count": None if probe_fails else 27,
        "nli_contradiction": None if probe_fails else 0.012,
        "nli_entailment": None if probe_fails else 0.321,
        "nli_neutral": None if probe_fails else 0.667,
        "qa_span_present": None if probe_fails else True,
    }
    assert "private" not in str(report).casefold()
    assert quote not in str(report) and statement not in str(report)
