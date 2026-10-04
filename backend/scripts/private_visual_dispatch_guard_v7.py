"""Read-only diagnostic guards for exact reviewed visual-v3 source requests.

This is not an Ask worker, provider caller, persisted-job grant or approval.
The host owns quota, credentials, approvals, resource fences and transactions.
Render in one fresh transaction, roll it back, then check in another fresh
transaction after quota waiting immediately before HTTP. A selected-page read
needs a third fresh transaction. Receipts contain identities/digests, never
question/source/image bytes. No Settings instance or operator file is read here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import base64
import json
import os
from pathlib import Path, PurePosixPath
import re
from types import MappingProxyType, SimpleNamespace
from typing import TYPE_CHECKING, Callable, Mapping
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import source_judgment_visual_v3 as contract
from app.ai.source_navigation_context_v1 import resolve_subject_context
from app.config import ASK_REQUIRED_RELEASE_POLICY_VERSION, Settings

if TYPE_CHECKING:
    from app.ai.related_evidence import RelatedExcerptSelection
    from app.services.source_visual_preparation import PdfSourceBinding


SCHEMA = "private_visual_dispatch_guard_v7"
POLICY = "related_knowledge_navigation_v7"
CONTRACT = "visual_source_id_v3"
MAX_FRESH_SECONDS = 5
REPO_ROOT = Path(__file__).resolve().parents[2]
_SHA = re.compile(r"[0-9a-f]{64}")
_SEAL = object()
REQUIRED_CODE_PATHS = frozenset({
    "backend/app/config.py", "backend/app/models/knowledge.py",
    "backend/app/ai/chunking.py", "backend/app/ai/related_evidence.py",
    "backend/app/ai/source_navigation.py", "backend/app/ai/source_navigation_context_v1.py",
    "backend/app/ai/source_judgment_visual.py", "backend/app/ai/source_judgment_visual_v2.py",
    "backend/app/ai/source_judgment_visual_v3.py", "backend/app/services/knowledge_retrieval.py",
    "backend/app/services/knowledge_pdf.py", "backend/app/services/knowledge_pdf_renderer.py",
    "backend/app/services/source_visual_preparation.py",
    "backend/app/services/source_visual_preparation_v3.py",
})


class DispatchGuardError(ValueError):
    """Fixed content-free failures; callers must not retain wrapped exceptions."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise DispatchGuardError(code)


def _digest(value: object) -> str:
    return sha256(contract.canonical(value)).hexdigest()


def _utc(value: datetime) -> bool:
    return type(value) is datetime and value.tzinfo is not None and value.utcoffset().total_seconds() == 0


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class DispatchScope:
    principal_id: UUID
    subject_id: UUID
    corpus_revision: int
    embedding_space_hash: str

    def identity(self) -> dict:
        _require(all(isinstance(value, UUID) and value.int > 0 for value in
                     (self.principal_id, self.subject_id))
                 and type(self.corpus_revision) is int and self.corpus_revision >= 1
                 and type(self.embedding_space_hash) is str and _SHA.fullmatch(self.embedding_space_hash) is not None,
                 "scope_invalid")
        return {"principal_id": str(self.principal_id), "subject_id": str(self.subject_id),
                "corpus_revision": self.corpus_revision, "embedding_space_hash": self.embedding_space_hash}


@dataclass(frozen=True, slots=True)
class GuardPins:
    bridge_sha256: str
    runtime_sha256: str
    request_sha256: str
    admission_sha256: str
    guard_code_sha256: str
    code_sha256: Mapping[str, str] = field(repr=False)

    def __post_init__(self) -> None:
        if isinstance(self.code_sha256, Mapping):
            object.__setattr__(self, "code_sha256", MappingProxyType(dict(self.code_sha256)))


@dataclass(frozen=True, slots=True)
class FrozenCandidate:
    id: str
    document_id: UUID
    content_revision_id: UUID
    index_revision_id: UUID
    page_number: int
    start_offset: int
    end_offset: int
    pdf_sha256: str
    cue_sha256: str
    png_sha256: str
    page_text_sha256: str


