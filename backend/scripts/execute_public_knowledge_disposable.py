"""Execute one frozen public holdout in a guarded disposable database.

Only `scripts/run_public_knowledge_holdout.py` should launch this child. The
parent owns Docker, generated credentials and cleanup. This mock-only run uses
local deterministic vectors, never the frozen holdout questions, and never
executes the source selector. It is plumbing evidence only.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
from pathlib import Path
import secrets
import sys
from types import SimpleNamespace
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import preflight_public_knowledge_disposable_run as admission  # noqa: E402


DATABASE_NAME = "public_holdout_test"
MOCK_KEY = "public-holdout-mock-no-network"
MAX_DOCUMENT_CALLS = 2
MAX_QUERY_CALLS = 12
MAX_DOCUMENT_TOKENS = 8_000
MAX_QUERY_TOKENS = 1_024
MAX_PROVIDER_SECONDS = 600


class Refusal(RuntimeError):
    """A fixed non-content failure code."""


def require_disposable_target(mode: str) -> None:
    """Validate process configuration before importing any application module."""
    from sqlalchemy.engine import make_url

    value = os.environ.get("DATABASE_URL", "")
    try:
        url = make_url(value)
    except Exception:
        raise Refusal("database_target_invalid") from None
    if (
        mode != "mock"
        or os.environ.get("CARDCH_PUBLIC_HOLDOUT_MODE") != mode
        or os.environ.get("CARDCH_PUBLIC_HOLDOUT_RUN_ID", "") == ""
        or os.environ.get("ENVIRONMENT") != "test"
        or url.drivername != "postgresql+asyncpg"
        or url.host not in {"127.0.0.1", "localhost", "::1"}
        or url.database != DATABASE_NAME
        or not isinstance(url.port, int)
        or not 1 <= url.port <= 65535
        or url.username != "qa"
        or os.environ.get("RAG_ASK_ENABLED", "").lower() != "false"
        or os.environ.get("RAG_AI_PROVIDER_ENABLED", "").lower() != "false"
        or os.environ.get("FLASHCARD_AI_PROVIDER_ENABLED", "").lower() != "false"
    ):
        raise Refusal("database_target_invalid")


def validate_settings(settings, mode: str) -> None:
    from decimal import Decimal

    if (
        settings.environment != "test"
        or not settings.rag_enabled
        or settings.rag_ask_enabled
        or settings.rag_ai_provider_enabled
        or settings.flashcard_ai_provider_enabled
        or not settings.rag_embedding_provider_enabled
        or settings.rag_embedding_provider != "gemini"
        or settings.rag_embedding_model != "gemini-embedding-001"
        or settings.rag_embedding_batch_size != 32
        or settings.rag_embedding_max_input_tokens != 2_048
        or settings.rag_embedding_provider_max_retries != 0
        or settings.rag_index_max_attempts != 1
        or settings.rag_embedding_provider_timeout_seconds != 30
        or settings.rag_embedding_input_cost_per_million_usd != Decimal("0.20")
        or settings.rag_embedding_max_estimated_cost_usd != Decimal("0.002")
        or settings.pdf_ocr_enabled
        or settings.rag_embedding_api_key_value != MOCK_KEY
    ):
        raise Refusal("runtime_profile_invalid")


class MockEmbeddingProvider:
    """Stable local vectors that prove plumbing without a model or network."""

    def __init__(self):
        self.requests = 0

    @staticmethod
    def _vector(value: str) -> tuple[float, ...]:
        import re

        values = [0.0] * 1_536
        for token in re.findall(r"[a-z0-9]+", value.casefold()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            slot = int.from_bytes(digest[:2], "big") % 1_536
            values[slot] += 1.0
        if not any(values):
            values[0] = 1.0
        norm = math.sqrt(math.fsum(item * item for item in values))
        return tuple(item / norm for item in values)

    async def embed_documents(self, texts, *, titles=None):
        from app.ai.embeddings import EmbeddingResponse
        from app.ai.providers import ProviderUsage

        if titles is not None:
            raise Refusal("unexpected_document_titles")
        self.requests += 1
        return EmbeddingResponse(
            vectors=tuple(self._vector(value) for value in texts),
            usage=ProviderUsage(sum(len(value.split()) for value in texts), 0, False),
        )

    async def embed_query(self, value):
        from app.ai.embeddings import EmbeddingResponse
        from app.ai.providers import ProviderUsage

        self.requests += 1
        return EmbeddingResponse(
            vectors=(self._vector(value),),
            usage=ProviderUsage(len(value.split()), 0, False),
        )

    def telemetry_snapshot(self):
        from app.ai.providers import ProviderAttemptTelemetry

        return ProviderAttemptTelemetry(
            request_count=self.requests, retry_count=0,
            rate_limit_wait_seconds=0, request_counts_by_stage={},
        )


class OneShotEmbeddingGate:
    """Counts before each request so an uncertain failure consumes the slot."""

    def __init__(self, provider, expected_batch_sizes: tuple[int, int]):
        self.provider = provider
        self.expected_batch_sizes = expected_batch_sizes
        self.document_calls = 0
        self.query_calls = 0
        self.document_tokens = 0
        self.query_tokens = 0
        self.deadline = asyncio.get_running_loop().time() + MAX_PROVIDER_SECONDS

    def telemetry_snapshot(self):
        return self.provider.telemetry_snapshot()

    async def _one_call(self, action):
        before = self.provider.telemetry_snapshot()
        remaining = self.deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            raise Refusal("provider_time_envelope_exceeded")
        try:
            async with asyncio.timeout(remaining):
                result = await action()
        except Exception:
            # Never replay a call whose outcome or billing is uncertain.
            raise Refusal("provider_outcome_uncertain") from None
        after = self.provider.telemetry_snapshot()
        if after.request_count - before.request_count != 1 or after.retry_count != before.retry_count:
            raise Refusal("physical_call_count_invalid")
        return result

    async def embed_documents(self, texts, *, titles=None):
        from app.ai.chunking import estimate_tokens

        if (self.document_calls >= MAX_DOCUMENT_CALLS
            or len(texts) != self.expected_batch_sizes[self.document_calls]
            or titles is not None):
            raise Refusal("document_call_envelope_exceeded")
        count = sum(estimate_tokens(value) for value in texts)
        if self.document_tokens + count > MAX_DOCUMENT_TOKENS:
            raise Refusal("document_call_envelope_exceeded")
        self.document_calls += 1
        self.document_tokens += count
        return await self._one_call(lambda: self.provider.embed_documents(texts))

    async def embed_query(self, value):
        from app.ai.chunking import estimate_tokens

        count = estimate_tokens(value)
        if self.query_calls >= MAX_QUERY_CALLS or self.query_tokens + count > MAX_QUERY_TOKENS:
            raise Refusal("query_call_envelope_exceeded")
        self.query_calls += 1
        self.query_tokens += count
        return await self._one_call(lambda: self.provider.embed_query(value))


def _expect(response, code: int, stage: str) -> dict:
    if response.status_code != code:
        raise Refusal(stage)
    if not response.content:
        return {}
    try:
        value = response.json()
    except ValueError:
        raise Refusal(stage) from None
    if not isinstance(value, dict):
        raise Refusal(stage)
    return value


async def _seed_principals():
    from sqlalchemy import func, select
    from app.database import async_session_maker
    from app.models.user import User, UserRole
    from app.schemas.user import UserCreate
    from app.services.auth import AuthService

    async with async_session_maker() as db:
        async with db.begin():
            if await db.scalar(select(func.count()).select_from(User)):
                raise Refusal("disposable_database_not_empty")
            suffix = secrets.token_hex(6)
            credentials = []
            for label, role in (
                ("instructor", UserRole.INSTRUCTOR),
                ("student", UserRole.STUDENT),
                ("outsider", UserRole.STUDENT),
            ):
                user = await AuthService.create_user(db, UserCreate(
                    email=f"holdout-{label}-{suffix}@example.com",
                    password=secrets.token_urlsafe(24),
                    full_name=f"Holdout {label.title()}",
                ), role)
                token, _refresh = await AuthService.create_session(db, user)
                credentials.append((user.id, token))
    return tuple(credentials)


async def execute(mode: str, temp_dir: Path) -> dict:
    require_disposable_target(mode)
    preflight = admission.preflight(temp_dir)
    if preflight["estimated_document_requests"] != 2 or preflight["query_case_count"] != 12:
        raise Refusal("source_envelope_invalid")

    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import text
    from app.config import get_settings
    from app.database import async_session_maker, close_database, engine, verify_database_revision
    from app.main import app
    from app.models.flashcard import Enrollment
    from app.workers.generation import GenerationWorker
    from app.workers.knowledge_index import KnowledgeIndexWorker

    settings = get_settings()
    validate_settings(settings, mode)
    async with engine.connect() as connection:
        identity = (await connection.execute(text("SELECT current_database(), current_user"))).one()
        if identity[0] != DATABASE_NAME or identity[1] != "qa":
            raise Refusal("database_identity_invalid")
    await verify_database_revision()

    directory, sources, _ = admission.source_preflight.load_manifest(
        temp_dir / admission.MANIFEST[0], admission.MANIFEST[1]
    )
    _cases, _, _ = admission.source_preflight.load_holdout(
        temp_dir / admission.HOLDOUT[0], admission.HOLDOUT[1], directory=directory,
        source_hashes={source["sha256"] for source in sources},
    )
    (instructor_id, instructor_token), (student_id, student_token), (
        _outsider_id, outsider_token,
    ) = await _seed_principals()
    headers = {"Authorization": f"Bearer {instructor_token}"}
    student_headers = {"Authorization": f"Bearer {student_token}"}
    outsider_headers = {"Authorization": f"Bearer {outsider_token}"}
    expected_sizes = tuple(int(row["chunks"]) for row in preflight["sources"])
    provider = MockEmbeddingProvider()
    gate = OneShotEmbeddingGate(provider, expected_sizes)
    document_ids: dict[str, UUID] = {}
    transport = ASGITransport(app=app)

    try:
        async with AsyncClient(transport=transport, base_url="http://localhost") as client:
            subject = _expect(await client.post(
                "/subjects", headers=headers, json={"name": "Public holdout Subject"},
            ), 201, "subject_create_failed")
            subject_id = UUID(subject["id"])
            other = _expect(await client.post(
                "/subjects", headers=headers, json={"name": "Other Subject"},
            ), 201, "subject_create_failed")
            other_subject_id = UUID(other["id"])
            async with async_session_maker() as db:
                async with db.begin():
                    db.add(Enrollment(student_id=student_id, subject_id=subject_id))

            for source in sources:
                name = source["file"]
                path = temp_dir / name
                raw = path.read_bytes()
                if hashlib.sha256(raw).hexdigest() != source["sha256"]:
                    raise Refusal("pdf_changed")
                reservation = _expect(await client.post(
                    "/flashcards/knowledge-jobs",
                    headers=headers | {"Idempotency-Key": secrets.token_hex(16)},
                    json={"subject_id": str(subject_id), "title": name,
                          "source_pdf_name": name},
                ), 202, "knowledge_reservation_failed")
                job_id = UUID(reservation["id"])
                uploaded = _expect(await client.put(
                    f"/flashcards/knowledge-jobs/{job_id}/source",
                    headers=headers | {"Content-Type": "application/pdf"},
                    content=raw,
                ), 202, "knowledge_upload_failed")
                if uploaded["status"] != "queued":
                    raise Refusal("knowledge_upload_not_queued")
                generation = GenerationWorker(settings=settings)
                claim = await generation.claim_next()
                if claim is None or claim[0] != job_id:
                    raise Refusal("knowledge_capture_claim_invalid")
                await generation.process_claim(*claim)
                captured = _expect(await client.get(
                    f"/flashcards/generation-jobs/{job_id}", headers=headers,
                ), 200, "knowledge_capture_failed")
                if (captured["status"] != "completed"
                    or captured["knowledge_capture_status"] != "captured"
                    or not captured.get("document_id")):
                    raise Refusal("knowledge_capture_failed")
                document_id = UUID(captured["document_id"])
                document_ids[source["sha256"]] = document_id

                indexer = KnowledgeIndexWorker(settings=settings, provider=gate)
                index_claim = await indexer.claim_next()
                if index_claim is None:
                    raise Refusal("knowledge_index_claim_invalid")
                await indexer.process_claim(*index_claim)
                detail = _expect(await client.get(
                    f"/subjects/{subject_id}/knowledge/documents/{document_id}",
                    headers=headers,
                ), 200, "knowledge_index_failed")
                index_job = detail["index_job"]
                index_revision = detail["index_revision"]
                if (index_job["status"] != "completed" or index_job["attempt_count"] != 1
                    or index_revision["status"] != "ready"
                    or index_revision["chunk_count"] != index_revision["embedded_count"]):
                    raise Refusal("knowledge_index_failed")
                _expect(await client.post(
                    f"/subjects/{subject_id}/knowledge/documents/{document_id}/review-publish",
                    headers=headers,
                ), 200, "knowledge_publish_failed")

            if gate.document_calls != MAX_DOCUMENT_CALLS or gate.document_tokens > MAX_DOCUMENT_TOKENS:
                raise Refusal("document_call_count_invalid")
            published = _expect(await client.get(
                f"/subjects/{subject_id}/published-knowledge/documents", headers=student_headers,
            ), 200, "published_list_failed")
            if len(published["documents"]) != 2:
                raise Refusal("published_list_invalid")

            # Exercise the query-call envelope with synthetic plumbing strings.
            # Do not embed a frozen holdout question or inspect selector output.
            for number in range(MAX_QUERY_CALLS):
                await gate.embed_query(f"Disposable plumbing query {number + 1}")
            if (gate.query_calls != MAX_QUERY_CALLS or gate.query_tokens > MAX_QUERY_TOKENS
                or gate.telemetry_snapshot().request_count != 14
                or gate.telemetry_snapshot().retry_count != 0):
                raise Refusal("query_call_count_invalid")

            # Both published originals must open through the real enrolled-
            # student routes and match the frozen bytes. This is not a page
            # selection or usefulness measurement.
            opened_ids: set[str] = set()
            for source, expected in zip(sources, preflight["sources"], strict=True):
                document_id = document_ids[source["sha256"]]
                url = f"/subjects/{subject_id}/published-knowledge/documents/{document_id}/original-pdf"
                metadata = await client.head(url, headers=student_headers)
                if (metadata.status_code != 200
                    or int(metadata.headers.get("X-PDF-Page-Count", "0")) != expected["pages"]):
                    raise Refusal("pdf_metadata_open_failed")
                original = (temp_dir / source["file"]).read_bytes()
                first = await client.get(url, headers=student_headers | {"Range": "bytes=0-1023"})
                if first.status_code != 206 or first.content != original[:1024]:
                    raise Refusal("pdf_range_open_failed")
                # The original-PDF endpoint deliberately requires bounded
                # ranges. Reassemble only through that public contract; an
                # unbounded GET is rejected by design.
                if (await client.get(url, headers=student_headers)).status_code != 400:
                    raise Refusal("pdf_unbounded_get_not_rejected")
                digest = hashlib.sha256()
                maximum_range_bytes = 8 * 1024 * 1024
                for start in range(0, len(original), maximum_range_bytes):
                    end = min(start + maximum_range_bytes, len(original))
                    part = await client.get(url, headers=student_headers | {
                        "Range": f"bytes={start}-{end - 1}",
                    })
                    if (part.status_code != 206
                        or part.headers.get("Content-Range") !=
                            f"bytes {start}-{end - 1}/{len(original)}"
                        or len(part.content) != end - start
                        or part.content != original[start:end]):
                        raise Refusal("pdf_range_open_failed")
                    digest.update(part.content)
                if digest.hexdigest() != source["sha256"]:
                    raise Refusal("pdf_original_bytes_changed")
                opened_ids.add(str(document_id))

            probe_id = next(iter(document_ids.values()))
            pdf_url = f"/subjects/{subject_id}/published-knowledge/documents/{probe_id}/original-pdf"
            if (await client.head(pdf_url, headers=outsider_headers)).status_code != 404:
                raise Refusal("pdf_access_control_failed")
            if (await client.get(pdf_url, headers=outsider_headers)).status_code != 404:
                raise Refusal("pdf_access_control_failed")
            if (await client.get(pdf_url, headers=headers)).status_code != 403:
                raise Refusal("pdf_access_control_failed")
            other_url = f"/subjects/{other_subject_id}/published-knowledge/documents/{probe_id}/original-pdf"
            if (await client.get(other_url, headers=student_headers)).status_code != 404:
                raise Refusal("pdf_access_control_failed")

            # Confirm a published PDF becomes inaccessible after the owner
            # unpublishes it. This happens only after the mock checks finish.
            _expect(await client.post(
                f"/subjects/{subject_id}/knowledge/documents/{probe_id}/unpublish",
                headers=headers,
            ), 200, "knowledge_unpublish_failed")
            if (await client.get(pdf_url, headers=student_headers)).status_code != 404:
                raise Refusal("pdf_stale_access_failed")
            return {
                "status": "disposable_mock_plumbing_passed",
                "mode": mode, "document_calls": gate.document_calls,
                "query_calls": gate.query_calls, "provider_retries": 0,
                "answer_calls": 0, "opened_pdf_document_count": len(opened_ids),
                "selector_calls": 0, "holdout_questions_embedded": 0,
                "release_gate_passed": False,
            }
    finally:
        await close_database()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("mock",), required=True)
    parser.add_argument("--temp-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = asyncio.run(execute(args.mode, args.temp_dir))
    except Exception as exc:
        code = str(exc) if isinstance(exc, (Refusal, admission.Refusal,
                                           admission.source_preflight.Refusal)) else "disposable_run_failed"
        raise SystemExit(f"Public Knowledge disposable execution refused: {code}") from None
    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
