"""Invented seed14 wire, review, source guards and prospective custody only."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from hashlib import sha256
import io
import json
from pathlib import Path
import sys
from uuid import uuid4
from types import FunctionType
import pytest

sys.path[:0] = [str(Path(__file__).resolve().parents[2] / "scripts"), str(Path(__file__).resolve().parents[1] / "scripts")]
import prepare_private_seed_visual_trial_v1 as prep
import run_private_seed_visual_trial_v1 as custody
import private_seed_visual_dispatch_guard_v1 as guard
import execute_private_seed_visual_trial_v1 as executor
import launch_private_seed_visual_trial_v1 as host
import private_seed_visual_trial_entry_v1 as entry
from test_private_visual_trial_v8_preflight import synthetic as old_synthetic
from test_private_visual_dispatch_guard_v8 import fixture as old_guard_fixture
from test_execute_private_visual_trial_v8 import ControllerHarness
from test_private_visual_trial_v8_caller import Harness
from test_private_source_display_v8_score import NOW
from tests.test_source_visual_provider import response

def pin(raw): return sha256(raw).hexdigest()

def synthetic(monkeypatch):
    _, code, values, _ = old_synthetic(monkeypatch)
    for name in prep.EXTRA_CODE_PATHS:
        code[name] = (prep.REPO / name).read_bytes()
    runtime = {"schema": "private_current_v8_runtime_manifest", "actual_policy": prep.scorer.POLICY,
        "actual_contract": prep.scorer.CONTRACT, "image_sha256": "sha256:" + "a" * 64,
        "migration_heads": ["20261002_0033"], "runtime_profile": {"ask": False, "judge": False,
            "contract": prep.scorer.CONTRACT, "output": 4096, "required_policy": prep.scorer.POLICY, "thinking": "high", "timeout": 120.0},
        "runtime_source_hashes": {"app/ai/source_navigation.py": pin(code["backend/app/ai/source_navigation.py"])},
        "diagnostic_sha256": pin(b"invented diagnostic"), "scorer_sha256": pin(code["scripts/score_private_source_display_v8.py"]),
        "raw_projection_sha256": pin(code["scripts/navigation_raw_query_projection_v1.py"])}
    old = values["packet"]
    packet = {"schema": "private_seed_visual_v8_preparation_v1", "policy": prep.scorer.POLICY, "contract": prep.scorer.CONTRACT,
        "provider_calls": 0, "database_writes": 0, "principal_id": old["scope"]["principal_id"], "subject_id": old["scope"]["subject_id"],
        "scope": {k: old["scope"][k] for k in ("corpus_revision", "embedding_space_hash")}, "cases": []}
    labels = []
    for ordinal, cid in enumerate(prep.CASE_IDS):
        oldrow = old["cases"][ordinal % 12]
        request = deepcopy(oldrow["request"]); parts = request["contents"][0]["parts"]
        count = 1 if cid in ("U01", "U02") else 4
        parts[:] = parts[:1 + 2 * count]
        request["generationConfig"]["responseJsonSchema"] = prep.contract.v2.v1.response_schema([f"S{i:02}" for i in range(1, count + 1)])
        if count == 1:
            request["systemInstruction"]["parts"][0]["text"] = request["systemInstruction"]["parts"][0]["text"].replace("the four issued IDs", "every issued ID")
        wire_question = json.loads(parts[0]["text"])["question"]
        previous = oldrow["preceding_question"] or ""
        row = {"case_id": cid, "question": wire_question, "previous_turn": previous, "request": request,
            "question_context": {"admission": oldrow["admission_snapshot"],
                "admission_sha256": prep.contract.admission_identity(prep.scorer._snapshot(oldrow["admission_snapshot"]), checked_at=NOW),
                "current_question_sha256": pin(wire_question.encode())}, "candidates": [], "bindings": [],
            "evaluation_role": "bounded_wrong_source_control" if count == 1 else "exposed_source_control" if cid == "N12" else "exposed_seed",
            "require_empty_candidate_slate": count == 1, "corpus_absence_claim": False}
        labelrow = {"case_id": cid, "question_sha256": pin(wire_question.encode()), "previous_turn_sha256": pin(previous.encode()),
            "evaluation_role": row["evaluation_role"], "require_empty_candidate_slate": count == 1,
            "corpus_absence_claim": False, "expected_question_status": "clear", "candidates": []}
        for n in range(count):
            text = json.loads(parts[1 + 2*n]["text"]); local = oldrow["source_bindings"][n]
            page = " " * text["context_start"] + text["context"]
            text["page_text_sha256"] = pin(page.encode()); parts[1+2*n]["text"] = prep.canonical(text).decode()
            pagekey = local["document_id"] + ":" + str(text["page"])
            candidate = {"document_id": local["document_id"], "content_revision_id": local["content_revision_id"], "index_revision_id": str(uuid4()),
                "page_key": pagekey, "page_number": text["page"], "start_offset": text["cue_start"], "end_offset": text["cue_end"],
                "page_text": page, "page_sha256": pin(page.encode()), "cue_sha256": pin(text["cue"].encode())}
            row["candidates"].append(candidate)
            if not any(x["document_id"] == candidate["document_id"] for x in row["bindings"]):
                row["bindings"].append({"document_id": candidate["document_id"], "source_sha256": text["pdf_sha256"]})
            import base64
            labelrow["candidates"].append({"id": text["id"], "page_key": pagekey, "cue_sha256": candidate["cue_sha256"],
                "image_sha256": pin(base64.b64decode(parts[2+2*n]["inline_data"]["data"])), "pdf_sha256": text["pdf_sha256"],
                "source_integrity_verified": True, "page_useful": "No" if count == 1 else "Yes", "cue_useful": "No" if count == 1 else "Yes",
                "learning_category": "topic_only" if count == 1 else "direct"})
        packet["cases"].append(row); labels.append(labelrow)
    panel = prep.canonical({"invented": True}); source = prep.canonical(packet)
    review = {"schema": "private_seed_source_review_v8", "cases": labels, "source_preparation_sha256": pin(source),
        "panel_manifest_sha256": pin(panel), "model_outcomes_read": False, "independent_of_runtime_selection": True,
        "original_pdf_full_page_png_inspected": True, "provider_calls": 0, "database_writes": 0}
    reviewraw = prep.canonical(review)
    witness = {"schema": "private_seed_v8_exact_review_reuse_witness", "source_preparation_sha256": pin(source),
        "panel_manifest_sha256": pin(panel), "independent_review_sha256": pin(reviewraw), "model_outcomes_read": False,
        "original_pdf_hashes_verified": True, "previous_labels_unchanged": True, "provider_calls": 0, "database_writes": 0,
        "old_exact_slots": 42, "new_slots": 8, "new_case_ids": ["D04", "N12"], "candidate_provenance": []}
    for row in labels:
        for label in row["candidates"]:
            new = row["case_id"] in ("D04", "N12")
            origin = {"case_id": row["case_id"], "id": label["id"], "candidate_label_sha256": pin(prep.canonical(label)),
                "review_origin": "fresh_independent_full_original_page_and_exact_cue" if new else "unchanged_previous_exact_before_outcomes"}
            if not new: origin["previous_candidate_label_sha256"] = origin["candidate_label_sha256"]
            witness["candidate_provenance"].append(origin)
    artifacts = {"source": source, "review": reviewraw, "witness": prep.canonical(witness), "panel": panel, "runtime": prep.canonical(runtime)}
    monkeypatch.setattr(prep, "FROZEN_PINS", {name: pin(raw) for name, raw in artifacts.items()})
    return artifacts, code

def bound_synthetic(monkeypatch):
    artifacts, code = synthetic(monkeypatch); prepared = prep.prepare(artifacts, current_code=code)
    hashes = {name: pin(raw) for name, raw in code.items()}
    for path in guard.REQUIRED_CODE_PATHS: hashes[path] = pin((prep.REPO / path).read_bytes())
    scope, pairs = host.modules()[2].bind_cases(prepared, json.loads(artifacts["source"]), hashes)
    bound = custody.BoundTrial(scope, tuple(case for case, _ in pairs), tuple(pins for _, pins in pairs))
    return prepared, bound

def test_complete_fifty_slot_unsigned_exact_review_preflight(monkeypatch):
    artifacts, code = synthetic(monkeypatch); prepared = prep.prepare(artifacts, current_code=code)
    r = prep.report(prepared)
    assert r["case_count"] == 14 and r["candidate_count"] == 50 and r["independent_review_sha_verified"]
    assert not r["signed_review_verified"] and not r["live_authorized"] and not r["release_gate_passed"]
    assert r["guards"]["reserved_cost_usd"] == "0.2809856" and r["guards"]["max_total_seconds"] == 2400
    assert [len(json.loads(c.sources_bytes)) for c in prepared.cases] == [4]*12 + [1]*2
    assert artifacts == dict(prepared.artifacts) and r["provider_calls"] == r["database_writes"] == 0

@pytest.mark.parametrize("mutation", ["bytes", "question", "page", "cue", "png", "review", "origin", "omission", "runtime"])
def test_identity_or_semantic_metadata_change_is_refused(monkeypatch, mutation):
    artifacts, code = synthetic(monkeypatch)
    if mutation == "bytes": artifacts["source"] += b" "
    elif mutation == "runtime": code["backend/app/ai/source_navigation.py"] += b"\n"
    else:
        name = "review" if mutation == "review" else "witness" if mutation == "origin" else "source"
        v = json.loads(artifacts[name])
        if mutation == "review": v["cases"][0]["candidates"][0]["page_useful"] = "No"
        elif mutation == "origin": v["candidate_provenance"][0]["previous_candidate_label_sha256"] = "0"*64
        elif mutation == "omission": v["cases"].pop()
        elif mutation == "question": v["cases"][0]["question"] += " changed"
        elif mutation == "page": v["cases"][0]["candidates"][0]["page_number"] += 1
        elif mutation == "cue": v["cases"][0]["candidates"][0]["start_offset"] += 1
        elif mutation == "png": v["cases"][0]["request"]["contents"][0]["parts"][2]["inline_data"]["data"] = "bad"
        artifacts[name] = prep.canonical(v)
    with pytest.raises((prep.Refusal, prep.contract.VisualSourceJudgmentError)):
        prep.prepare(artifacts, current_code=code)

@pytest.mark.asyncio
@pytest.mark.parametrize("count", [1, 2, 3, 4])
async def test_current_exact_wire_and_fresh_guard_accept_only_actual_slate(monkeypatch, count):
    f = await old_guard_fixture.__wrapped__(monkeypatch)
    selections = f.selections[:count]
    from app.services.source_visual_preparation_v5 import prepare_visual_sources_v5
    fresh = await prepare_visual_sources_v5(f.db(), settings=f.settings, retriever=f.retriever,
        subject_id=f.scope.subject_id, question=f.case.question, selections=selections, snapshot=f.case.snapshot,
        checked_at=f.now, raw_navigation_query=f.case.question)
    case = replace(f.case, case_id="D01", candidates=f.case.candidates[:count], request_bytes=prep.canonical(fresh.request))
    code = {name: pin((prep.REPO/name).read_bytes()) for name in guard.REQUIRED_CODE_PATHS}
    pins = replace(f.pins, request_sha256=pin(case.request_bytes), guard_code_sha256=pin(Path(guard.__file__).read_bytes()), code_sha256=code)
    proof = await guard.prepare_dispatch_proof_seed_v1(f.db(), settings=f.settings, scope=f.scope,
        case=case, selections=selections, pins=pins, services=f.services, clock=lambda:f.now)
    receipt = await guard.verify_private_visual_dispatch_seed_v1(f.db(), settings=f.settings, scope=f.scope,
        case=case, selections=selections, pins=pins, proof=proof, services=f.services, clock=lambda:f.now,
        trial_id=uuid4(), dispatch_nonce=uuid4(), after_quota_wait=True, selected_ids=())
    assert len(receipt["sources"]) == count and receipt["transaction_read_only"] is True
    assert receipt["purpose"] == "post_selection_pdf_read" and not receipt["production_interfaces"]
    assert not receipt["browser_page_open_observed"] and not receipt["persisted_job_authorized"]
    f.pdfs[case.candidates[0].content_revision_id].source_sha256 = "0" * 64
    with pytest.raises(guard.DispatchGuardError):
        await guard.verify_private_visual_dispatch_seed_v1(f.db(), settings=f.settings, scope=f.scope,
            case=case, selections=selections, pins=pins, proof=proof, services=f.services, clock=lambda:f.now,
            trial_id=uuid4(), dispatch_nonce=uuid4(), after_quota_wait=True)

def test_binding_verifies_shared_code_once_per_startup_not_across_calls(monkeypatch):
    prepared, bound = bound_synthetic(monkeypatch)
    original, calls = guard.verify_code_pins, []
    def checked(pins): calls.append(pins); return original(pins)
    monkeypatch.setattr(guard, "verify_code_pins", checked)
    identity = custody.binding_identity(bound)
    custody._validate_bound(prepared, bound, identity); assert len(calls) == 1
    custody._validate_bound(prepared, bound, identity); assert len(calls) == 2
    bad = replace(bound, pins=bound.pins[:-1]+(replace(bound.pins[-1], request_sha256="0"*64),))
    with pytest.raises((custody.TrialError, guard.DispatchGuardError)):
        custody._validate_bound(prepared, bad, identity)

def test_late_equal_code_pairs_cannot_skip_per_case_shape_checks(monkeypatch):
    prepared, bound = bound_synthetic(monkeypatch)
    late = replace(bound.pins[-1], code_sha256=list(bound.pins[-1].code_sha256.items()))
    changed = replace(bound, pins=bound.pins[:-1] + (late,))
    with pytest.raises(custody.TrialError, match="binding_code_invalid"):
        custody._validate_bound(prepared, changed, custody.binding_identity(changed))

@pytest.mark.parametrize("field", ["request_sha256", "guard_code_sha256", "map_key", "map_value"])
def test_late_equal_string_subclasses_cannot_skip_cheap_pin_validation(monkeypatch, field):
    prepared, bound = bound_synthetic(monkeypatch)
    class SameText(str): pass
    late = bound.pins[-1]
    if field.startswith("map_"):
        code = dict(late.code_sha256); name = next(iter(code))
        if field == "map_key": value = code.pop(name); code[SameText(name)] = value
        else: code[name] = SameText(code[name])
        late = replace(late, code_sha256=code)
    else: late = replace(late, **{field:SameText(getattr(late, field))})
    changed = replace(bound, pins=bound.pins[:-1]+(late,))
    with pytest.raises(custody.TrialError, match="binding_code_invalid"):
        custody._validate_bound(prepared, changed, custody.binding_identity(changed))

def test_default_host_and_entry_refuse_before_key_or_docker(monkeypatch, capsys):
    def forbidden(*a, **k): pytest.fail("key or Docker read before authorization")
    monkeypatch.setattr(host, "docker", forbidden); monkeypatch.setattr(host, "read_credential_stdin", forbidden)
    assert host.main([]) == 0 and host.main(["--execute", "unused"]) == 2 and entry.main([]) == 2
    assert host.LIVE_AUTHORIZED is executor.LIVE_AUTHORIZED is entry.LIVE_AUTHORIZED is False
    assert all(json.loads(line)["provider_calls"] == 0 for line in capsys.readouterr().out.splitlines())
    with pytest.raises(host.LaunchError, match="private_execution_not_authorized"):
        host.execute(Path("not-read"), approval_sha256="0"*64, stdin=io.BytesIO(b"forbidden"))

def test_seed_imports_do_not_mutate_frozen_private12_module_globals():
    assert prep.base.MAX_CALLS == 12 and prep.MAX_CALLS == 14
    assert executor.base.SCHEMA == "private_visual_trial_v8_execution"
    assert host.base.MAX_SECONDS == 1800 and "1800" in host.base.WATCHDOG and "2400" in host.WATCHDOG
    assert guard.base.SCHEMA == "private_visual_dispatch_guard_v8" and guard.SCHEMA != guard.base.SCHEMA
    assert host.inspect_runtime.__globals__ is vars(host)

def test_container_args_are_four_cpu_two_gib_and_hard_forty_minutes():
    args = host.create_arguments(Path("/tmp/invented"), {"image":"sha256:"+"a"*64}, "invented-network",
        {"SECRET_KEY":"invented-test-secret", "GENERATION_SOURCE_ENCRYPTION_KEY":"invented-test-source-key"}, "b"*64)
    assert args[args.index("--cpus")+1] == "4" and args[args.index("--memory")+1] == args[args.index("--memory-swap")+1] == "2g"
    assert "2400" in args and "--read-only" in args and "ALL" in args and "no-new-privileges" in args
    assert "SECRET_KEY" in args and "GENERATION_SOURCE_ENCRYPTION_KEY" in args
    assert "invented-test-secret" not in args
    with pytest.raises(host.LaunchError): host.create_arguments(Path("/tmp/x"), {"image":"unused"}, "n", {"RAG_SOURCE_JUDGE_API_KEY":"unused"}, "a"*64)

def test_stage_validation_reuses_only_just_verified_inputs_and_runtime_subset(monkeypatch,tmp_path):
    artifacts,_=synthetic(monkeypatch)
    source=tmp_path/"invented-inputs";source.mkdir()
    for name,raw in artifacts.items():(source/prep.FILES[name]).write_bytes(raw)
    monkeypatch.setattr(host.tempfile,"tempdir",str(tmp_path))
    staged=host.stage(source);root=Path(staged["directory"])
    def forbidden(*a,**k):pytest.fail("validation cannot reread preflight files after verifying bytes")
    monkeypatch.setattr(prep,"preflight_directory",forbidden)
    original=prep.prepare;calls=[]
    def checked(values,*,current_code):
        assert values==artifacts
        assert set(current_code)==set(prep.EXTRA_CODE_PATHS)|{"backend/app/ai/source_navigation.py"}
        calls.append(True);return original(values,current_code=current_code)
    monkeypatch.setattr(prep,"prepare",checked)
    manifest,prepared,bound=host.validate_stage(root)
    assert calls==[True] and len(bound.cases)==14 and not (root/"approval.json").exists()
    # A later invocation must reread/revalidate the actual bytes.
    (root/prep.FILES["source"]).write_bytes(artifacts["source"]+b" ")
    with pytest.raises(host.LaunchError,match="artifact_changed"):host.validate_stage(root)

def measurement(prepared):
    return {"schema": executor.SCHEMA, "status":"completed", "synthetic_interfaces":False,
        "case_denominator":14, "completed_cases":14, "provider_calls":14, "embedding_calls":0, "answer_calls":0,
        "verifier_calls":0, "automatic_retries":0, "database_writes":0, "cases":[{
            "case_id":c.case_id, "selected_ids":[] if c.case_id in ("U01","U02") else ["S01"],
            "question_status":"clear", "request_sha256":c.request_sha256,
            "admission_sha256":c.admission_sha256,"backend_association_verified":True,"unverified_references":True} for c in prepared.cases]}

@pytest.mark.parametrize("mutation", [None,"wrong_source","missing_seed","n12","no_match_status","simulated","changed_request"])
def test_selection_score_all_actual_cards_and_restricted_controls(monkeypatch, mutation):
    artifacts, code = synthetic(monkeypatch); prepared = prep.prepare(artifacts, current_code=code); obs=measurement(prepared)
    if mutation=="wrong_source":obs["cases"][-1]["selected_ids"]=["S01"]
    elif mutation=="missing_seed":
        obs["cases"][0]["selected_ids"]=[];obs["cases"][1]["selected_ids"]=[]
    elif mutation=="n12":obs["cases"][-3]["selected_ids"]=[]
    elif mutation=="no_match_status":obs["cases"][-1]["question_status"]="needs_clarification"
    elif mutation=="simulated":obs["synthetic_interfaces"]=True
    elif mutation=="changed_request":obs["cases"][0]["request_sha256"]="0"*64
    raw=prep.canonical(obs)
    if mutation in ("simulated","changed_request"):
        with pytest.raises(prep.Refusal):prep.score_supplied_measurement(prepared,raw,measurement_sha256=pin(raw))
    else:
        result=prep.score_supplied_measurement(prepared,raw,measurement_sha256=pin(raw))
        assert result["selection_gate_passed"] is (mutation is None)
        assert not result["release_gate_passed"] and not result["browser_page_open_observed"]

class SeedHarness(ControllerHarness):
    _environment = {**Harness.envelope.__globals__, "runner": custody}
    envelope = FunctionType(Harness.envelope.__code__, _environment, "envelope", Harness.envelope.__defaults__)
    envelope.__kwdefaults__ = Harness.envelope.__kwdefaults__
    async def transport(self, endpoint, body, *, api_key, timeout_seconds):
        wire=json.loads(body); count=(len(wire["contents"][0]["parts"])-1)//2
        self.events.append((None,"transport")); self.keys.append(api_key); self.calls.append(body); self.starts.append(self.seconds)
        payload=deepcopy(self.payload)
        value={"question_status":"clear", "pages":[{
            "id":f"S{i:02}","usefulness":"topic_only" if count==1 else "direct","cue_locates":count!=1} for i in range(1,count+1)]}
        payload["candidates"][0]["content"]["parts"][1]["text"]=json.dumps(value)
        return custody.SuppliedHTTPResponse(self.status,prep.canonical(payload))
    def controller_interfaces(self,**changes):
        args=dict(session_factory=self.factory,quota=self.quota,transport=self.transport,current_selections=self.anchors,
            render=self.render,final=self.final,clock=self.now,monotonic=lambda:self.seconds,sleep=self.sleep,close=self.close,synthetic=True)
        args.update(changes);return executor.Interfaces(**args)

async def run_seed(monkeypatch,tmp_path,*,change=None):
    prepared,bound=bound_synthetic(monkeypatch);harness=SeedHarness(prepared,bound)
    raw=executor.approval_payload(prepared,bound,trial_id=uuid4(),authorization_id="invented_seed_test_authority",
        approved_at=NOW,expires_at=NOW+timedelta(hours=1))
    monkeypatch.setattr(executor,"LIVE_AUTHORIZED",True)
    options={}
    if change=="http":harness.status=503
    if change=="wait":
        async def badsleep(seconds):pass
        options["sleep"]=badsleep
    if change=="stale":
        async def delayed(db,**args):
            result=await harness.final(db,**args);harness.seconds+=6;return result
        options["final"]=delayed
    if change=="selected":
        async def rejected(db,**args):
            if "selected_ids" in args:raise guard.DispatchGuardError("invented post-result revocation")
            return await harness.final(db,**args)
        options["final"]=rejected
    result=await executor.execute_private_seed_trial_v1(prepared,bound,settings=object(),api_key="invented-ram-only-test-key",
        approval_bytes=raw,approval_sha256=pin(raw),ledger=executor.TrialLedger(tmp_path),interfaces=harness.controller_interfaces(**options))
    return result,harness

@pytest.mark.asyncio
async def test_fourteen_complete_mock_calls_have_fresh_transactions_and_one_use_custody(monkeypatch,tmp_path):
    result,harness=await run_seed(monkeypatch,tmp_path)
    assert result["status"]=="completed" and result["completed_cases"]==14 and result["case_denominator"]==14
    assert result["provider_calls"]==0 and result["synthetic_transport_calls"]==14
    assert result["reserved_cost_usd"]=="0.2809856" and len(harness.transactions)==56
    assert len(harness.calls)==14 and result["automatic_retries"]==0
    assert all(after-before>=30 for before,after in zip(harness.starts,harness.starts[1:]))
    assert result["cases"][-1]["selected_ids"]==[] and result["cases"][-1]["question_status"]=="clear"
    assert not result["actual_display_integrity_proved"] and not result["release_gate_passed"]
    files=list(tmp_path.glob("*.json"));assert len(files)==72
    text="\n".join(file.read_text() for file in files)
    assert "invented-ram-only-test-key" not in text and "discarded synthetic thought" not in text
    with pytest.raises(executor.ExecutionError,match="ledger_already_consumed"):
        executor.TrialLedger(tmp_path).write("claim.json",{})

@pytest.mark.asyncio
@pytest.mark.parametrize("change,phase,calls",[("http","provider_transport",1),("wait","quota_wait",1),("stale","fresh_dispatch_guard",0),("selected","post_selection_guard",1)])
async def test_pre_send_and_post_result_failures_preserve_claim_stop_without_retry(monkeypatch,tmp_path,change,phase,calls):
    result,harness=await run_seed(monkeypatch,tmp_path,change=change)
    assert result["status"]=="stopped" and result["failure_phase"]==phase and len(harness.calls)==calls
    assert result["automatic_retries"]==0 and (tmp_path/"claim.json").is_file()
    assert result["usage_unknown_attempts"]==(1 if change=="http" else 0)