@dataclass(frozen=True, slots=True)
class FrozenDispatchCase:
    case_id: str
    question: str = field(repr=False)
    request_bytes: bytes = field(repr=False)
    snapshot: contract.SubjectAdmissionSnapshot = field(repr=False)
    candidates: tuple[FrozenCandidate, ...] = field(repr=False)
    preceding_question: str | None = field(default=None, repr=False)


@dataclass(frozen=True, slots=True)
class RenderedDispatchProof:
    """Local immediate-call custody only; never deserialize or treat as a grant."""

    case_identity_sha256: str
    source_code_sha256: str
    request_sha256: str
    production_interfaces: bool
    bindings: tuple[PdfSourceBinding, ...] = field(repr=False)
    _seal: object = field(repr=False)


@dataclass(frozen=True, slots=True)
class GuardServices:
    """Synthetic test seams; real calls must use defaults with pinned code."""

    authorize: Callable | None = None
    prepare: Callable | None = None
    check_bindings: Callable | None = None
    read_archive: Callable | None = None


def _dependencies(services: GuardServices | None, settings: Settings) -> GuardServices:
    # Source/navigation models transitively import app.database, which loads
    # Settings at import. Keep module import inert and fence that import before
    # it could inspect an operator file or unrelated provider credentials.
    if services is not None:
        _require(type(services) is GuardServices and os.environ.get("ENVIRONMENT") == "test",
                 "test_interfaces_forbidden")
    else:
        _require(not (REPO_ROOT / ".env").exists(), "operator_env_mount_forbidden")
        _require(all(name not in os.environ for name in (
            "FLASHCARD_AI_API_KEY", "RAG_AI_API_KEY", "RAG_EMBEDDING_API_KEY", "RAG_SOURCE_JUDGE_API_KEY")),
            "provider_credentials_forbidden")
    _require(all(getattr(settings, name) is None for name in (
        "flashcard_ai_api_key", "rag_ai_api_key", "rag_embedding_api_key", "rag_source_judge_api_key")),
        "runtime_not_closed")
    from app.services.knowledge_retrieval import KnowledgeRetriever
    from app.services.knowledge_pdf import read_complete_pdf_archive
    from app.services.source_visual_preparation import check_pdf_bindings
    from app.services.source_visual_preparation_v3 import prepare_visual_sources_v3 as prepare
    supplied = services or GuardServices()
    return GuardServices(supplied.authorize or KnowledgeRetriever.authorize, supplied.prepare or prepare,
                         supplied.check_bindings or check_pdf_bindings, supplied.read_archive or read_complete_pdf_archive)


def _settings(settings: Settings, scope: DispatchScope) -> None:
    _require(settings.environment == "development" and settings.rag_ask_enabled is False
             and settings.rag_source_judge_provider_enabled is False
             and ASK_REQUIRED_RELEASE_POLICY_VERSION == POLICY
             and settings.rag_source_judge_contract_version == CONTRACT
             and settings.rag_source_judge_provider == "gemini"
             and settings.rag_source_judge_model == contract.MODEL
             and settings.rag_source_judge_thinking_level == "high"
             and settings.rag_source_judge_max_input_tokens == 32768
             and settings.rag_source_judge_max_output_tokens == 4096
             and settings.rag_source_judge_provider_timeout_seconds == 120
             and settings.rag_source_judge_provider_max_retries == 0
             and all(getattr(settings, name) is None for name in (
                 "flashcard_ai_api_key", "rag_ai_api_key", "rag_embedding_api_key", "rag_source_judge_api_key")),
             "runtime_not_closed")
    from app.models.knowledge import embedding_space_hash
    _require(embedding_space_hash(settings.rag_embedding_space_identity) == scope.embedding_space_hash,
             "profile_incompatible")


