"""Bind and blind the separately prepared public heldout for independent review.

No provider, source-model inference, runtime, database, credential or private
Knowledge access exists here. Old Boolean labels remain in their original
freeze; reviewers see exact current text/cue/full-page PNGs without outcomes.
"""
from __future__ import annotations

import argparse
import copy
from pathlib import Path
import tempfile

import prepare_visual_public_heldout_v2 as input_
import prepare_visual_source_feasibility_review_v1 as rubric_source
import summarize_visual_source_feasibility_v1 as review_contract

VERSION = "visual_public_heldout_review_v1"
FIELDS = review_contract.FIELDS
VALUES = review_contract.VALUES
REASONS = review_contract.REASONS
RUBRIC = copy.deepcopy(rubric_source.RUBRIC)
RUBRIC["readability"] = (
    "Judge the supplied faithful full-page PNG at its actual recorded resolution, "
    "1600 or1400/1200/1000pixels on the long side. Yes if necessary details are readable; "
    "No if they are not; preserve Unsure. Do not rerender or infer missing visual content.")
RUBRIC["question_clarity"] = (
    "Yes when the task and material conditions are identifiable, including a question "
    "asking to discover a name, object or example. Do not require the unknown answer "
    "to be named in the question. No for a genuinely unresolved referent or unspecified "
    "task; preserve Unsure. No outside facts or other questions.")
RUBRIC["procedure"] = (
    "Independently read every supplied full-page image using view_image at its actual "
    "resolution and judge each supplied question/text/cue pair. Read the wire-visible "
    "text first, then the image. Do not inspect historical labels, model outputs or "
    "the original PDF. No desired useful count, answer generation or rewriting parent "
    "labels. Return complete Yes/No/Unsure judgments and a closed reason for every ID.")


def validate_frozen_input(root: Path, expected_freeze_sha256: str) -> tuple[dict, dict, dict]:
    input_.require(root.is_dir() and not root.is_symlink() and
                   root.resolve().parent == Path(tempfile.gettempdir()).resolve(),
                   "owned_public_freeze_required")
    freeze = input_.read_json(root/"freeze.json", expected_freeze_sha256)
    input_.require(freeze == {"schema_version":input_.VERSION,
        "manifest_sha256":freeze.get("manifest_sha256"),"groups":60,
        "candidate_pairs":240,"distinct_pages":86,"provider_calls":0,
        "quality_pass":False,"scoring_permitted":False} and
        input_._sha(freeze["manifest_sha256"]), "complete_input_freeze_required")
    manifest = input_.read_json(root/"manifest.json",freeze["manifest_sha256"])
    input_.require(manifest.get("schema_version")==input_.VERSION and
        manifest.get("source_packet_sha256")==input_.PACKET_SHA and
        manifest.get("historical_labels_sha256")==input_.LABEL_SHA and
        manifest.get("parent_freeze_sha256")==input_.PARENT_FREEZE_SHA and
        manifest.get("groups")==60 and manifest.get("candidate_pairs")==240 and
        manifest.get("distinct_pages")==86 and manifest.get("provider_calls")==0 and
        manifest.get("quality_pass") is False and manifest.get("scoring_permitted") is False and
        manifest.get("resource_limits_enforced") is True and manifest.get("mock_renderer") is False and
        manifest.get("resource_enforcement")==input_.RESOURCE_RECEIPT,
        "enforced_input_manifest_required")
    receipt_path=root/"preparation-receipt.json"
    receipt=input_.read_json(receipt_path,input_.digest(receipt_path.read_bytes()))
    input_.require(receipt=={"schema_version":input_.VERSION,"complete":True,
        "manifest_sha256":freeze["manifest_sha256"],"resource_limits_enforced":True,
        "provider_calls":0,"quality_pass":False},"complete_preparation_receipt")
    image_index={(r["document_id"],r["physical_page"]):r for r in manifest["images"]}
    input_.require(len(image_index)==len(manifest["images"])==86,"complete_unique_image_roster")
    image_files={r["path"] for r in manifest["images"]}
    expected=image_files|{f"{kind}/group-{n:03d}.json" for kind in ("inputs","wires") for n in range(1,61)}|{"review/packet.json"}
    input_.require(set(manifest["files"])==expected,"complete_frozen_file_roster")
    for relative,sha in manifest["files"].items():
        path=root/relative
        input_.require(not Path(relative).is_absolute() and ".." not in Path(relative).parts and
            path.resolve().is_relative_to(root.resolve()) and path.is_file() and not path.is_symlink() and
            input_._sha(sha),"frozen_path_invalid")
        limit=input_.MAX_PNG_BYTES if relative in image_files else input_.MAX_REQUEST_BYTES
        with path.open("rb") as stream:raw=stream.read(limit+1)
        input_.require(len(raw)<=limit and input_.digest(raw)==sha,"frozen_file_hash_mismatch")
    parent_packet,bound=input_.load_inputs()
    mapping_path=root/"mapping-root-only.json"
    expected_mapping={"schema_version":input_.VERSION,"source_packet_sha256":input_.PACKET_SHA,
        "historical_labels_sha256":input_.LABEL_SHA,"pairs":bound["mapping"]}
    input_.require(mapping_path.is_file() and not mapping_path.is_symlink() and
        mapping_path.read_bytes()==input_.canonical(expected_mapping),"mapping_parent_binding")
    input_.require(manifest["documents"]==parent_packet["documents"] and
        set(image_index)==set(bound["pages"]),"source_manifest_binding")
    images={}
    for source,row in image_index.items():
        relative=f"images/{source[0]}-page-{source[1]:03d}.png"
        input_.require(row["path"]==relative and manifest["files"][relative]==row["sha256"],
            "image_path_binding")
        images[source]={k:v for k,v in row.items() if k!="path"}|{"png_bytes":(root/relative).read_bytes()}
    for ordinal,original in enumerate(bound["groups"],1):
        input_path=f"inputs/group-{ordinal:03d}.json";wire_path=f"wires/group-{ordinal:03d}.json"
        assembled,wire=input_.build_group_payload(original,images)
        input_.require((root/input_path).read_bytes()==input_.canonical(assembled) and
            (root/wire_path).read_bytes()==input_.canonical(wire),"exact_parent_wire_binding")
        request=manifest["requests"][ordinal-1]
        input_.require(request=={"group_id":original["group_id"],"input_path":input_path,
            "wire_path":wire_path,"wire_sha256":manifest["files"][wire_path],
            "wire_bytes":len(input_.canonical(wire)),"images":4},"complete_request_binding")
    input_.require(len(manifest["requests"])==60,"complete_request_roster")
    return manifest,bound,images


