"""Create a non-overwriting root .env with independent generated secrets."""

from __future__ import annotations

import base64
import os
from pathlib import Path
import secrets


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / ".env.example"
OUTPUT = ROOT / ".env"


def generated_values() -> dict[str, str]:
    return {
        "POSTGRES_PASSWORD": secrets.token_urlsafe(36),
        "SECRET_KEY": secrets.token_urlsafe(48),
        "GENERATION_SOURCE_ENCRYPTION_KEY": base64.urlsafe_b64encode(
            secrets.token_bytes(32)
        ).decode("ascii").rstrip("="),
    }


def render_environment(template: str) -> str:
    replacements = generated_values()
    found: set[str] = set()
    rendered: list[str] = []

    for line in template.splitlines():
        key, separator, _ = line.partition("=")
        if separator and key in replacements:
            rendered.append(f"{key}={replacements[key]}")
            found.add(key)
        else:
            rendered.append(line)

    missing = replacements.keys() - found
    if missing:
        names = ", ".join(sorted(missing))
        raise RuntimeError(f"Missing secret placeholders in .env.example: {names}")
    return "\n".join(rendered) + "\n"


def main() -> None:
    if OUTPUT.exists():
        raise SystemExit("Refusing to overwrite existing .env")

    content = render_environment(EXAMPLE.read_text(encoding="utf-8"))
    descriptor = os.open(OUTPUT, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
    except BaseException:
        OUTPUT.unlink(missing_ok=True)
        raise

    print("Created .env with independent generated secrets; no values were printed.")


if __name__ == "__main__":
    main()