def verify_code_pins(pins: GuardPins) -> str:
    """Read only repository code, never arbitrary paths or configuration files."""
    _require(type(pins) is GuardPins and all(type(value) is str and _SHA.fullmatch(value) for value in (
        pins.bridge_sha256, pins.runtime_sha256, pins.request_sha256, pins.admission_sha256,
        pins.guard_code_sha256)), "pins_invalid")
    _require(isinstance(pins.code_sha256, Mapping) and REQUIRED_CODE_PATHS <= set(pins.code_sha256)
             and len(pins.code_sha256) <= 100, "code_pins_invalid")
    try:
        for relative, expected in pins.code_sha256.items():
            _require(type(relative) is str and type(expected) is str and _SHA.fullmatch(expected)
                     and relative.startswith(("backend/", "scripts/"))
                     and PurePosixPath(relative).suffix == ".py"
                     and "\\" not in relative and ".." not in PurePosixPath(relative).parts,
                     "code_pins_invalid")
            # Checking a resolved target for symlinks loses the original link.
            # Reject redirecting files and directory ancestors before reading.
            original = REPO_ROOT / relative
            _require(not original.is_symlink() and not getattr(original, "is_junction", lambda: False)(),
                     "code_pins_invalid")
            path = original.resolve()
            _require(path.is_relative_to(REPO_ROOT) and path == original.absolute(), "code_pins_invalid")
            _require(sha256(path.read_bytes()).hexdigest() == expected, "runtime_code_changed")
        _require(sha256(Path(__file__).read_bytes()).hexdigest() == pins.guard_code_sha256,
                 "guard_code_changed")
    except OSError:
        raise DispatchGuardError("runtime_code_unavailable") from None
    return _digest(dict(pins.code_sha256))


def _case_identity(case: FrozenDispatchCase, scope: DispatchScope, pins: GuardPins) -> str:
    _require(type(case) is FrozenDispatchCase and type(case.case_id) is str
             and re.fullmatch(r"[A-Z][A-Z0-9_-]{1,31}", case.case_id) is not None
             and type(case.request_bytes) is bytes
             and 0 < len(case.request_bytes) <= contract.MAX_REQUEST_BYTES
             and sha256(case.request_bytes).hexdigest() == pins.request_sha256
             and type(case.candidates) is tuple and len(case.candidates) == 4,
             "frozen_case_invalid")
    return _digest({"case_id": case.case_id, "scope": scope.identity(),
        "request_sha256": pins.request_sha256, "admission_sha256": pins.admission_sha256,
        "bridge_sha256": pins.bridge_sha256, "runtime_sha256": pins.runtime_sha256,
        "candidates": [{name: str(getattr(row, name)) if name.endswith("_id") and name != "id"
                         else getattr(row, name) for name in FrozenCandidate.__dataclass_fields__}
                        for row in case.candidates]})


def _context(case: FrozenDispatchCase, scope: DispatchScope, pins: GuardPins, now: datetime):
    _require(_utc(now), "guard_time_invalid")
    from app.ai.source_navigation import navigation_query_v4
    raw = navigation_query_v4(case.question, ())
    history = (("user", case.preceding_question),) if case.preceding_question is not None else ()
    resolution = resolve_subject_context(case.question, history, raw_navigation_query=raw)
    binding = contract.bind_question_context(case.question, case.snapshot, checked_at=now,
        raw_navigation_query=raw, preceding_question=case.preceding_question, anchor=resolution.anchor)
    _require(binding.status != "needs_clarification" and binding.admission_sha256 == pins.admission_sha256
             and case.snapshot.current.user_id == scope.principal_id
             and case.snapshot.current.subject_id == scope.subject_id
             and case.snapshot.corpus_revision == scope.corpus_revision
             and case.snapshot.embedding_space_hash == scope.embedding_space_hash,
             "context_scope_invalid")
    query = raw if binding.anchor is None else f"{case.question.strip()} {binding.anchor.subject}"
    _require(type(query) is str and 0 < len(query) <= 4000, "question_context_unresolved")
    return raw, binding, query


async def _fresh_transaction(db: AsyncSession) -> None:
    """Must be the first SQL of the caller's explicitly begun transaction.

    PostgreSQL refuses changing isolation after an earlier query. A fresh
    session avoids stale identity-map values; expiring it also prevents cached
    metadata from a caller's prior rolled-back render phase being reused.

    The host must configure server statement_timeout <= 5,000 ms, lock_timeout
    <= 1,000 ms and idle_in_transaction_session_timeout <= 15,000 ms before
    this transaction starts, and put the whole final check in asyncio.timeout(5).
    Receipt freshness is checked after work, so it cannot interrupt blocked SQL.
    """
    _require(db.in_transaction() and not db.new and not db.dirty and not db.deleted
             and db.autoflush is False, "fresh_read_only_transaction_required")
    await db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
    _require((await db.scalar(text("SHOW transaction_read_only"))) == "on"
             and (await db.scalar(text("SHOW transaction_isolation"))) == "repeatable read",
             "fresh_read_only_transaction_required")
    db.expire_all()


