"""Public-only development input review; no model scores or execution.

This projection keeps old labels/results outside reviewer packets. It selects
the predeclared five input gaps and a deterministic sixteen-pair sample on
which both prior independent reviewers agreed that page and cue were weak.
Original labels and all 66 questions remain unchanged in their parent freeze.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile

import prepare_visual_page_source_input_v1 as visual
import summarize_source_usefulness_contract_v1 as prior

VERSION = "visual_source_feasibility_review_v1"
GAPS = frozenset({"P072", "P122", "P139", "P146", "P199"})
MAPPING_SHA = "1a25153b1ac6163671b1f18e69c836e3007faf44a2ba24875990e83e0938847d"
SEED = "visual-feasibility-weak-v1"
CONTROL_QUESTION = ("What measured patient survival rate did a randomized clinical "
                    "trial of chemotherapy report, and which two treatments did it compare?")
RUBRIC = {
    "readability": "Yes if the full supplied 1600-pixel page can be read without external zoom/rerender; No if necessary details are unreadable; Unsure if unresolved.",
    "input_usefulness": "Judge only the supplied exact text/cue and full-page image. Yes if they teach the requested relation or an explicitly connected concrete learning step under its conditions; a complete answer is unnecessary. No for shared topic, generic prerequisite, restatement, or unsupported outside inference. Preserve Unsure.",
    "cue_usefulness": "Yes only when the exact cue locates useful material on this same image. A heading can locate a diagram; it need not reproduce the answer. Preserve Unsure.",
    "question_clarity": "Yes if the required object/conditions are identifiable from the question itself; No if clarification is needed; Unsure if unresolved. Do not invent a referent from other questions.",
    "procedure": "Read every supplied image at its actual input resolution using view_image. Do not inspect old labels/model outputs or original PDFs. Source/image bindings were independently checked. No desired useful count, no answer generation, no reannotation of parent labels. This is development input feasibility, not a model quality score.",
}


def select_weak(a: dict, b: dict) -> list[str]:
    visual.require(set(a) == set(b) and len(a) == 264, "complete_review_roster")
    weak = [pid for pid in a if pid not in GAPS and all(
        rows[pid][field] == "No" for rows in (a, b)
        for field in ("page_usefulness", "cue_usefulness"))]
    ordered = sorted(weak, key=lambda pid: visual.digest(f"{SEED}:{pid}".encode()))
    visual.require(len(ordered) >= 16, "insufficient_agreed_weak_pairs")
    return ordered[:16]


def prepare(root: Path, expected_freeze_sha256: str) -> Path:
    # Source/input access is confined to the completed public calibration.
    mapping = visual.read_json(visual.AUDIT_ROOT / "final/complete-label-mapping.json", MAPPING_SHA)
    a, b = {}, {}
    for batch in (1, 2, 3):
        for reviewer, target in (("a", a), ("b", b)):
            target.update(prior.load_sealed(visual.AUDIT_ROOT, batch, reviewer))
    weak = select_weak(a, b)
    chosen = GAPS | set(weak)
    indexed = {row["pair_id"]: row for row in mapping["pairs"]}
    visual.require(len(indexed) == 264 and chosen <= indexed.keys(), "complete_parent_mapping")
    # Loader checks the complete frozen roster once. Each projected image is
    # then read and revalidated against that immutable manifest's SHA/metadata.
    visual.load_frozen_group(root, 1, expected_freeze_sha256=expected_freeze_sha256)
    freeze = visual.read_json(root / "freeze.json", expected_freeze_sha256)
    manifest = visual.read_json(root / "manifest.json", freeze["manifest_sha256"])
    image_index = {(r["document_id"], r["physical_page"]): r for r in manifest["images"]}
    inputs = {}
    for ordinal in range(1, 67):
        relative = f"inputs/group-{ordinal:03d}.json"
        group = visual.read_json(root / relative, manifest["files"][relative])
        for candidate in group["candidates"]:
            inputs[candidate["pair_id"]] = (group, candidate)
    visual.require(set(inputs) == set(indexed), "projection_parent_roster")
    ordered = sorted(chosen, key=lambda pid: visual.digest(f"visual-review-v1:{pid}".encode()))
    cases, hidden = [], {}

    def project(group, candidate, review_id, question=None):
        key = (candidate["document_id"], candidate["page"])
        image = image_index[key]
        raw = (root / image["path"]).read_bytes()
        visual.validate_raster_bindings(candidate, {k: v for k, v in image.items() if k != "path"} | {"png_bytes": raw})
        return {"review_id": review_id, "question": question or group["question"],
                "context": candidate["context"], "cue": candidate["cue"],
                "image_path": str(root / image["path"]), "image_sha256": image["sha256"],
                "width": image["width"], "height": image["height"]}

    for ordinal, pid in enumerate(ordered, 1):
        group, candidate = inputs[pid]
        rid = f"R{ordinal:02d}"
        cases.append(project(group, candidate, rid))
        hidden[rid] = {"pair_id": pid, "kind": "gap" if pid in GAPS else "agreed_weak"}
    # Retain unresolved original question separately, and add exactly one new
    # four-candidate control using the same physical pages (no additional render).
    unresolved = [row for row in mapping["pairs"] if "Unsure" in row["new_labels"].values()]
    visual.require(len(unresolved) == 3 and len({r["old_group_id"] for r in unresolved}) == 1,
                   "uncertainty_control_binding")
    unknown_group = inputs[unresolved[0]["pair_id"]][0]
    controls = []
    for prefix, question in (("U", unknown_group["question"]), ("N", CONTROL_QUESTION)):
        for ordinal, candidate in enumerate(unknown_group["candidates"], 1):
            controls.append(project(unknown_group, candidate, f"{prefix}{ordinal:02d}", question))
    packet = {"schema_version": VERSION, "rubric": RUBRIC, "development_only": True,
              "cases": cases, "controls": controls}
    destination = Path(tempfile.mkdtemp(prefix="cardchemy-visual-feasibility-v1-"))
    packet_sha = visual.write_new(destination / "review-packet.json", visual.canonical(packet))
    hidden_sha = visual.write_new(destination / "mapping-root-only.json", visual.canonical(hidden))
    visual.write_new(destination / "freeze.json", visual.canonical({
        "schema_version": VERSION, "parent_visual_freeze_sha256": expected_freeze_sha256,
        "packet_sha256": packet_sha, "mapping_sha256": hidden_sha,
        "feasibility_pairs": 21, "original_uncertainty_pages": 4,
        "additional_control_groups": 1, "additional_control_pages": 4,
        "provider_calls": 0, "model_quality_pass": False,
        "old_labels_changed": False, "heldout_opened": False}))
    return destination
