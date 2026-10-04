"""Keyless contracts for the one-shot published-roster query-vector packet."""
from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_private_query_vectors as builder
import diagnose_source_navigation as consumer

from app.config import Settings
from app.models.knowledge import embedding_space_hash


def settings(**overrides):
    values = dict(
        environment="test", database_url="sqlite+aiosqlite:///:memory:",
        secret_key="test-only-secret-key-with-adequate-entropy-1234567890",
        generation_source_encryption_key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        rag_enabled=True, rag_embedding_provider_enabled=True,
        rag_embedding_api_key="synthetic-test-key", rag_embedding_quota_bucket="test-project",
    )
    values.update(overrides)
    return Settings(_env_file=None, **values)


def cases():
    return tuple(consumer.Case(
        case_id=f"D{index:02}", group="direct", question=f"What is concept {index}?",
        prior_question="", expected_pdf_sha256="a" * 64, expected_page=index,
        gold_window="",
    ) for index in range(1, 12))


def scope(current):
    return consumer.Scope(uuid4(), uuid4(), 4,
                          embedding_space_hash(current.rag_embedding_space_identity))


def private_input(monkeypatch, tmp_path):
    monkeypatch.setattr(builder, "PRIVATE_MOUNT", tmp_path)
    monkeypatch.setattr(consumer, "PRIVATE_MOUNT", tmp_path)
    path = tmp_path / "published-roster.json"
    path.write_text(json.dumps({"schema": consumer.ROSTER_SCHEMA,
                                "cases": [asdict(case) for case in cases()]}), encoding="utf-8")
    if sys.platform != "win32":
        path.chmod(0o600)
    return path, sha256(path.read_bytes()).hexdigest()


def test_default_cli_never_reads_roster_settings_or_provider():
    result = subprocess.run([sys.executable, str(Path(builder.__file__))],
                            capture_output=True, text=True, check=True)
    report = json.loads(result.stdout)
    assert report["status"] == "preflight_unexecuted"
    assert report["provider_requests"] == report["database_reads"] == report["database_writes"] == 0
    assert report["max_provider_requests"] == 11
    assert report["max_cost_usd"] == "0.001"
    assert result.stderr == ""


def test_fresh_matching_uuid4_flag_and_environment_required(monkeypatch):
    token = str(uuid4())
    monkeypatch.delenv(builder.APPROVAL_ENV, raising=False)
    with pytest.raises(builder.Refusal, match="approval_missing"):
        builder.require_approval(token)
    monkeypatch.setenv(builder.APPROVAL_ENV, token)
    assert builder.require_approval(token).version == 4
    with pytest.raises(builder.Refusal, match="approval_missing"):
        builder.require_approval(str(uuid4()))
    with pytest.raises(builder.Refusal, match="approval_missing"):
        builder.require_approval("not-a-token")


def test_one_shot_receipt_is_exclusive_and_private(monkeypatch, tmp_path):
    private_input(monkeypatch, tmp_path)
    token = uuid4()
    builder.consume_approval(token)
    receipts = list(tmp_path.glob(".query-vector-approval-*.used"))
    assert len(receipts) == 1 and token.hex not in receipts[0].name
    with pytest.raises(builder.Refusal, match="approval_used"):
        builder.consume_approval(token)
    if sys.platform != "win32":
        assert receipts[0].stat().st_mode & 0o077 == 0


@pytest.mark.parametrize("overrides", [
    {"rag_embedding_provider_enabled": False},
    {"rag_embedding_model": "gemini-embedding-2"},
    {"rag_embedding_base_url": "https://other.example"},
    {"rag_embedding_format_version": "gemini2_qa_section_v1"},
])
def test_active_embedding_profile_must_match_scope(overrides):
    current = settings()
    wrong = current.model_copy(update=overrides)
    with pytest.raises(builder.Refusal, match="profile_incompatible"):
        builder.bounded_profile(wrong, scope(current), cases())


def test_budget_and_bounded_settings_preserve_embedding_space():
    current = settings()
    bounded, tokens = builder.bounded_profile(current, scope(current), cases())
    assert 0 < tokens <= 512
    assert bounded.rag_embedding_space_identity == current.rag_embedding_space_identity
    assert bounded.rag_embedding_provider_max_retries == 0
    assert bounded.rag_embedding_provider_timeout_seconds == 30
    assert bounded.rag_embedding_batch_size == 1
    assert bounded.rag_embedding_input_cost_per_million_usd == builder.CONSERVATIVE_INPUT_PRICE
    oversized = tuple(consumer.Case(**{**asdict(case), "question": "many " * 400})
                      for case in cases())
    with pytest.raises(builder.Refusal, match="input_budget_invalid"):
        builder.bounded_profile(current, scope(current), oversized)