async def _current(db, *, services, settings, scope, case, pins, selections, now):
    from app.ai.related_evidence import RelatedExcerptSelection
    from app.services.knowledge_retrieval import SOURCE_NAVIGATION_RETRIEVAL_POLICY
    raw, binding, query = _context(case, scope, pins, now)
    _require(type(selections) is tuple and len(selections) == 4
             and all(type(item) is RelatedExcerptSelection for item in selections),
             "candidate_binding_invalid")
    documents = tuple(dict.fromkeys(item.source.document_id for item in selections))
    retriever = await services.authorize(db, principal=SimpleNamespace(id=scope.principal_id),
        subject_id=scope.subject_id, query=query, document_ids=documents,
        limit=SOURCE_NAVIGATION_RETRIEVAL_POLICY.max_results, policy=SOURCE_NAVIGATION_RETRIEVAL_POLICY)
    _require(retriever.scope.principal_id == scope.principal_id
             and retriever.scope.subject_id == scope.subject_id
             and retriever.scope.corpus_revision == scope.corpus_revision
             and retriever.scope.embedding_space_hash == scope.embedding_space_hash,
             "scope_changed")
    ids = tuple(item.source.chunk_id for item in selections)
    _require(len(set(ids)) == 4, "candidate_binding_invalid")
    current = {source.chunk_id: source for source in await retriever.read_current_sources(ids)}
    pages = await retriever.read_current_source_pages(ids, max_pages=4, max_tokens=8192)
    _require(len(current) == len(pages) == 4, "current_sources_unavailable")
    seen = set()
    for ordinal, (item, frozen) in enumerate(zip(selections, case.candidates, strict=True), 1):
        source = current.get(item.source.chunk_id)
        _require(type(frozen) is FrozenCandidate and source is not None
                 and frozen.id == f"S{ordinal:02d}"
                 and all(isinstance(getattr(frozen, key), UUID) and getattr(frozen, key).int > 0 for key in
                         ("document_id", "content_revision_id", "index_revision_id"))
                 and all(getattr(source, key) == getattr(item.source, key) for key in (
                     "document_id", "content_revision_id", "index_revision_id", "page_number", "content",
                     "section", "embedding_space_hash", "corpus_revision"))
                 and all(getattr(source, key) == getattr(frozen, key) for key in (
                     "document_id", "content_revision_id", "index_revision_id", "page_number"))
                 and source.corpus_revision == scope.corpus_revision
                 and source.embedding_space_hash == scope.embedding_space_hash
                 and item.source_kind == "canonical_page" and type(item.page_content) is str
                 and pages.get(item.source.chunk_id) == item.page_content
                 and type(frozen.page_number) is int and frozen.page_number > 0
                 and type(item.start_offset) is int and type(item.end_offset) is int
                 and item.start_offset == frozen.start_offset and item.end_offset == frozen.end_offset
                 and 0 <= item.start_offset < item.end_offset <= len(item.page_content)
                 and item.end_offset - item.start_offset <= 480
                 and all(type(getattr(frozen, name)) is str and _SHA.fullmatch(getattr(frozen, name)) for name in
                         ("pdf_sha256", "cue_sha256", "png_sha256", "page_text_sha256"))
                 and sha256(item.quote.encode()).hexdigest() == frozen.cue_sha256
                 and sha256(item.page_content.encode()).hexdigest() == frozen.page_text_sha256,
                 "candidate_binding_invalid")
        page = (source.document_id, source.page_number)
        _require(page not in seen, "duplicate_source_page")
        seen.add(page)
    return retriever, raw, binding


