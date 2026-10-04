"""Synthetic, keyless heldout preparation safety; no cached corpus or provider."""
import copy
import json
from pathlib import Path
import struct
import sys
import zlib

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/"scripts"))
import prepare_visual_public_heldout_v1 as heldout


def png():
    def chunk(kind, data):
        return struct.pack(">I", len(data))+kind+data+struct.pack(">I", zlib.crc32(kind+data)&0xffffffff)
    return (b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR", struct.pack(">IIBBBBB",80,60,8,2,0,0,0))+
            chunk(b"IDAT",zlib.compress((b"\0"+b"\x11\x22\x33"*80)*60))+chunk(b"IEND",b""))


@pytest.fixture
def packet():
    groups=[]
    docs=sorted(heldout.ROSTER)
    for index in range(4):
        rows=[]
        for k in range(4):
            did=docs[(index%2)*2+k//2]
            context="Prefix\nInvented relation.\nSuffix"
            rows.append({"id":f"S{k+1:02d}","document_id":did,"page":k%2+1,
                "context":context,"cue":"Invented relation.","context_start":0,
                "context_end":len(context),"cue_start":7,"cue_end":25,
                "page_text_sha256":"a"*64})
        groups.append({"group_id":f"G{index+1:03d}","question":"What relation is invented?","candidates":rows})
    return {"schema_version":"synthetic","corpus_id":"synthetic-public",
        "documents":[{"document_id":d,"pages":2,"sha256":"b"*64} for d in docs],
        "groups":groups,"source_manifest_sha256":"c"*64,"split":"heldout"}


def validate(packet):
    return heldout.validate_packet(packet,expected_groups=4,expected_pages=8)


def test_immutable_questions_and_exact_windows_preserved(packet):
    before=copy.deepcopy(packet)
    bound=validate(packet)
    assert packet==before
    assert len(bound["mapping"])==16
    assert len({r["review_id"] for r in bound["mapping"]})==16
    assert [g["question"] for g in bound["groups"]]==[g["question"] for g in packet["groups"]]
    for old,new in zip(packet["groups"],bound["groups"]):
        for a,b in zip(old["candidates"],new["candidates"]):
            assert all(b[k]==v for k,v in a.items())


@pytest.mark.parametrize("mutation,code",[
    (lambda p:p.update(split="calibration"),"heldout_packet_required"),
    (lambda p:p["groups"].pop(),"complete_group_roster"),
    (lambda p:p["groups"][0]["candidates"][0].update(document_id="lec04"),"candidate_source_identity"),
    (lambda p:p["groups"][0]["candidates"][0].update(page=True),"candidate_source_identity"),
    (lambda p:p["groups"][0]["candidates"][0].update(cue="Changed"),"exact_source_window_required"),
    (lambda p:p["groups"][0]["candidates"][0].update(id="foreign"),"four_issued_candidates_required"),
    (lambda p:p["groups"][1].update(group_id="G001"),"group_identity_invalid"),
])
def test_invalid_identity_and_exact_window_rejected(packet,mutation,code):
    mutation(packet)
    with pytest.raises(heldout.PreparationError,match=code):validate(packet)


def test_payload_has_only_public_text_images_and_same_v5_wire(packet):
    bound=validate(packet);raw=png();images={}
    for did,page in bound["pages"]:
        images[(did,page)]={"document_id":did,"pdf_sha256":"b"*64,"physical_page":page,
            "render":heldout.RENDER_PARAMETERS,"renderer_sha256":"d"*64,
            **heldout.inspect_png(raw),"png_bytes":raw}
    group,wire=heldout.build_group_payload(bound["groups"][0],images)
    assert wire["generationConfig"]["maxOutputTokens"]==4096
    assert wire["generationConfig"]["thinkingConfig"]=={"thinkingLevel":"HIGH"}
    assert wire["systemInstruction"]=={"parts":[{"text":heldout.prototype.SYSTEM}]}
    assert wire["store"] is False
    assert len(wire["contents"][0]["parts"])==9
    assert set(group["candidates"][0])==heldout.CANDIDATE_FIELDS|{"pair_id","pdf_sha256","image"}
    for forbidden in ("labels","selected_ids","reviewer","api_key"):
        assert forbidden not in wire
    images[(group["candidates"][0]["document_id"],group["candidates"][0]["page"])]["physical_page"]=99
    with pytest.raises(heldout.PreparationError,match="raster_source_binding"):
        heldout.build_group_payload(bound["groups"][0],images)


def test_mock_freeze_never_claims_resource_or_quality_pass(packet,tmp_path,monkeypatch):
    bound=validate(packet)
    monkeypatch.setattr(heldout,"GROUPS",4);monkeypatch.setattr(heldout,"PAIRS",16)
    def renderer(pdf,page,destination,timeout):return png(),"d"*64
    heldout.prepare_from_inputs(packet,bound,renderer,tmp_path)
    manifest=json.loads((tmp_path/"manifest.json").read_bytes())
    assert manifest["mock_renderer"] is True
    assert manifest["resource_limits_enforced"] is False
    assert manifest["provider_calls"]==0 and manifest["quality_pass"] is False
    assert manifest["scoring_permitted"] is False
    assert manifest["source_qualification_review_complete"] is False
    packet=json.loads((tmp_path/"review/packet.json").read_bytes())
    assert packet["historical_labels_included"] is False
    assert packet["model_outcomes_included"] is False
    assert all(not any(k in c for k in ("page_useful","cue_useful","selected_ids")) for c in packet["cases"])
    with pytest.raises(heldout.PreparationError,match="output_or_partial_state_exists"):
        heldout.prepare_from_inputs({},bound,renderer,tmp_path)


def test_resource_admission_precedes_source_read(monkeypatch,tmp_path):
    monkeypatch.setattr(heldout,"_inside_windows_job",lambda:False)
    monkeypatch.setattr(heldout,"load_inputs",lambda:pytest.fail("Source read before resource admission"))
    with pytest.raises(heldout.PreparationError,match="enforceable_resource_mode_required"):
        heldout.prepare(destination=tmp_path,resource_receipt=heldout.RESOURCE_RECEIPT)


def test_named_resource_ancestor_and_caps_remain_exact():
    name=heldout.RESOURCE_JOB_PREFIX+"f"*32
    assert heldout.validate_resource_job_name(name)==name
    with pytest.raises(heldout.PreparationError):heldout.validate_resource_job_name("cardchemy-visual-"+"f"*32)
    assert heldout.RESOURCE_RECEIPT=={
        "mode":"windows_job_object_v1","cpus":4,"aggregate_committed_memory_bytes":2_147_483_648,
        "total_timeout_seconds":600,"child_timeout_seconds":30,"kill_tree_on_close":True}