def project_review(root: Path, expected_freeze_sha256: str) -> tuple[dict, dict]:
    manifest,bound,images=validate_frozen_input(root,expected_freeze_sha256)
    indexed={c["pair_id"]:(g,c) for g in bound["groups"] for c in g["candidates"]}
    ordered=sorted(indexed,key=lambda pid:input_.digest(f"visual-heldout-review-v1:{pid}".encode()))
    cases,mapping=[],[]
    for ordinal,pid in enumerate(ordered,1):
        group,candidate=indexed[pid];source=(candidate["document_id"],candidate["page"])
        image=images[source];rid=f"R{ordinal:03d}"
        cases.append({"review_id":rid,"question":group["question"],
            "context":candidate["context"],"cue":candidate["cue"],
            "image_path":str(root/f"images/{source[0]}-page-{source[1]:03d}.png"),
            "image_sha256":image["sha256"],"width":image["width"],"height":image["height"],
            "actual_scale":image["render"]["scale_to"]})
        mapping.append({"review_id":rid,"pair_id":pid,"group_id":group["group_id"],
            "candidate_id":candidate["id"]})
    packet={"schema_version":VERSION,"rubric":RUBRIC,"cases":cases,
        "source_visual_freeze_sha256":expected_freeze_sha256,"candidate_pairs":240,
        "distinct_images":86,"provider_calls":0,"model_quality_pass":False,
        "historical_labels_included":False,"model_outcomes_included":False}
    hidden={"schema_version":VERSION,"pairs":mapping,
        "source_packet_sha256":input_.PACKET_SHA,"historical_labels_sha256":input_.LABEL_SHA}
    return packet,hidden


def validate_review(review: dict, packet: dict, packet_sha256: str, reviewer: str) -> dict:
    roster={r["review_id"] for r in packet["cases"]}
    input_.require(type(review) is dict and set(review)=={
        "reviewer","packet_sha256","images_visually_inspected","provider_calls",
        "model_quality_pass","judgments"} and review["reviewer"]==reviewer and
        type(reviewer) is str and bool(reviewer) and review["packet_sha256"]==packet_sha256 and
        type(review["images_visually_inspected"]) is int and
        review["images_visually_inspected"]==packet["distinct_images"] and
        type(review["provider_calls"]) is int and review["provider_calls"]==0 and
        review["model_quality_pass"] is False,"review_binding_invalid")
    rows=review["judgments"]
    input_.require(type(rows) is list and len(rows)==len(roster),"complete_review_required")
    output={}
    for row in rows:
        input_.require(type(row) is dict and set(row)=={"review_id",*FIELDS,"reason"} and
            row["review_id"] in roster and row["review_id"] not in output and
            all(type(row[f]) is str and row[f] in VALUES for f in FIELDS) and
            type(row["reason"]) is str and row["reason"] in REASONS,
            "review_judgment_invalid")
        input_.require(row["cue_usefulness"]!="Yes" or row["input_usefulness"]=="Yes",
            "cue_without_useful_input")
        output[row["review_id"]]=row
    input_.require(set(output)==roster,"complete_review_required")
    return output


def prepare(root: Path,expected_freeze_sha256: str) -> Path:
    packet,mapping=project_review(root,expected_freeze_sha256)
    destination=Path(tempfile.mkdtemp(prefix="cardchemy-visual-heldout-review-v1-"))
    packet_sha=input_.write_new(destination/"packet.json",input_.canonical(packet))
    mapping_sha=input_.write_new(destination/"mapping-root-only.json",input_.canonical(mapping))
    input_.write_new(destination/"freeze.json",input_.canonical({"schema_version":VERSION,
        "source_visual_freeze_sha256":expected_freeze_sha256,"packet_sha256":packet_sha,
        "mapping_sha256":mapping_sha,"candidate_pairs":240,"distinct_images":86,
        "provider_calls":0,"model_quality_pass":False,"reviews_complete":False}))
    return destination


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root",type=Path,required=True)
    parser.add_argument("--freeze-sha256",required=True)
    args=parser.parse_args()
    try:
        root=prepare(args.input_root,args.freeze_sha256)
        print(input_.canonical({"output_dir":str(root),
            "freeze_sha256":input_.digest((root/"freeze.json").read_bytes()),
            "provider_calls":0,"model_quality_pass":False}).decode("utf-8"))
    except (input_.PreparationError,OSError) as error:
        parser.exit(2,(str(error) if isinstance(error,input_.PreparationError) else "review_io_failed")+"\n")


if __name__=="__main__":main()