async def prepare_dispatch_proof_v7(
    db: AsyncSession, *, settings: Settings, scope: DispatchScope, case: FrozenDispatchCase,
    selections: tuple[RelatedExcerptSelection, ...], pins: GuardPins,
    services: GuardServices | None = None, clock: Callable[[], datetime] = _now,
) -> RenderedDispatchProof:
    """Authenticate/render and compare exact frozen request in a first transaction."""
    try:
        source_code = verify_code_pins(pins)
        identity = _case_identity(case, scope, pins)
        dependencies = _dependencies(services, settings)
        _settings(settings, scope)
        await _fresh_transaction(db)
        now = clock()
        retriever, raw, binding = await _current(db, services=dependencies, settings=settings,
            scope=scope, case=case, pins=pins, selections=selections, now=now)
        prepared = await dependencies.prepare(db, settings=settings, retriever=retriever,
            subject_id=scope.subject_id, question=case.question, selections=selections,
            snapshot=case.snapshot, checked_at=now, raw_navigation_query=raw,
            preceding_question=case.preceding_question, anchor=binding.anchor)
        _require(contract.canonical(prepared.request) == case.request_bytes, "reviewed_request_changed")
        # Whole-wire equality includes source aliases, context, cue offsets and
        # exact PNG bytes; no quote-only or image-digest shortcut is accepted.
        wire_parts = prepared.request["contents"][0]["parts"]
        _require(len(wire_parts) == 9, "reviewed_request_changed")
        for ordinal, frozen in enumerate(case.candidates):
            candidate = json.loads(wire_parts[1 + ordinal * 2]["text"])
            image = base64.b64decode(wire_parts[2 + ordinal * 2]["inline_data"]["data"], validate=True)
            _require(candidate["id"] == frozen.id and candidate["page"] == frozen.page_number
                     and candidate["pdf_sha256"] == frozen.pdf_sha256
                     and candidate["page_text_sha256"] == frozen.page_text_sha256
                     and sha256(image).hexdigest() == frozen.png_sha256, "reviewed_request_changed")
        _require(verify_code_pins(pins) == source_code, "runtime_code_changed")
        return RenderedDispatchProof(identity, source_code, pins.request_sha256, services is None,
                                     prepared.bindings, _SEAL)
    except DispatchGuardError:
        raise
    except Exception:
        raise DispatchGuardError("dispatch_preparation_unavailable") from None


def require_fresh_receipt(receipt: dict, *, now: datetime, trial_id: UUID, dispatch_nonce: UUID,
                          request_sha256: str, purpose: str = "provider_dispatch",
                          _allow_test_interfaces: bool = False) -> None:
    """Host must call immediately before its physical HTTP; not an approval."""
    try:
        checked = datetime.fromisoformat(receipt["checked_at_utc"])
        _require(_utc(checked) and _utc(now) and 0 <= (now - checked).total_seconds() <= MAX_FRESH_SECONDS
                 and receipt["schema"] == SCHEMA and receipt["purpose"] == purpose
                 and receipt["trial_id"] == str(trial_id) and receipt["dispatch_nonce"] == str(dispatch_nonce)
                 and receipt["request_sha256"] == request_sha256
                 and (receipt["production_interfaces"] is True or _allow_test_interfaces is True)
                 and receipt["transaction_read_only"] is True
                 and receipt["ask_enabled"] is False and receipt["source_judge_enabled"] is False
                 and receipt["after_quota_wait"] is True, "dispatch_guard_stale_or_unbound")
    except DispatchGuardError:
        raise
    except Exception:
        raise DispatchGuardError("dispatch_guard_stale_or_unbound") from None


