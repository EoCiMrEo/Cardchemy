"""Bounded public-only reconciliation projection with opaque reviewer IDs.

Only three approved semantic pairs and the already prepared four-page draft
are projected. No rendering, labels, model scores, provider, private sources,
heldout, environment file or database is read. Old artifacts remain immutable.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import tempfile
import uuid

import prepare_visual_page_source_input_v1 as visual
import prepare_visual_source_feasibility_review_v1 as old
import prototype_visual_page_source_judge_v2 as prospective

VERSION = "visual_semantic_control_review_v2"
OLD_ROOT = Path("C:/Users/eocim/AppData/Local/Temp/cardchemy-visual-feasibility-v1-7ut522w8")
OLD_FREEZE_SHA = "9791994e5657dd3062659a105ea0dd71c5f6ff9b7201292ce542d6075dae840c"
VISUAL_ROOT = Path("C:/Users/eocim/AppData/Local/Temp/cardchemy-visual-input-v1-vwcn8r3i")
VISUAL_FREEZE_SHA = "1079eab34382f62467757209040e40113ee4bae76082ea98c4e644bd378e5bac"
PAIRS = frozenset({"P146", "P119", "P009"})
SCRATCH = Path(__file__).resolve().parents[1] / "tmp/pdfs"
RUBRIC = dict(old.RUBRIC, question_clarity=prospective.QUESTION_CLARITY +
              " Yes means the task is clear; No means clarification is required; "
              "Unsure means unresolved. Preserve uncertainty.", procedure=
              "Read every supplied image at its actual input resolution using view_image. "
              "Use only this packet's question, text, cue and full-page image. "
              "Do not read parent labels, old votes, model outputs, original PDFs or "
              "root-only mappings. There is no desired useful count or label. "
              "Do not generate an answer. Return the four tri-state fields and a "
              "closed reason per issued ID. This is input review, not model quality.")


def project(rows: list[dict], target: Path, copied: dict) -> list[dict]:
    ordered = sorted(rows, key=lambda row: visual.digest(
        (VERSION + ":" + row["review_id"]).encode()))
    projected = []
    for ordinal, row in enumerate(ordered, 1):
        source = Path(row["image_path"])
        visual.require(source.resolve().parent == (VISUAL_ROOT / "images").resolve()
                       and not source.is_symlink(), "issued_image_source_required")
        with source.open("rb") as stream:
            raw = stream.read(visual.MAX_PNG_BYTES + 1)
        inspected = visual.inspect_png(raw)
        visual.require(all(inspected[k] == row[k] for k in ("width", "height")) and
                       inspected["sha256"] == row["image_sha256"],
                       "issued_image_bytes_changed")
        if row["image_sha256"] not in copied:
            destination = target / f"image-{len(copied) + 1:03d}.png"
            visual.write_new(destination, raw)
            visual.require(visual.digest(destination.read_bytes()) == row["image_sha256"],
                           "access_copy_bytes_changed")
            copied[row["image_sha256"]] = destination
        value = {k: row[k] for k in ("question", "context", "cue", "image_sha256", "width", "height")}
        value.update(review_id=f"R{ordinal:03d}", image_path=str(copied[row["image_sha256"]]))
        projected.append(value)
    return projected


def prepare(destination: Path) -> None:
    visual.require(visual._inside_windows_job(), "enforceable_resource_mode_required")
    # External anchors are reread after validation; coordinated file replacement
    # cannot substitute a new locally consistent manifest or review projection.
    visual.load_frozen_group(VISUAL_ROOT, 1, expected_freeze_sha256=VISUAL_FREEZE_SHA)
    freeze = visual.read_json(OLD_ROOT / "freeze.json", OLD_FREEZE_SHA)
    packet = visual.read_json(OLD_ROOT / "review-packet.json", freeze["packet_sha256"])
    mapping = visual.read_json(OLD_ROOT / "mapping-root-only.json", freeze["mapping_sha256"])
    semantic_rows = [r for r in packet["cases"] if mapping[r["review_id"]]["pair_id"] in PAIRS]
    control_rows = [r for r in packet["controls"] if r["review_id"].startswith("N")]
    visual.require(len(semantic_rows) == 3 and len(control_rows) == 4 and
                   {mapping[r["review_id"]]["pair_id"] for r in semantic_rows} == PAIRS and
                   len({r["question"] for r in control_rows}) == 1,
                   "approved_reconciliation_roster_required")
    # Check each projected row against canonical parent question/text/cue/image.
    image_freeze = visual.read_json(VISUAL_ROOT / "freeze.json", VISUAL_FREEZE_SHA)
    manifest = visual.read_json(VISUAL_ROOT / "manifest.json", image_freeze["manifest_sha256"])
    originals = {}
    for ordinal in range(1, 67):
        relative = f"inputs/group-{ordinal:03d}.json"
        group = visual.read_json(VISUAL_ROOT / relative, manifest["files"][relative])
        for candidate in group["candidates"]:
            originals[candidate["pair_id"]] = (group, candidate)
    semantic_ids = {r["review_id"] for r in semantic_rows}
    for row in semantic_rows + control_rows:
        if row["review_id"] in semantic_ids:
            group, candidate = originals[mapping[row["review_id"]]["pair_id"]]
            visual.require(row["question"] == group["question"], "question_binding_invalid")
        else:
            matches = [candidate for _, candidate in originals.values() if
                       candidate["image"]["sha256"] == row["image_sha256"] and
                       candidate["context"] == row["context"] and candidate["cue"] == row["cue"]]
            visual.require(bool(matches) and row["question"] == old.CONTROL_QUESTION,
                           "draft_control_binding_invalid")
            candidate = matches[0]
        visual.require(candidate["context"] == row["context"] and
                       candidate["cue"] == row["cue"] and
                       candidate["image"]["sha256"] == row["image_sha256"],
                       "source_projection_changed")
    SCRATCH.mkdir(parents=True, exist_ok=True)
    visual.require(not SCRATCH.is_symlink(), "scratch_reparse_forbidden")
    target = SCRATCH / ("visual-semantic-access-" + uuid.uuid4().hex)
    target.mkdir()
    copied = {}
    receipt = {"schema_version": VERSION, "parent_visual_freeze_sha256": VISUAL_FREEZE_SHA,
               "parent_review_freeze_sha256": OLD_FREEZE_SHA, "provider_calls": 0,
               "model_inferences": 0, "heldout_opened": False, "old_labels_changed": False,
               "model_quality_pass": False, "provider_trial_ready": False,
               "resource_limits_enforced": True, "files": {}, "access_root": str(target)}
    root_mapping = {}
    for name, rows in (("semantic", semantic_rows), ("source_group", control_rows)):
        projected = project(rows, target, copied)
        raw = visual.canonical({"schema_version": VERSION, "rubric": RUBRIC,
                               "development_only": True, "cases": projected})
        path = destination / f"{name}-packet.json"
        receipt["files"][path.name] = visual.write_new(path, raw)
        ordered = sorted(rows, key=lambda row: visual.digest((VERSION + ":" + row["review_id"]).encode()))
        root_mapping[name] = {p["review_id"]: {"old_review_id": r["review_id"],
                              "pair_id": mapping[r["review_id"]]["pair_id"] if name == "semantic" else None}
                              for p, r in zip(projected, ordered)}
    receipt["distinct_images"] = len(copied)
    receipt["files"]["mapping-root-only.json"] = visual.write_new(
        destination / "mapping-root-only.json", visual.canonical(root_mapping))
    receipt["files"]["prototype-v2.sha256"] = visual.write_new(
        destination / "prototype-v2.sha256", visual.digest(Path(prospective.__file__).read_bytes()).encode())
    sha = visual.write_new(destination / "freeze.json", visual.canonical(receipt))
    visual.write_new(destination / "receipt.json", visual.canonical({
        "root": str(destination), "freeze_sha256": sha,
        "packets": {k: v for k, v in receipt["files"].items() if k.endswith("packet.json")},
        "projected_rows": 7, "distinct_images": len(copied), "provider_calls": 0}))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--resource-job")
    args = parser.parse_args()
    if args.worker:
        visual.RESOURCE_JOB_NAME = visual.validate_resource_job_name(args.resource_job)
        visual.require(args.destination is not None and args.destination.resolve().parent ==
                       Path(tempfile.gettempdir()).resolve(), "temp_destination_required")
        prepare(args.destination)
    else:
        visual.require(args.destination is None and args.resource_job is None,
                       "internal_worker_arguments_forbidden")
        destination = Path(tempfile.mkdtemp(prefix="cardchemy-visual-semantic-v2-"))
        visual.__file__ = __file__
        visual.supervise(destination)
        print((destination / "receipt.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
