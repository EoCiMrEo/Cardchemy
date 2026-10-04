"""Invented SQL/archive/render contracts; no service, key or provider execution."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys
import subprocess
from types import SimpleNamespace
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import private_visual_dispatch_guard_v7 as guard

from app.ai import source_judgment_visual_v3 as contract
from app.config import Settings
from app.models.knowledge import embedding_space_hash
from app.services import source_visual_preparation as visual
from app.services.source_visual_preparation_v3 import prepare_visual_sources_v3
from app.services.knowledge_pdf_renderer import RenderedPdfPage
from app.services.knowledge_retrieval import KnowledgeScopeUnavailable
from tests.test_source_judgment_visual import png
from tests.test_source_judgment_worker import _Retriever, _selection


class Db:
    def __init__(self, pdfs, revisions):
        self.pdfs, self.revisions = pdfs, revisions
        self.statements = []
        self.new, self.dirty, self.deleted = (), (), ()
        self.autoflush, self.begun, self.expired = False, True, 0
        self.read_only, self.isolation = "on", "repeatable read"
        self.prior_query = False

    def in_transaction(self):
        return self.begun

    def expire_all(self):
        self.expired += 1

    async def execute(self, statement):
        self.statements.append(str(statement))
        if self.prior_query:
            raise RuntimeError("invented SQL cannot change an already observed snapshot")

    async def scalar(self, statement):
        self.statements.append(str(statement))
        return self.read_only if str(statement) == "SHOW transaction_read_only" else self.isolation

    async def get(self, model, identity):
        return (self.pdfs if model is visual.SubjectDocumentPdf else self.revisions).get(identity)

    async def commit(self):
        pytest.fail("guard must not commit")

    async def rollback(self):
        pytest.fail("rollback belongs to host")


@pytest.fixture
async def fixture(monkeypatch):
    # Historical v7 helper remains pinned; current Settings now advertises v8.
    # Inject only the invented old profile instead of widening its runtime gate.
    monkeypatch.setattr(guard, "ASK_REQUIRED_RELEASE_POLICY_VERSION", guard.POLICY)
    monkeypatch.setattr(Settings, "rag_source_judge_contract_version",
                        property(lambda _self: guard.CONTRACT))
    now = datetime.now(timezone.utc)
    settings = Settings(_env_file=None, environment="development", rag_ask_enabled=False,
        rag_source_judge_provider_enabled=False, flashcard_ai_api_key=None, rag_ai_api_key=None,
        rag_embedding_api_key=None, rag_source_judge_api_key=None)
    space = embedding_space_hash(settings.rag_embedding_space_identity)
    principal, subject = uuid4(), uuid4()
    scope = guard.DispatchScope(principal, subject, 3, space)
    selections, pdfs, revisions, archives = [], {}, {}, {}
    for document in range(2):
        document_id, revision_id, index_id = uuid4(), uuid4(), uuid4()
        archive = b"%PDF-invented, never sent to a renderer " + bytes([document])
        source_sha = sha256(archive).hexdigest()
        archives[revision_id] = archive
        pdfs[revision_id] = SimpleNamespace(document_id=document_id, subject_id=subject,
            source_sha256=source_sha, page_count=2, content_revision_id=revision_id)
        revisions[revision_id] = SimpleNamespace(document_id=document_id, subject_id=subject,
            source_sha256=source_sha, actual_page_count=2, status="ready", is_active=True,
            reviewed_at=now, published_at=now)
        for page in (1, 2):
            item = _selection(page)
            selections.append(replace(item, source=replace(item.source, document_id=document_id,
                content_revision_id=revision_id, index_revision_id=index_id, corpus_revision=3,
                embedding_space_hash=space)))
    selections = tuple(selections)
    retriever = _Retriever(tuple(item.source for item in selections))
    retriever.scope = SimpleNamespace(principal_id=principal, subject_id=subject,
        corpus_revision=3, embedding_space_hash=space)
    calls = []
    async def authorize(db, **kwargs):
        calls.append(kwargs)
        return retriever
    async def archive(db, *, pdf, **kwargs):
        return archives[pdf.content_revision_id]
    async def render(data, source_sha, pages):
        raw = png()
        return tuple(RenderedPdfPage(page, source_sha, raw, sha256(raw).hexdigest(),
                                     2, 2, "c" * 64) for page in pages)
    monkeypatch.setattr(visual, "read_complete_pdf_archive", archive)
    monkeypatch.setattr(visual, "_render", render)
    services = guard.GuardServices(authorize=authorize, read_archive=archive)
    question = "What is Bluebird encoding?"
    snapshot = contract.SubjectAdmissionSnapshot(contract.AdmissionUserMessage(uuid4(), principal,
        uuid4(), subject, sha256(question.encode()).hexdigest(), now - timedelta(seconds=1),
        now + timedelta(days=1)), None, 3, space, now, True)
    prepared = await prepare_visual_sources_v3(Db(pdfs, revisions), settings=settings,
        retriever=retriever, subject_id=subject, question=question, selections=selections,
        snapshot=snapshot, checked_at=now, raw_navigation_query=question)
    frozen = tuple(guard.FrozenCandidate(f"S{n:02}", item.source.document_id,
        item.source.content_revision_id, item.source.index_revision_id, item.source.page_number,
        item.start_offset, item.end_offset, pdfs[item.source.content_revision_id].source_sha256,
        sha256(item.quote.encode()).hexdigest(), sha256(png()).hexdigest(),
        sha256(item.page_content.encode()).hexdigest()) for n, item in enumerate(selections, 1))
    body = contract.canonical(prepared.request)
    case = guard.FrozenDispatchCase("T01", question, body, snapshot, frozen)
    code = {relative: sha256((guard.REPO_ROOT / relative).read_bytes()).hexdigest()
            for relative in guard.REQUIRED_CODE_PATHS}
    pins = guard.GuardPins("b" * 64, "d" * 64, sha256(body).hexdigest(),
        contract.admission_identity(snapshot, checked_at=now), sha256(Path(guard.__file__).read_bytes()).hexdigest(), code)
    return SimpleNamespace(now=now, settings=settings, scope=scope, case=case, pins=pins,
        selections=selections, services=services, retriever=retriever, pdfs=pdfs, revisions=revisions,
        archives=archives, calls=calls, db=lambda: Db(pdfs, revisions))


async def proof(f):
    return await guard.prepare_dispatch_proof_v7(f.db(), settings=f.settings, scope=f.scope,
        case=f.case, selections=f.selections, pins=f.pins, services=f.services, clock=lambda: f.now)


async def verify(f, prepared=None, **changes):
    args = dict(settings=f.settings, scope=f.scope, case=f.case, selections=f.selections,
        pins=f.pins, proof=prepared or await proof(f), services=f.services, clock=lambda: f.now,
        trial_id=uuid4(), dispatch_nonce=uuid4(), after_quota_wait=True)
    args.update(changes)
    return await guard.verify_private_visual_dispatch_v7(f.db(), **args)


@pytest.mark.asyncio
async def test_exact_current_source_render_and_fresh_final_read_are_separate(fixture):
    f = fixture
    render_db, final_db = f.db(), f.db()
    prepared = await guard.prepare_dispatch_proof_v7(render_db, settings=f.settings, scope=f.scope,
        case=f.case, selections=f.selections, pins=f.pins, services=f.services, clock=lambda: f.now)
    trial, nonce = uuid4(), uuid4()
    result = await guard.verify_private_visual_dispatch_v7(final_db, settings=f.settings, scope=f.scope,
        case=f.case, selections=f.selections, pins=f.pins, proof=prepared, services=f.services,
        trial_id=trial, dispatch_nonce=nonce, after_quota_wait=True, clock=lambda: f.now)
    assert render_db.statements == final_db.statements == [
        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY",
        "SHOW transaction_read_only", "SHOW transaction_isolation"]
    assert render_db.expired == final_db.expired == 1
    assert len(f.calls) == 2 and len(result["sources"]) == 4
    assert result["purpose"] == "provider_dispatch" and result["selected_ids"] is None
    assert result["production_interfaces"] is False
    assert result["persisted_job_authorized"] is False and result["browser_page_open_observed"] is False
    for row in result["sources"]:
        assert all(row[key] is True for key in ("current_authorized", "published", "index_ready",
            "current_revision", "original_pdf_authenticated", "page_association_valid"))
    encoded = json.dumps(result)
    assert f.case.question not in encoded and f.selections[0].quote not in encoded
    assert "png_bytes" not in encoded and "preceding_question" not in encoded


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["unpublish", "inactive", "pdf_sha", "page_count", "deleted_pdf"])
async def test_change_after_render_refuses_before_dispatch(fixture, mutation):
    f = fixture
    prepared = await proof(f)
    revision_id = next(iter(f.revisions))
    if mutation == "unpublish":
        f.revisions[revision_id].published_at = None
    elif mutation == "inactive":
        f.revisions[revision_id].is_active = False
    elif mutation == "pdf_sha":
        f.pdfs[revision_id].source_sha256 = "e" * 64
    elif mutation == "page_count":
        f.pdfs[revision_id].page_count = 1
    else:
        del f.pdfs[revision_id]
    with pytest.raises(guard.DispatchGuardError):
        await verify(f, prepared)


@pytest.mark.asyncio
async def test_revoked_owner_or_enrollment_after_render_refuses(fixture):
    f = fixture
    prepared = await proof(f)
    async def revoked(*args, **kwargs):
        raise KnowledgeScopeUnavailable()
    f.services = replace(f.services, authorize=revoked)
    with pytest.raises(guard.DispatchGuardError, match="dispatch_guard_unavailable"):
        await verify(f, prepared)


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["corpus", "space", "subject", "principal"])
async def test_authorization_scope_is_freshly_bound(fixture, mutation):
    f = fixture
    prepared = await proof(f)
    key, value = {"corpus": ("corpus_revision", 4), "space": ("embedding_space_hash", "e" * 64),
        "subject": ("subject_id", uuid4()), "principal": ("principal_id", uuid4())}[mutation]
    setattr(f.retriever.scope, key, value)
    with pytest.raises(guard.DispatchGuardError, match="scope_changed"):
        await verify(f, prepared)


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["cue", "page", "document", "revision", "index", "page_text"])
async def test_candidate_or_exact_window_mutation_refuses(fixture, mutation):
    f = fixture
    prepared = await proof(f)
    first = f.selections[0]
    if mutation == "cue":
        first = replace(first, start_offset=first.start_offset + 1)
    elif mutation == "page_text":
        first = replace(first, page_content=first.page_content + " Different text.")
    else:
        key = {"page": "page_number", "document": "document_id", "revision": "content_revision_id",
               "index": "index_revision_id"}[mutation]
        first = replace(first, source=replace(first.source, **{key: 3 if mutation == "page" else uuid4()}))
    with pytest.raises(guard.DispatchGuardError, match="candidate_binding_invalid"):
        await verify(f, prepared, selections=(first, *f.selections[1:]))


@pytest.mark.asyncio
async def test_authenticating_full_archive_is_not_a_metadata_shortcut(fixture):
    f = fixture
    prepared = await proof(f)
    revision_id = next(iter(f.archives))
    f.archives[revision_id] += b"tampered encrypted archive result"
    with pytest.raises(guard.DispatchGuardError, match="current_pdf_unavailable"):
        await verify(f, prepared)


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["warning", "image"])
async def test_frozen_whole_request_and_png_are_exact(fixture, mutation):
    f = fixture
    request = json.loads(f.case.request_bytes)
    if mutation == "warning":
        request["systemInstruction"]["parts"][0]["text"] += " changed trusted contract"
    else:
        request["contents"][0]["parts"][2]["inline_data"]["data"] = "changed"
    raw = contract.canonical(request)
    f.case = replace(f.case, request_bytes=raw)
    f.pins = replace(f.pins, request_sha256=sha256(raw).hexdigest())
    with pytest.raises(guard.DispatchGuardError, match="reviewed_request_changed"):
        await proof(f)


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["no_transaction", "prior_read", "autoflush", "dirty", "read_write", "wrong_isolation"])
async def test_fresh_explicit_read_only_caller_transaction_is_required(fixture, mutation):
    f = fixture
    db = f.db()
    key, value = {"no_transaction": ("begun", False), "prior_read": ("prior_query", True),
        "autoflush": ("autoflush", True), "dirty": ("dirty", (object(),)),
        "read_write": ("read_only", "off"), "wrong_isolation": ("isolation", "read committed")}[mutation]
    setattr(db, key, value)
    with pytest.raises(guard.DispatchGuardError):
        await guard.prepare_dispatch_proof_v7(db, settings=f.settings, scope=f.scope,
            case=f.case, selections=f.selections, pins=f.pins, services=f.services, clock=lambda: f.now)


@pytest.mark.asyncio
@pytest.mark.parametrize("change", [{"rag_ask_enabled": True}, {"rag_source_judge_provider_enabled": True},
    {"rag_source_judge_provider_timeout_seconds": 60}, {"rag_embedding_api_key": "invented-forbidden"}])
async def test_settings_remain_off_and_credentials_are_not_in_guard(fixture, change):
    f = fixture
    f.settings = f.settings.model_copy(update=change)
    with pytest.raises(guard.DispatchGuardError, match="runtime_not_closed"):
        await proof(f)


@pytest.mark.asyncio
async def test_raw_clarity_cannot_be_forged_by_supplied_snapshot(fixture):
    f = fixture
    f.case = replace(f.case, question="How does it work?",
        snapshot=replace(f.case.snapshot, current=replace(f.case.snapshot.current,
            content_sha256=sha256(b"How does it work?").hexdigest())))
    f.pins = replace(f.pins, admission_sha256=contract.admission_identity(f.case.snapshot, checked_at=f.now))
    with pytest.raises(guard.DispatchGuardError):
        await proof(f)


@pytest.mark.asyncio
async def test_literal_followup_preserves_only_unique_strict_previous_subject(fixture):
    f = fixture
    question, previous = "How does it work?", f.case.question
    current = replace(f.case.snapshot.current, content_sha256=sha256(question.encode()).hexdigest())
    preceding = replace(current, message_id=uuid4(), content_sha256=sha256(previous.encode()).hexdigest(),
                        created_at=f.now - timedelta(seconds=2))
    snapshot = replace(f.case.snapshot, current=current, preceding=preceding, raw_question_clear=False)
    resolution = guard.resolve_subject_context(question, (("user", previous),), raw_navigation_query=None)
    prepared = await prepare_visual_sources_v3(f.db(), settings=f.settings, retriever=f.retriever,
        subject_id=f.scope.subject_id, question=question, selections=f.selections, snapshot=snapshot,
        checked_at=f.now, raw_navigation_query=None, preceding_question=previous, anchor=resolution.anchor)
    raw = contract.canonical(prepared.request)
    f.case = replace(f.case, question=question, snapshot=snapshot, preceding_question=previous, request_bytes=raw)
    f.pins = replace(f.pins, request_sha256=sha256(raw).hexdigest(),
                     admission_sha256=contract.admission_identity(snapshot, checked_at=f.now))
    result = await verify(f)
    assert len(result["sources"]) == 4
    envelope = json.loads(prepared.request["contents"][0]["parts"][0]["text"])
    assert envelope["referent_context"]["literal_subject"] == "Bluebird encoding"
    assert previous.encode() not in raw and previous not in json.dumps(result)


@pytest.mark.asyncio
async def test_render_proof_cannot_be_reused_for_other_bridge_or_runtime(fixture):
    f = fixture
    prepared = await proof(f)
    with pytest.raises(guard.DispatchGuardError, match="render_proof_unbound"):
        await verify(f, prepared, pins=replace(f.pins, bridge_sha256="f" * 64))


@pytest.mark.asyncio
async def test_final_checks_must_finish_within_five_seconds(fixture):
    f = fixture
    prepared = await proof(f)
    ticks = iter((f.now, f.now + timedelta(seconds=5, microseconds=1)))
    with pytest.raises(guard.DispatchGuardError, match="dispatch_guard_stale_or_unbound"):
        await verify(f, prepared, clock=lambda: next(ticks))


@pytest.mark.asyncio
async def test_fresh_receipt_cannot_be_replayed_with_another_nonce_or_late(fixture):
    f = fixture
    trial, nonce = uuid4(), uuid4()
    result = await verify(f, trial_id=trial, dispatch_nonce=nonce)
    with pytest.raises(guard.DispatchGuardError, match="dispatch_guard_stale_or_unbound"):
        guard.require_fresh_receipt(result, now=f.now, trial_id=trial, dispatch_nonce=nonce,
            request_sha256=f.pins.request_sha256)
    # The host's default boundary rejects test seams even when time/identity
    # match. The test-only opt-in isolates the age/nonce regression below.
    guard.require_fresh_receipt(result, now=f.now, trial_id=trial, dispatch_nonce=nonce,
        request_sha256=f.pins.request_sha256, _allow_test_interfaces=True)
    for now, bound_nonce in ((f.now + timedelta(seconds=6), nonce), (f.now, uuid4())):
        with pytest.raises(guard.DispatchGuardError, match="dispatch_guard_stale_or_unbound"):
            guard.require_fresh_receipt(result, now=now, trial_id=trial, dispatch_nonce=bound_nonce,
                request_sha256=f.pins.request_sha256, _allow_test_interfaces=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("ids", [("S01", "S02", "S03", "S04"), ("S01", "S01"), ("S99",)])
async def test_selected_page_read_rejects_bad_selection(fixture, ids):
    with pytest.raises(guard.DispatchGuardError, match="selected_source_invalid"):
        await verify(fixture, selected_ids=ids)


@pytest.mark.asyncio
async def test_post_result_selected_read_rechecks_entire_four_page_bundle(fixture):
    f = fixture
    prepared = await proof(f)
    selected = await verify(f, prepared, selected_ids=("S01", "S03"))
    assert selected["purpose"] == "post_selection_pdf_read"
    assert selected["selected_ids"] == ["S01", "S03"] and len(selected["sources"]) == 4
    f.revisions[f.selections[3].source.content_revision_id].published_at = None
    with pytest.raises(guard.DispatchGuardError):
        await verify(f, prepared, selected_ids=("S01",))


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["none", "scope", "runtime", "admission", "bridge", "index",
    "png", "page", "source_order", "production", "extra", "sha"])
async def test_host_binds_full_callback_receipt_not_only_request_and_time(fixture, mutation):
    f = fixture
    trial, nonce = uuid4(), uuid4()
    receipt = await verify(f, trial_id=trial, dispatch_nonce=nonce)
    # No service is executed in this parser test. A synthetic supplied receipt
    # marked production lets the regression target exact frozen identities.
    receipt["production_interfaces"] = True
    if mutation == "scope":
        receipt["scope"]["principal_id"] = str(uuid4())
    elif mutation in ("runtime", "admission", "bridge"):
        receipt[mutation + "_sha256"] = "f" * 64
    elif mutation == "index":
        receipt["sources"][0]["index_revision_id"] = str(uuid4())
    elif mutation == "png":
        receipt["sources"][0]["png_sha256"] = "f" * 64
    elif mutation == "page":
        receipt["sources"][0]["page_number"] = 2
    elif mutation == "source_order":
        receipt["sources"].reverse()
    elif mutation == "production":
        receipt["production_interfaces"] = False
    elif mutation == "extra":
        receipt["private_text"] = "invented unrelated content"
    raw = contract.canonical(receipt)
    expected_sha = sha256(raw).hexdigest() if mutation != "sha" else "f" * 64
    args = dict(receipt_sha256=expected_sha, now=f.now, trial_id=trial, dispatch_nonce=nonce,
                scope=f.scope, case=f.case, pins=f.pins)
    if mutation == "none":
        assert guard.require_dispatch_receipt_binding(raw, **args) == receipt
    else:
        with pytest.raises(guard.DispatchGuardError):
            guard.require_dispatch_receipt_binding(raw, **args)


@pytest.mark.parametrize("mutation", ["missing", "bad_sha", "traversal", "env_path", "guard_sha"])
def test_code_pins_are_complete_exact_and_code_only(fixture, mutation):
    f = fixture
    code = dict(f.pins.code_sha256)
    pins = f.pins
    if mutation == "missing":
        code.pop(next(iter(code)))
    elif mutation == "bad_sha":
        code[next(iter(code))] = "a" * 64
    elif mutation == "traversal":
        code["backend/../scripts/private.py"] = "a" * 64
    elif mutation == "env_path":
        code["backend/.env"] = "a" * 64
    else:
        pins = replace(pins, guard_code_sha256="a" * 64)
    with pytest.raises(guard.DispatchGuardError):
        guard.verify_code_pins(replace(pins, code_sha256=code))


def test_code_pins_copy_caller_mapping_before_async_work(fixture):
    code = dict(fixture.pins.code_sha256)
    pins = replace(fixture.pins, code_sha256=code)
    code.clear()
    assert guard.REQUIRED_CODE_PATHS <= set(pins.code_sha256)
    with pytest.raises(TypeError):
        pins.code_sha256["backend/app/config.py"] = "f" * 64


def test_code_pin_symlink_is_checked_before_resolving_original_path(fixture, monkeypatch):
    target = guard.REPO_ROOT / next(iter(fixture.pins.code_sha256))
    old = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda path: path == target or old(path))
    with pytest.raises(guard.DispatchGuardError, match="code_pins_invalid"):
        guard.verify_code_pins(fixture.pins)


def test_code_pins_portable_without_python312_windows_junction_api(fixture, monkeypatch):
    monkeypatch.delattr(Path, "is_junction", raising=False)
    assert guard.verify_code_pins(fixture.pins)


def test_import_is_inert_without_database_settings_or_operator_env_reads():
    # A new interpreter has no conftest/application cache. Deny every .env open
    # via audit hook before importing the guard; imports must stay definition-only.
    body = """
