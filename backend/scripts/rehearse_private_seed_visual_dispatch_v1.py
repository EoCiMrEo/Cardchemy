"""Keyless seed14 binding/current lookup; explicitly rolled-back read-only SQL."""
from __future__ import annotations
from hashlib import sha256
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from uuid import UUID
REPO = Path(__file__).resolve().parents[2]
if Path("/app/app/__init__.py").is_file():
    sys.path.insert(0, "/app")
    import app
sys.path.insert(0, str(REPO / "scripts"))
import prepare_private_seed_visual_trial_v1 as preparation
import private_seed_visual_dispatch_guard_v1 as guard

def bind_cases(prepared, packet, code):
    scope = guard.DispatchScope(UUID(packet["principal_id"]), UUID(packet["subject_id"]), **packet["scope"])
    pairs = []
    for frozen, row in zip(prepared.cases, packet["cases"], strict=True):
        sources = json.loads(frozen.sources_bytes)
        candidates = tuple(guard.FrozenCandidate(source["id"], UUID(local["document_id"]), UUID(local["content_revision_id"]),
            UUID(local["index_revision_id"]), local["page_number"], local["start_offset"], local["end_offset"],
            source["pdf_sha256"], source["cue_sha256"], source["png_sha256"], source["page_text_sha256"])
            for source, local in zip(sources, row["candidates"], strict=True))
        snapshot = preparation.scorer._snapshot(row["question_context"]["admission"])
        case = guard.FrozenDispatchCase(row["case_id"], row["question"], frozen.request_bytes, snapshot, candidates,
            row["previous_turn"] if snapshot.preceding is not None else None)
        pins = guard.GuardPins(prepared.bridge_sha256, prepared.runtime_sha256, frozen.request_sha256,
            frozen.admission_sha256, sha256(Path(guard.__file__).read_bytes()).hexdigest(), code)
        pairs.append((case, pins))
    preparation.require(tuple(case.case_id for case, _ in pairs) == preparation.CASE_IDS, "case_count_changed")
    return scope, tuple(pairs)

async def current_selections(db, scope, case):
    from sqlalchemy import select
    from app.ai.related_evidence import RelatedExcerptSelection
    from app.models.knowledge import SubjectDocumentChunk
    from app.services.knowledge_retrieval import KnowledgeRetriever, SOURCE_NAVIGATION_RETRIEVAL_POLICY
    from app.ai.source_navigation import navigation_query_v4
    await guard._fresh_transaction(db)
    retriever = await KnowledgeRetriever.authorize(db, principal=SimpleNamespace(id=scope.principal_id),
        subject_id=scope.subject_id, query=navigation_query_v4(case.question, ()) or case.question,
        document_ids=tuple(dict.fromkeys(row.document_id for row in case.candidates)),
        limit=SOURCE_NAVIGATION_RETRIEVAL_POLICY.max_results, policy=SOURCE_NAVIGATION_RETRIEVAL_POLICY)
    preparation.require(retriever.scope.corpus_revision == scope.corpus_revision
        and retriever.scope.embedding_space_hash == scope.embedding_space_hash, "scope_changed")
    ids = []
    for source in case.candidates:
        chunk = await db.scalar(select(SubjectDocumentChunk.id).where(
            SubjectDocumentChunk.subject_id == scope.subject_id, SubjectDocumentChunk.document_id == source.document_id,
            SubjectDocumentChunk.content_revision_id == source.content_revision_id,
            SubjectDocumentChunk.index_revision_id == source.index_revision_id, SubjectDocumentChunk.page_number == source.page_number,
            SubjectDocumentChunk.embedding_space_hash == scope.embedding_space_hash,
        ).order_by(SubjectDocumentChunk.chunk_index, SubjectDocumentChunk.id).limit(1))
        preparation.require(chunk is not None, "current_anchor_unavailable"); ids.append(chunk)
    current = {row.chunk_id: row for row in await retriever.read_current_sources(ids)}
    pages = await retriever.read_current_source_pages(ids, max_pages=4, max_tokens=8192)
    preparation.require(len(current) == len(pages) == len(case.candidates), "current_sources_unavailable")
    return tuple(RelatedExcerptSelection(current[chunk], source.start_offset, source.end_offset,
        source_kind="canonical_page", page_content=pages[chunk]) for chunk, source in zip(ids, case.candidates, strict=True))

