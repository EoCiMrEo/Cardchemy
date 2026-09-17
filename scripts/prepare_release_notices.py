"""Synchronize distribution notices from their canonical root documents."""
from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAMES = ("LICENSE", "NOTICE", "BRANDING.md")
DESTINATIONS = ("backend/legal", "frontend/public/legal")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    for destination in DESTINATIONS:
        directory = ROOT / destination
        if not arguments.check:
            directory.mkdir(parents=True, exist_ok=True)
        for name in NAMES:
            content = (ROOT / name).read_bytes()
            target = directory / name
            if arguments.check:
                if not target.is_file() or target.read_bytes() != content:
                    print(f"Distribution notice is stale: {destination}/{name}")
                    return 1
            else:
                target.write_bytes(content)
    print("Canonical code and separate brand notices verified" if arguments.check
          else "Canonical distribution notices synchronized")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