import pathlib, sys
sys.path.insert(0, sys.argv[1])
sys.path.insert(0, sys.argv[2])
def audit(event, args):
    if event == 'open' and isinstance(args[0], (str, bytes)) and pathlib.Path(args[0]).name == '.env':
        raise RuntimeError('operator env read forbidden')
sys.addaudithook(audit)
import private_visual_dispatch_guard_v7
assert 'app.database' not in sys.modules
assert 'app.services.knowledge_retrieval' not in sys.modules
print('guard_import_inert')
"""
    result = subprocess.run([sys.executable, "-I", "-c", body,
        str(guard.REPO_ROOT / "backend"), str(Path(guard.__file__).parent)],
        capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "guard_import_inert" and result.stderr == ""


def test_default_production_import_refuses_operator_env_mount(fixture, monkeypatch, tmp_path):
    (tmp_path / ".env").write_text("invented sentinel never read")
    monkeypatch.setattr(guard, "REPO_ROOT", tmp_path)
    with pytest.raises(guard.DispatchGuardError, match="operator_env_mount_forbidden"):
        guard._dependencies(None, fixture.settings)


def test_injected_interfaces_are_only_allowed_in_keyless_test_process(fixture, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    with pytest.raises(guard.DispatchGuardError, match="test_interfaces_forbidden"):
        guard._dependencies(fixture.services, fixture.settings)
