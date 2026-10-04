"""Admission-bound local context for the prospective v7 source-only policy.

The enqueue caller already owns Subject/access/corpus authorization and holds
the thread admission lock. Capture occurs before adding the current question;
only identities, timestamps, hashes and literal-span offsets are persisted.
The worker rehydrates the exact binding before each expensive boundary. Later
queued questions, assistant responses and an older fallback are never context.
This helper does not authorize sources, commit, call a provider or read Settings.
Completed reference reads do not depend on this admission context.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.source_judgment_visual_v3 import (
    ADMISSION_SCHEMA,
    CONTRACT_VERSION,
    AdmissionUserMessage,
    QuestionContextBinding,
    SubjectAdmissionSnapshot,
    admission_identity,
    bind_question_context,
)
from app.ai.source_navigation import navigation_query_v4
from app.ai.source_navigation_context_v1 import (
    LiteralSubjectAnchor,
    MAX_CURRENT_CHARS,
    POLICY_ID,
    resolve_subject_context,
)
from app.models.rag import RagAnswerJob, RagMessage, RagThread
from app.time_utils import as_utc


ANSWER_POLICY = "related_knowledge_navigation_v7"
_SPAN_FIELDS = (
    "subject_start_offset", "subject_end_offset", "subject_start_byte_offset",
    "subject_end_byte_offset", "subject_sha256",
)
_PRECEDING_FIELDS = (
    "preceding_message_id", "preceding_question_sha256", "preceding_created_at",
    "preceding_expires_at",
)


class QuestionContextUnavailable(ValueError):
    """Safe content-free failure for missing, expired or altered bindings."""

    def __init__(self) -> None:
        super().__init__("question_context_unavailable")


@dataclass(frozen=True, slots=True)
class CapturedQuestionContext:
    snapshot: SubjectAdmissionSnapshot
    binding: QuestionContextBinding = field(repr=False)

    @property
    def admission_sha256(self) -> str:
        return self.binding.admission_sha256


@dataclass(frozen=True, slots=True)
class HydratedQuestionContext:
    """Only the v3 builder may project its literal anchor into a provider wire."""

    snapshot: SubjectAdmissionSnapshot
    binding: QuestionContextBinding = field(repr=False)
    question: str = field(repr=False)
    preceding_question: str | None = field(repr=False)
    raw_navigation_query: str | None = field(repr=False)
    local_query: str | None = field(repr=False)

    @property
    def needs_clarification(self) -> bool:
        return self.local_query is None or self.binding.status == "needs_clarification"


def _require(condition: bool) -> None:
    if not condition:
        raise QuestionContextUnavailable()


def _digest(content: str) -> str:
    _require(type(content) is str)
    try:
        return sha256(content.encode("utf-8")).hexdigest()
    except UnicodeError:
        raise QuestionContextUnavailable() from None


def _time(value: datetime) -> datetime:
    _require(type(value) is datetime)
    return as_utc(value)


def _uuid(value: UUID) -> UUID:
    # asyncpg returns a UUID subclass. Normalize trusted ORM identities before
    # passing them to the pure contract, which requires an exact stdlib UUID.
    _require(isinstance(value, UUID) and value.int > 0)
    return UUID(bytes=value.bytes)


def _message(row: RagMessage) -> AdmissionUserMessage:
    _require(row is not None and row.role == "user" and row.outcome is None
             and row.source_count == 0 and type(row.content) is str
             and 0 < len(row.content) <= MAX_CURRENT_CHARS)
    _require(all(isinstance(value, UUID) and value.int > 0 for value in (
        row.id, row.user_id, row.thread_id, row.subject_id,
    )))
    return AdmissionUserMessage(
        _uuid(row.id), _uuid(row.user_id), _uuid(row.thread_id), _uuid(row.subject_id), _digest(row.content),
        _time(row.created_at), _time(row.expires_at),
    )


async def _scoped_thread(
    db: AsyncSession, *, thread_id: UUID, user_id: UUID, subject_id: UUID,
) -> RagThread:
    row = await db.scalar(select(RagThread).where(
        RagThread.id == thread_id, RagThread.user_id == user_id,
        RagThread.subject_id == subject_id,
    ).with_for_update())
    _require(row is not None)
    return row


async def _latest_preceding(
    db: AsyncSession, *, current: AdmissionUserMessage,
) -> RagMessage | None:
    # First choose the latest USER, without eligibility filters. An expired or
    # unusable latest turn must not cause an older topic to become the context.
    return await db.scalar(select(RagMessage).where(
        RagMessage.thread_id == current.thread_id,
        RagMessage.user_id == current.user_id,
        RagMessage.subject_id == current.subject_id,
        RagMessage.role == "user",
        RagMessage.id != current.message_id,
        RagMessage.created_at < current.created_at,
    ).order_by(RagMessage.created_at.desc(), RagMessage.id.desc()).limit(1).with_for_update())


def _bind(
    question: str, snapshot: SubjectAdmissionSnapshot, *, checked_at: datetime,
    raw_navigation_query: str | None, preceding_question: str | None,
    stored_anchor: LiteralSubjectAnchor | None = None,
) -> QuestionContextBinding:
    history = () if preceding_question is None else (("user", preceding_question),)
    resolved = resolve_subject_context(
        question, history, raw_navigation_query=raw_navigation_query,
    )
    anchor = resolved.anchor if stored_anchor is None else stored_anchor
    try:
        return bind_question_context(
            question, snapshot, checked_at=checked_at,
            raw_navigation_query=raw_navigation_query,
            preceding_question=preceding_question, anchor=anchor,
        )
    except ValueError:
        raise QuestionContextUnavailable() from None


async def capture_question_context(
    db: AsyncSession, *, current: RagMessage, thread: RagThread,
    corpus_revision: int, embedding_space_hash: str, captured_at: datetime,
    raw_navigation_query: str | None,
) -> CapturedQuestionContext:
    """Capture under the thread lock, before enqueue inserts ``current``.

    The caller must assign its UUID and created/expiry timestamps first. Both
    capture and the eventual job use that same admission timestamp. A raw-clear
    question captures no predecessor. Unresolved latest-user grammar captures
    that user's identity but yields clarification, without scanning older turns.
    """
    checked_at = _time(captured_at)
    identity = _message(current)
    _require(identity.created_at == checked_at and identity.expires_at > checked_at)
    _require(thread is not None and (thread.id, thread.user_id, thread.subject_id)
             == (identity.thread_id, identity.user_id, identity.subject_id))
    _require(raw_navigation_query == navigation_query_v4(current.content, ()))
    with db.no_autoflush:
        await _scoped_thread(db, thread_id=identity.thread_id,
                             user_id=identity.user_id, subject_id=identity.subject_id)
        _require(await db.get(RagMessage, identity.message_id) is None)
        previous = None if raw_navigation_query is not None else await _latest_preceding(
            db, current=identity,
        )
    if previous is not None:
        try:
            _require(not getattr(previous, "hidden", False)
                     and _time(previous.expires_at) > checked_at)
            _message(previous)
        except QuestionContextUnavailable:
            previous = None
    snapshot = SubjectAdmissionSnapshot(
        current=identity, preceding=None if previous is None else _message(previous),
        corpus_revision=corpus_revision, embedding_space_hash=embedding_space_hash,
        captured_at=checked_at, raw_question_clear=raw_navigation_query is not None,
    )
    binding = _bind(
        current.content, snapshot, checked_at=checked_at,
        raw_navigation_query=raw_navigation_query,
        preceding_question=None if previous is None else previous.content,
    )
    return CapturedQuestionContext(snapshot, binding)


def _binding_model(binding_model: Any = None) -> Any:
    if binding_model is not None:
        return binding_model
    # Lazy only while the new model/migration is being prepared concurrently.
    from app.models.rag import RagAnswerQuestionContext
    return RagAnswerQuestionContext


def _row_values(job: RagAnswerJob, captured: CapturedQuestionContext) -> dict[str, Any]:
    snapshot, binding = captured.snapshot, captured.binding
    current, preceding = snapshot.current, snapshot.preceding
    _require(job.answer_policy_version == ANSWER_POLICY
             and job.source_judge_contract_version == CONTRACT_VERSION)
    _require((job.question_message_id, job.thread_id, job.user_id, job.subject_id)
             == (current.message_id, current.thread_id, current.user_id, current.subject_id))
    _require(_time(job.created_at) == snapshot.captured_at
             and job.corpus_revision == snapshot.corpus_revision
             and job.embedding_space_hash == snapshot.embedding_space_hash)
    try:
        _require(binding.admission_sha256 == admission_identity(
            snapshot, checked_at=snapshot.captured_at,
        ) and binding.current_question_sha256 == current.content_sha256
                 and binding.contract_version == CONTRACT_VERSION)
    except ValueError:
        raise QuestionContextUnavailable() from None
    anchor = binding.anchor
    _require(binding.status in {"clear_current_question", "resolved_literal_subject", "needs_clarification"})
    _require((binding.status == "clear_current_question") == snapshot.raw_question_clear
             and (binding.status == "resolved_literal_subject") == (anchor is not None))
    if anchor is not None:
        _require(preceding is not None and anchor.policy_id == POLICY_ID
                 and anchor.current_question_sha256 == current.content_sha256
                 and anchor.preceding_question_sha256 == preceding.content_sha256
                 and anchor.subject_sha256 == _digest(anchor.subject)
                 and anchor.preceding_history_index == 0)
    values: dict[str, Any] = {
        "job_id": job.id, "thread_id": current.thread_id, "user_id": current.user_id,
        "subject_id": current.subject_id, "current_message_id": current.message_id,
        "context_version": ADMISSION_SCHEMA, "raw_question_clear": snapshot.raw_question_clear,
        "current_question_sha256": current.content_sha256,
        "current_created_at": current.created_at, "current_expires_at": current.expires_at,
        "captured_at": snapshot.captured_at, "admission_sha256": binding.admission_sha256,
        "preceding_message_id": None if preceding is None else preceding.message_id,
        "preceding_question_sha256": None if preceding is None else preceding.content_sha256,
        "preceding_created_at": None if preceding is None else preceding.created_at,
        "preceding_expires_at": None if preceding is None else preceding.expires_at,
        "subject_start_offset": None if anchor is None else anchor.start_offset,
        "subject_end_offset": None if anchor is None else anchor.end_offset,
        "subject_start_byte_offset": None if anchor is None else anchor.start_byte_offset,
        "subject_end_byte_offset": None if anchor is None else anchor.end_byte_offset,
        "subject_sha256": None if anchor is None else anchor.subject_sha256,
    }
    _require(isinstance(job.id, UUID) and job.id.int > 0)
    return values


async def persist_question_context(
    db: AsyncSession, *, job: RagAnswerJob, captured: CapturedQuestionContext,
    binding_model: Any = None,
) -> Any:
    """Insert once in the caller's transaction; never overwrite an old binding.

    The two job snapshot fields are assigned here before the caller flushes the
    job. No commit occurs. The PostgreSQL deferred admission trigger additionally
    requires this matching binding when the transaction commits.
    """
    values = _row_values(job, captured)
    model = _binding_model(binding_model)
    with db.no_autoflush:
        _require(await db.get(model, job.id) is None)
    job.source_context_policy_version = ADMISSION_SCHEMA
    job.source_context_admission_sha256 = captured.admission_sha256
    row = model(**values)
    db.add(row)
    return row


def _snapshot_from_row(row: Any, job: RagAnswerJob) -> SubjectAdmissionSnapshot:
    current = AdmissionUserMessage(
        _uuid(row.current_message_id), _uuid(row.user_id), _uuid(row.thread_id), _uuid(row.subject_id),
        row.current_question_sha256, _time(row.current_created_at), _time(row.current_expires_at),
    )
    present = [getattr(row, name) is not None for name in _PRECEDING_FIELDS]
    _require(all(present) or not any(present))
    preceding = None if not any(present) else AdmissionUserMessage(
        _uuid(row.preceding_message_id), _uuid(row.user_id), _uuid(row.thread_id), _uuid(row.subject_id),
        row.preceding_question_sha256, _time(row.preceding_created_at), _time(row.preceding_expires_at),
    )
    return SubjectAdmissionSnapshot(
        current, preceding, job.corpus_revision, job.embedding_space_hash,
        _time(row.captured_at), row.raw_question_clear, row.context_version,
    )


def _anchor_from_row(
    row: Any, *, question: str, preceding_question: str | None,
) -> LiteralSubjectAnchor | None:
    present = [getattr(row, name) is not None for name in _SPAN_FIELDS]
    _require(all(present) or not any(present))
    if not any(present):
        return None
    _require(preceding_question is not None)
    start, end = row.subject_start_offset, row.subject_end_offset
    _require(type(start) is int and type(end) is int and 0 <= start < end <= len(preceding_question))
    return LiteralSubjectAnchor(
        preceding_question[start:end], row.subject_sha256, _digest(question),
        _digest(preceding_question), 0, start, end,
        row.subject_start_byte_offset, row.subject_end_byte_offset, POLICY_ID,
    )


async def rehydrate_question_context(
    db: AsyncSession, *, job: RagAnswerJob, checked_at: datetime,
    binding_model: Any = None,
) -> HydratedQuestionContext:
    """Validate an immutable admission row against current local messages.

    Call before query embedding, before reserving the source-ID attempt, and
    inside atomic completion after the caller rechecks access/corpus/lease.
    Expired/deleted/altered current or predecessor rows fail safely. A newer
    queued turn is excluded; a backdated substituted predecessor is rejected.
    """
    now = _time(checked_at)
    _require(job.answer_policy_version == ANSWER_POLICY
             and job.source_judge_contract_version == CONTRACT_VERSION
             and job.source_context_policy_version == ADMISSION_SCHEMA)
    model = _binding_model(binding_model)
    await _scoped_thread(db, thread_id=job.thread_id, user_id=job.user_id, subject_id=job.subject_id)
    row = await db.scalar(select(model).where(model.job_id == job.id).with_for_update())
    _require(row is not None and row.context_version == ADMISSION_SCHEMA
             and row.admission_sha256 == job.source_context_admission_sha256
             and (row.current_message_id, row.thread_id, row.user_id, row.subject_id)
             == (job.question_message_id, job.thread_id, job.user_id, job.subject_id))
    snapshot = _snapshot_from_row(row, job)
    _require(snapshot.captured_at == _time(job.created_at))
    try:
        _require(admission_identity(snapshot, checked_at=now) == row.admission_sha256)
    except ValueError:
        raise QuestionContextUnavailable() from None
    current_row = await db.scalar(select(RagMessage).where(
        RagMessage.id == snapshot.current.message_id,
        RagMessage.thread_id == job.thread_id, RagMessage.user_id == job.user_id,
        RagMessage.subject_id == job.subject_id, RagMessage.role == "user",
    ).with_for_update())
    _require(current_row is not None and _message(current_row) == snapshot.current)
    raw_query = navigation_query_v4(current_row.content, ())
    _require((raw_query is not None) == snapshot.raw_question_clear)
    previous_row = None
    if not snapshot.raw_question_clear and snapshot.preceding is not None:
        previous_row = await _latest_preceding(db, current=snapshot.current)
        _require(previous_row is not None and not getattr(previous_row, "hidden", False)
                 and _message(previous_row) == snapshot.preceding)
    else:
        _require(snapshot.preceding is None)
    previous_question = None if previous_row is None else previous_row.content
    anchor = _anchor_from_row(row, question=current_row.content, preceding_question=previous_question)
    binding = _bind(
        current_row.content, snapshot, checked_at=now, raw_navigation_query=raw_query,
        preceding_question=previous_question, stored_anchor=anchor,
    )
    _require((binding.anchor is None) == (anchor is None)
             and binding.admission_sha256 == row.admission_sha256)
    local_query = raw_query
    if binding.anchor is not None:
        # Both literal inputs are retained. Never truncate a qualifier to fit.
        joined = f"{current_row.content.strip()} {binding.anchor.subject}"
        local_query = joined if len(joined) <= MAX_CURRENT_CHARS else None
    return HydratedQuestionContext(
        snapshot, binding, current_row.content, previous_question, raw_query, local_query,
    )
