"""Bounded byte-identical scratch projection for read-only image tool access.

Original public freezes/labels/images are never modified. Some image viewers
cannot open the Windows Temp surface although normal file reads can. Only
packet-issued, hash-verified PNGs are copied into an owned workspace scratch
directory; this does not render, crop or improve an input.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile
import uuid

import prepare_visual_page_source_input_v1 as visual

PACKET = Path("C:/Users/eocim/AppData/Local/Temp/cardchemy-visual-feasibility-v1-7ut522w8/review-packet.json")
PACKET_SHA = "4f1d237852e8bd9894437fabfc060072ab49313fd5778a84fc637fb316aac1c8"
SOURCE = Path("C:/Users/eocim/AppData/Local/Temp/cardchemy-visual-input-v1-vwcn8r3i/images")
SCRATCH = Path(__file__).resolve().parents[1] / "tmp/pdfs"


def copy_inputs(receipt_root: Path) -> None:
    visual.require(visual._inside_windows_job(), "enforceable_resource_mode_required")
    packet = visual.read_json(PACKET, PACKET_SHA)
    rows = packet["cases"] + packet["controls"]
    visual.require(len(rows) == 29 and len({r["review_id"] for r in rows}) == 29,
                   "complete_visual_review_roster")
    SCRATCH.mkdir(parents=True, exist_ok=True)
    target = SCRATCH / ("visual-review-access-" + uuid.uuid4().hex)
    target.mkdir()
    access = []
    copied = {}
    for row in rows:
        source = Path(row["image_path"])
        visual.require(source.resolve().parent == SOURCE.resolve() and source.is_file()
                       and not source.is_symlink(), "issued_image_source_required")
        with source.open("rb") as stream:
            raw = stream.read(visual.MAX_PNG_BYTES + 1)
        inspected = visual.inspect_png(raw)
        visual.require(inspected["sha256"] == row["image_sha256"] and
                       inspected["width"] == row["width"] and inspected["height"] == row["height"],
                       "issued_image_bytes_changed")
        if source.name not in copied:
            destination = target / source.name
            visual.write_new(destination, raw)
            visual.require(visual.digest(destination.read_bytes()) == row["image_sha256"],
                           "access_copy_bytes_changed")
            copied[source.name] = destination
        access.append({"review_id": row["review_id"], "image_sha256": row["image_sha256"],
                       "original_path": str(source), "access_path": str(copied[source.name])})
    output = {"schema_version": "visual_review_access_v1", "packet_sha256": PACKET_SHA,
              "rows": access, "distinct_images": len(copied), "byte_identical": True,
              "resource_limits_enforced": True, "provider_calls": 0, "model_quality_pass": False}
    sha = visual.write_new(target / "access.json", visual.canonical(output))
    visual.write_new(receipt_root / "receipt.json", visual.canonical({
        "access_path": str(target / "access.json"), "access_sha256": sha,
        "rows": 29, "distinct_images": len(copied), "provider_calls": 0}))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--resource-job")
    args = parser.parse_args()
    if args.worker:
        visual.RESOURCE_JOB_NAME = visual.validate_resource_job_name(args.resource_job)
        visual.require(args.destination is not None and
                       args.destination.resolve().parent == Path(tempfile.gettempdir()).resolve(),
                       "temp_destination_required")
        copy_inputs(args.destination)
    else:
        visual.require(args.destination is None and args.resource_job is None,
                       "internal_worker_arguments_forbidden")
        receipt_root = Path(tempfile.mkdtemp(prefix="cardchemy-visual-access-receipt-"))
        visual.__file__ = __file__  # Supervisor launches this no-render worker.
        visual.supervise(receipt_root)
        print((receipt_root / "receipt.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
