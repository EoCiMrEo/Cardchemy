"""Separate seed14 variable-slate guards; v8/private12 sources stay immutable.

The shape-specific functions below retain the v8 fresh read-only SQL, current
source authorization, immutable admission, whole-wire render and full original
archive authentication boundaries. Only 1--4 sources per case are permitted.
Shared immutable v8 function bodies have isolated globals, never monkeypatches.
"""
from __future__ import annotations
import base64,json,re
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from types import FunctionType,SimpleNamespace
from typing import Callable
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
import private_visual_dispatch_guard_v8 as base
from app.ai import source_judgment_visual_v5 as contract
SCHEMA="private_seed_visual_dispatch_guard_v1"
POLICY,CONTRACT,MAX_FRESH_SECONDS,REPO_ROOT=base.POLICY,base.CONTRACT,base.MAX_FRESH_SECONDS,base.REPO_ROOT
DispatchGuardError,DispatchScope,GuardPins,FrozenCandidate,FrozenDispatchCase,RenderedDispatchProof,GuardServices=(
 base.DispatchGuardError,base.DispatchScope,base.GuardPins,base.FrozenCandidate,base.FrozenDispatchCase,base.RenderedDispatchProof,base.GuardServices)
_require,_digest,_utc,_now,_SHA=base._require,base._digest,base._utc,base._now,base._SHA
_SEAL=object()
REQUIRED_CODE_PATHS=base.REQUIRED_CODE_PATHS | {"backend/scripts/private_visual_dispatch_guard_v8.py","backend/scripts/private_seed_visual_dispatch_guard_v1.py"}
def _shared(function):
 result=FunctionType(function.__code__,globals(),function.__name__,function.__defaults__,function.__closure__)
 result.__kwdefaults__=function.__kwdefaults__
 return result
_dependencies,_settings,_context,_fresh_transaction=base._dependencies,base._settings,base._context,base._fresh_transaction
verify_code_pins=_shared(base.verify_code_pins)
# Pin the original shared code as well as this adapter. __file__ now names this
# guard; the old frozen guard remains an explicit member of the code map.
from pathlib import PurePosixPath
from typing import Mapping
require_fresh_receipt=_shared(base.require_fresh_receipt)
def _case_identity(case: FrozenDispatchCase, scope: DispatchScope, pins: GuardPins) -> str:
    _require(type(case) is FrozenDispatchCase and type(case.case_id) is str
             and re.fullmatch(r"[A-Z][A-Z0-9_-]{1,31}", case.case_id) is not None
             and type(case.request_bytes) is bytes
             and 0 < len(case.request_bytes) <= contract.MAX_REQUEST_BYTES
             and sha256(case.request_bytes).hexdigest() == pins.request_sha256
             and type(case.candidates) is tuple and 1 <= len(case.candidates) <= 4,
             "frozen_case_invalid")
    return _digest({"case_id": case.case_id, "scope": scope.identity(),
        "request_sha256": pins.request_sha256, "admission_sha256": pins.admission_sha256,
        "bridge_sha256": pins.bridge_sha256, "runtime_sha256": pins.runtime_sha256,
        "candidates": [{name: str(getattr(row, name)) if name.endswith("_id") and name != "id"
                         else getattr(row, name) for name in FrozenCandidate.__dataclass_fields__}
                        for row in case.candidates]})

async def _current(db, *, services, settings, scope, case, pins, selections, now):
    from app.ai.related_evidence import RelatedExcerptSelection
    from app.services.knowledge_retrieval import SOURCE_NAVIGATION_RETRIEVAL_POLICY
    raw, binding, query = _context(case, scope, pins, now)
    _require(type(selections) is tuple and len(selections) == len(case.candidates)
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
    _require(len(set(ids)) == len(case.candidates), "candidate_binding_invalid")
    current = {source.chunk_id: source for source in await retriever.read_current_sources(ids)}
    pages = await retriever.read_current_source_pages(ids, max_pages=4, max_tokens=8192)
    _require(len(current) == len(pages) == len(case.candidates), "current_sources_unavailable")
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

async def prepare_dispatch_proof_seed_v1(
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
        _require(len(wire_parts) == 1 + 2 * len(case.candidates), "reviewed_request_changed")
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
                 and type(receipt["sources"]) is list and len(receipt["sources"]) == len(case.candidates),
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

async def verify_private_visual_dispatch_seed_v1(
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