async def rehearse(directory):
    """Actual keyless read-only rehearsal, separately resource-fenced by host.

    Does not consume or create provider approval/claim/intent/usage records. A
    fresh receipt with an empty hypothetical selection grants no display or
    quality credit; it only checks current source/PDF/context associations.
    """
    import asyncio
    from datetime import datetime, timezone
    from uuid import uuid4
    import launch_private_seed_visual_trial_v1 as host
    import private_seed_visual_trial_entry_v1 as entry
    import execute_private_seed_visual_trial_v1 as executor
    manifest, prepared, bound = host.validate_stage(directory, image=True)
    settings = entry.keyless_settings(Path("/tmp/output"), bound)
    interfaces = executor.production_interfaces(settings)
    checked = []
    trial = uuid4()
    try:
        async with asyncio.timeout(600):
            for case, pins in zip(bound.cases, bound.pins, strict=True):
                selections = await executor._transaction(interfaces,
                    lambda db: current_selections(db, bound.scope, case), executor.MAX_ANCHOR_SECONDS)
                proof = await executor._transaction(interfaces, lambda db: guard.prepare_dispatch_proof_seed_v1(db,
                    settings=settings, scope=bound.scope, case=case, selections=selections, pins=pins), executor.MAX_RENDER_SECONDS)
                nonce = uuid4()
                async def final(db, selected=None):
                    return await guard.verify_private_visual_dispatch_seed_v1(db, settings=settings, scope=bound.scope,
                        case=case, selections=selections, pins=pins, proof=proof, trial_id=trial, dispatch_nonce=nonce,
                        after_quota_wait=True, selected_ids=selected)
                receipt = await executor._transaction(interfaces, final, executor.MAX_GUARD_SECONDS)
                guard.require_dispatch_receipt_binding(preparation.canonical(receipt),
                    receipt_sha256=preparation.digest(preparation.canonical(receipt)), now=datetime.now(timezone.utc),
                    trial_id=trial, dispatch_nonce=nonce, scope=bound.scope, case=case, pins=pins)
                selected = await executor._transaction(interfaces, lambda db: final(db, ()), executor.MAX_GUARD_SECONDS)
                guard.require_dispatch_receipt_binding(preparation.canonical(selected),
                    receipt_sha256=preparation.digest(preparation.canonical(selected)), now=datetime.now(timezone.utc),
                    trial_id=trial, dispatch_nonce=nonce, scope=bound.scope, case=case, pins=pins, selected_ids=())
                checked.append({"case_id": case.case_id, "candidate_count": len(case.candidates),
                    "request_sha256": pins.request_sha256, "fresh_read_only_guards": True})
    finally:
        await interfaces.close()
    return {"schema": "private_seed_visual_dispatch_rehearsal_v1", "status": "rehearsal_passed",
        "stage_sha256": host.digest(host.canonical(manifest)), "cases": checked, "provider_calls": 0,
        "database_writes": 0, "credentials_read": False, "hypothetical_empty_selection_only": True,
        "browser_page_open_observed": False, "release_gate_passed": False}

def main(argv=None):
    import argparse
    import asyncio
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--rehearse", type=Path)
    args = parser.parse_args(argv)
    if not args.rehearse:
        result, code = {"status": "unexecuted", "provider_calls": 0, "database_writes": 0}, 0
    else:
        try: result, code = asyncio.run(rehearse(args.rehearse)), 0
        except Exception: result, code = {"status": "keyless_rehearsal_refused", "provider_calls": 0, "database_writes": 0}, 2
    print(json.dumps(result, sort_keys=True)); return code

if __name__ == "__main__":
    raise SystemExit(main())