@pytest.mark.asyncio
async def test_mock_native_sdk_sends_only_current_question_and_packet_passes_consumer(monkeypatch, tmp_path):
    roster_path, roster_digest = private_input(monkeypatch, tmp_path)
    # Keep the mock fast while exercising the unchanged production admission path.
    current = settings(rag_embedding_requests_per_minute=1000)
    scoped = scope(current)
    bounded, _tokens = builder.bounded_profile(current, scoped, cases())
    requests = []

    def handler(request):
        requests.append(request)
        assert request.method == "POST"
        assert request.url.host == "generativelanguage.googleapis.com"
        body = json.loads(request.content)
        assert len(body["requests"]) == 1
        row = body["requests"][0]
        assert row["taskType"] == "QUESTION_ANSWERING"
        assert row["outputDimensionality"] == 1536
        assert row["content"]["parts"] == [{"text": cases()[len(requests) - 1].question}]
        return httpx.Response(200, json={
            "embeddings": [{"values": [1.0] + [0.0] * 1535}],
        })

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
        def factory(_settings):
            assert _settings is not current
            assert _settings == bounded
            return builder.make_native_query_provider(_settings, http_client=transport)

        output = tmp_path / "vectors.json"
        report = await builder.build_packet(cases(), roster_digest, roster_path, output,
                                            scoped, uuid4(), current, provider_factory=factory)
    assert report["status"] == "completed_private_packet", (report, len(requests))
    assert report["provider_requests"] == len(requests) == 11
    assert report["retry_count"] == report["database_reads"] == report["database_writes"] == 0
    assert report["packet_sha256"] == sha256(output.read_bytes()).hexdigest()
    loaded, digest = consumer.load_vectors(output, report["packet_sha256"],
                                           roster_sha256=roster_digest, cases=cases(), scope=scoped)
    assert digest == report["packet_sha256"] and len(loaded) == 11
    assert not any(case.question in json.dumps(report) for case in cases())
    if sys.platform != "win32":
        assert output.stat().st_mode & 0o077 == 0


@pytest.mark.asyncio
async def test_provider_failure_stops_without_packet_or_retry(monkeypatch, tmp_path):
    roster_path, roster_digest = private_input(monkeypatch, tmp_path)
    current = settings()
    scoped = scope(current)
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 3:
            return httpx.Response(429, json={
                "error": {"code": 429, "message": "private response must not print"},
            })
        return httpx.Response(200, json={
            "embeddings": [{"values": [1.0] + [0.0] * 1535}],
        })

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
        def factory(bounded):
            return builder.make_native_query_provider(bounded, http_client=transport)

        output = tmp_path / "failed-vectors.json"
        approval = uuid4()
        report = await builder.build_packet(cases(), roster_digest, roster_path, output,
                                            scoped, approval, current, provider_factory=factory)
    assert report["status"] == "refused_or_failed"
    assert report["provider_requests"] == len(calls) == 3
    assert report["retry_count"] == 0
    assert report["previous_attempt_cost"] == "unknown"
    assert "private response" not in json.dumps(report)
    assert not output.exists()
    with pytest.raises(builder.Refusal, match="approval_used"):
        builder.consume_approval(approval)


@pytest.mark.asyncio
async def test_output_exists_refuses_before_approval_and_provider(monkeypatch, tmp_path):
    roster_path, roster_digest = private_input(monkeypatch, tmp_path)
    output = tmp_path / "already-there.json"
    output.write_text("private existing data", encoding="utf-8")
    approval = uuid4()

    def forbidden(_settings):
        pytest.fail("provider must not be constructed")

    with pytest.raises(builder.Refusal, match="output_exists"):
        await builder.build_packet(cases(), roster_digest, roster_path, output,
                                   scope(settings()), approval, settings(),
                                   provider_factory=forbidden)
    builder.consume_approval(approval)
    assert output.read_text(encoding="utf-8") == "private existing data"


def test_execute_without_approval_never_opens_settings_or_roster():
    script = Path(builder.__file__)
    result = subprocess.run([sys.executable, str(script), "--execute"],
                            capture_output=True, text=True)
    assert result.returncode == 1
    assert json.loads(result.stdout)["failure_code"] == "approval_missing"
    assert result.stderr == ""


def test_execute_and_preflight_flags_cannot_be_combined(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", [str(builder.__file__), "--execute", "--preflight-inputs"])
    assert builder.main() == 1
    assert json.loads(capsys.readouterr().out)["failure_code"] == "invalid_arguments"


def test_input_preflight_checks_active_profile_without_provider_or_approval(monkeypatch, tmp_path, capsys):
    from app import config

    roster_path, roster_digest = private_input(monkeypatch, tmp_path)
    current = settings()
    scoped = scope(current)
    monkeypatch.setattr(builder, "ROSTER_SHA256", roster_digest)
    monkeypatch.setattr(config, "Settings", lambda: current)
    monkeypatch.setattr(builder, "make_native_query_provider",
                        lambda _settings: pytest.fail("no provider in preflight"))
    monkeypatch.delenv(builder.APPROVAL_ENV, raising=False)
    monkeypatch.setattr(sys, "argv", [
        str(builder.__file__), "--preflight-inputs", "--roster", str(roster_path),
        "--roster-sha256", roster_digest, "--output", str(tmp_path / "vectors.json"),
        "--principal-id", str(scoped.principal_id), "--subject-id", str(scoped.subject_id),
        "--corpus-revision", str(scoped.corpus_revision),
        "--embedding-space-hash", scoped.embedding_space_hash,
    ])
    assert builder.main() == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "preflight_ready"
    assert report["case_count"] == 11
    assert report["provider_requests"] == report["database_reads"] == 0
    assert report["estimated_input_tokens"] <= 512
    assert not (tmp_path / "vectors.json").exists()
    assert not list(tmp_path.glob(".query-vector-approval-*.used"))