def require_dispatch_receipt_binding(
    receipt_bytes: bytes, *, receipt_sha256: str, now: datetime, trial_id: UUID,
    dispatch_nonce: UUID, scope: DispatchScope, case: FrozenDispatchCase, pins: GuardPins,
    selected_ids: tuple[str, ...] | None = None,
) -> dict:
    """Strict host boundary for the immediate callback's SHA-bound receipt.

    The host obtains the bytes and SHA from its trusted, just-completed guard
    callback, never from a model or an old Temp receipt. This function grants
    no permission to execute a provider request and creates no durable ledger.
    """
    try:
        _require(type(receipt_bytes) is bytes and 0 < len(receipt_bytes) <= 16 * 1024
                 and type(receipt_sha256) is str and _SHA.fullmatch(receipt_sha256)
                 and sha256(receipt_bytes).hexdigest() == receipt_sha256,
                 "dispatch_receipt_binding_invalid")
        receipt = json.loads(receipt_bytes, object_pairs_hook=contract.v2._unique,
                             parse_constant=contract.v2._reject_constant)
        _require(type(receipt) is dict and contract.canonical(receipt) == receipt_bytes
                 and set(receipt) == {
                     "schema", "policy", "contract", "purpose", "case_id", "trial_id", "dispatch_nonce",
                     "checked_at_utc", "bridge_sha256", "runtime_sha256", "request_sha256", "admission_sha256",
                     "guard_code_sha256", "source_code_sha256", "scope", "admission_basis",
                     "persisted_job_authorized", "transaction_read_only", "production_interfaces",
                     "ask_enabled", "source_judge_enabled", "after_quota_wait", "selected_ids",
                     "browser_page_open_observed", "sources"}, "dispatch_receipt_binding_invalid")
        _case_identity(case, scope, pins)
        source_code = verify_code_pins(pins)
        purpose = "provider_dispatch" if selected_ids is None else "post_selection_pdf_read"
        require_fresh_receipt(receipt, now=now, trial_id=trial_id, dispatch_nonce=dispatch_nonce,
                              request_sha256=pins.request_sha256, purpose=purpose)
        _require(receipt["policy"] == POLICY and receipt["contract"] == CONTRACT
                 and receipt["case_id"] == case.case_id
                 and contract.canonical(receipt["scope"]) == contract.canonical(scope.identity())
                 and receipt["bridge_sha256"] == pins.bridge_sha256
                 and receipt["runtime_sha256"] == pins.runtime_sha256
                 and receipt["admission_sha256"] == pins.admission_sha256
                 and receipt["guard_code_sha256"] == pins.guard_code_sha256
                 and receipt["source_code_sha256"] == source_code
                 and receipt["admission_basis"] == "frozen_case_simulation_not_persisted_history"
                 and receipt["persisted_job_authorized"] is False
                 and receipt["browser_page_open_observed"] is False
                 and receipt["selected_ids"] == (list(selected_ids) if selected_ids is not None else None)
                 and type(receipt["sources"]) is list and len(receipt["sources"]) == 4,
                 "dispatch_receipt_binding_invalid")
        for actual, frozen in zip(receipt["sources"], case.candidates, strict=True):
            expected = {key: str(getattr(frozen, key)) if key.endswith("_id") and key != "id"
                        else getattr(frozen, key) for key in (
                "id", "document_id", "content_revision_id", "index_revision_id", "page_number",
                "pdf_sha256", "cue_sha256", "png_sha256", "page_text_sha256")}
            expected.update({key: True for key in ("current_authorized", "published", "index_ready",
                "current_revision", "original_pdf_authenticated", "page_association_valid")})
            _require(type(actual) is dict and contract.canonical(actual) == contract.canonical(expected),
                     "dispatch_receipt_binding_invalid")
        return receipt
    except DispatchGuardError:
        raise
    except Exception:
        raise DispatchGuardError("dispatch_receipt_binding_invalid") from None


