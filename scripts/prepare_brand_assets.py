"""Derive web-sized PNGs without replacing the owner-supplied artwork.

Art maintenance only: run with a Python installation containing Pillow.
The application, tests and containers do not import this optional tool.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "frontend" / "public"


def main() -> None:
    destination = PUBLIC / "brand"
    destination.mkdir(exist_ok=True)
    records = []
    for original, filename, width in (
        ("cardchemy-text-icon.png", "cardchemy-wordmark.png", 480),
        ("cardchemy-logo.png", "cardchemy-lockup.png", 960),
    ):
        source = PUBLIC / original
        artwork = Image.open(source).convert("RGBA")
        bounds = artwork.getchannel("A").getbbox()
        if bounds is None:
            raise SystemExit("Brand source has no visible pixels")
        cropped = artwork.crop(bounds)
        height = round(cropped.height * width / cropped.width)
        export = cropped.resize((width, height), Image.Resampling.LANCZOS)
        output = destination / filename
        # The raster is deliberately resized; PNG encodes those pixels losslessly.
        export.save(output, format="PNG", optimize=True, compress_level=9)
        records.append({
            "source": original,
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "alpha_bounds": list(bounds),
            "file": filename,
            "width": width,
            "height": height,
            "bytes": output.stat().st_size,
            "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        })
    (destination / "assets.json").write_text(
        json.dumps({"license": "LicenseRef-Cardchemy-Brand-Assets", "terms": "/legal/BRANDING.md", "exports": records}, indent=2) + "\n",
        encoding="utf-8",
    )
    for record in records:
        print(f"{record['file']}: {record['width']}x{record['height']}, {record['bytes']} bytes")


if __name__ == "__main__":
    main()