async def verify_private_visual_dispatch_v7(
    db: AsyncSession, *, settings: Settings, scope: DispatchScope, case: FrozenDispatchCase,
    selections: tuple[RelatedExcerptSelection, ...], pins: GuardPins, proof: RenderedDispatchProof,
    trial_id: UUID, dispatch_nonce: UUID, after_quota_wait: bool,
    selected_ids: tuple[str, ...] | None = None,
    services: GuardServices | None = None, clock: Callable[[], datetime] = _now,
) -> dict:
    """Fresh final grant/archive check; selected IDs mean a new post-result read.

    The caller must roll back the rendering transaction before this function.
    It begins no transaction and commits/rolls back nothing. Every candidate is
    rechecked even when only a subset is selected. Post-result correctness here
    proves current backend PDF/page association, not browser canvas rendering.
    """
    try:
        _require(isinstance(trial_id, UUID) and trial_id.version == 4
                 and isinstance(dispatch_nonce, UUID) and dispatch_nonce.version == 4
                 and after_quota_wait is True, "dispatch_identity_invalid")
        source_code = verify_code_pins(pins)
        identity = _case_identity(case, scope, pins)
        dependencies = _dependencies(services, settings)
        _settings(settings, scope)
        _require(type(proof) is RenderedDispatchProof and proof._seal is _SEAL
                 and type(proof.production_interfaces) is bool
                 and proof.case_identity_sha256 == identity and proof.source_code_sha256 == source_code
                 and proof.request_sha256 == pins.request_sha256, "render_proof_unbound")
        checked = clock()
        _require(_utc(checked), "guard_time_invalid")
        await _fresh_transaction(db)
        await _current(db, services=dependencies, settings=settings, scope=scope, case=case,
                       pins=pins, selections=selections, now=checked)
        await dependencies.check_bindings(db, proof.bindings)
        archive_shas = {}
        from app.models.knowledge import SubjectDocumentPdf
        for binding in proof.bindings:
            pdf = await db.get(SubjectDocumentPdf, binding.content_revision_id)
            _require(pdf is not None and pdf.subject_id == scope.subject_id
                     and pdf.document_id == binding.document_id and pdf.source_sha256 == binding.source_sha256
                     and pdf.page_count == binding.page_count, "current_pdf_unavailable")
            data = await dependencies.read_archive(db, settings=settings, pdf=pdf)
            _require(type(data) is bytes and sha256(data).hexdigest() == binding.source_sha256,
                     "current_pdf_unavailable")
            archive_shas[binding.content_revision_id] = (binding.source_sha256, binding.page_count)
        _require(set(archive_shas) == {candidate.content_revision_id for candidate in case.candidates},
                 "current_pdf_unavailable")
        for candidate in case.candidates:
            sha, count = archive_shas[candidate.content_revision_id]
            _require(sha == candidate.pdf_sha256 and 1 <= candidate.page_number <= count,
                     "current_pdf_unavailable")
        issued = tuple(row.id for row in case.candidates)
        if selected_ids is not None:
            _require(type(selected_ids) is tuple and len(selected_ids) <= 3
                     and len(set(selected_ids)) == len(selected_ids)
                     and all(type(value) is str and value in issued for value in selected_ids),
                     "selected_source_invalid")
        _require(verify_code_pins(pins) == source_code, "runtime_code_changed")
        receipt = {"schema": SCHEMA, "policy": POLICY, "contract": CONTRACT,
            "purpose": "provider_dispatch" if selected_ids is None else "post_selection_pdf_read",
            "case_id": case.case_id, "trial_id": str(trial_id), "dispatch_nonce": str(dispatch_nonce),
            "checked_at_utc": checked.isoformat(), "bridge_sha256": pins.bridge_sha256,
            "runtime_sha256": pins.runtime_sha256, "request_sha256": pins.request_sha256,
            "admission_sha256": pins.admission_sha256, "guard_code_sha256": pins.guard_code_sha256,
            "source_code_sha256": source_code, "scope": scope.identity(),
            "admission_basis": "frozen_case_simulation_not_persisted_history",
            "persisted_job_authorized": False, "transaction_read_only": True,
            "production_interfaces": proof.production_interfaces is True and services is None,
            "ask_enabled": False, "source_judge_enabled": False, "after_quota_wait": True,
            "selected_ids": list(selected_ids) if selected_ids is not None else None,
            "browser_page_open_observed": False,
            "sources": [{**{key: str(getattr(row, key)) if key.endswith("_id") and key != "id"
                            else getattr(row, key) for key in (
                "id", "document_id", "content_revision_id", "index_revision_id", "page_number",
                "pdf_sha256", "cue_sha256", "png_sha256", "page_text_sha256")},
                "current_authorized": True, "published": True, "index_ready": True,
                "current_revision": True, "original_pdf_authenticated": True,
                "page_association_valid": True} for row in case.candidates]}
        require_fresh_receipt(receipt, now=clock(), trial_id=trial_id, dispatch_nonce=dispatch_nonce,
                              request_sha256=pins.request_sha256, purpose=receipt["purpose"],
                              _allow_test_interfaces=receipt["production_interfaces"] is False)
        return receipt
    except DispatchGuardError:
        raise
    except Exception:
        raise DispatchGuardError("dispatch_guard_unavailable") from None
