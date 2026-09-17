"""Check required repository context files and active local Markdown links.

Uses only the standard library, reads no application settings, and makes no
network requests. Historical dated logs/archive content are not active guides.
Architecture accuracy still requires human/source review.
"""
from __future__ import annotations

from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    "README.md", "AGENTS.md", "PROJECT-MAP.md", "backend/MOC.md", "frontend/MOC.md",
    "docs/00-START-HERE.md", "docs/README.md", "docs/archive/README.md",
    "docs/development/LOCAL-SETUP.md", "docs/development/CURRENT-STATE.md",
    "docs/architecture/SYSTEM-OVERVIEW.md", "docs/architecture/DATA-MODEL.md",
    "docs/architecture/AUTH-FLOW.md", "docs/architecture/AI-GENERATION-FLOW.md",
    "docs/architecture/STUDY-PROGRESS-FLOW.md", "docs/decisions/ADR-000-INDEX.md",
    "docs/decisions/ADR-001-four-option-cards.md",
    "docs/decisions/ADR-002-server-derived-correctness.md",
    "docs/decisions/ADR-003-completion-and-mastery.md",
    "docs/decisions/ADR-004-alembic-schema-ownership.md",
    "docs/decisions/ADR-005-deletion-cascades.md",
    "docs/decisions/ADR-006-grounded-generation-validation.md",
    "docs/decisions/ADR-007-root-configuration.md",
    "docs/decisions/ADR-008-postgresql-durable-jobs.md",
    "docs/decisions/ADR-009-session-and-role-boundaries.md",
    "docs/decisions/ADR-010-transactional-email.md",
    "docs/decisions/ADR-011-operational-privacy-controls.md",
    "docs/OBSERVABILITY.md", "docs/PRIVACY.md",
    "CONTRIBUTING.md", "SECURITY.md", "CODE_OF_CONDUCT.md", "BRANDING.md", "ROADMAP.md",
    "docs/RELEASING.md", "docs/NAME-REVIEW.md", "docs/DEMO.md",
)
LINK = re.compile(r"!?\[[^\]\n]*\]\((<[^>]+>|[^\s)]+)(?:\s+\"[^\"]*\")?\)")


def prose(path: Path, *, keep_inline: bool = False) -> str:
    """Exclude fenced examples and inline code, retaining lines for diagnostics."""
    lines: list[str] = []
    fence: str | None = None
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        marker = re.match(r"^\s*(`{3,}|~{3,})", line)
        if marker:
            token = marker.group(1)
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            lines.append("")
        elif fence is None:
            lines.append(line if keep_inline else re.sub(r"(`+).*?\1", "", line))
        else:
            lines.append("")
    return "\n".join(lines)


def anchors(path: Path) -> set[str]:
    counts: dict[str, int] = {}
    result: set[str] = set()
    for heading in re.findall(r"^#{1,6}\s+(.+?)\s*#*\s*$", prose(path, keep_inline=True), re.M):
        slug = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
        count = counts.get(slug, 0)
        counts[slug] = count + 1
        result.add(slug if count == 0 else f"{slug}-{count}")
    return result


def validate(root: Path = ROOT) -> tuple[list[str], int, int]:
    errors = [f"Missing or empty required context: {name}" for name in REQUIRED
              if not (root / name).is_file() or not (root / name).read_text(encoding="utf-8-sig").strip()]
    active = {root / name for name in REQUIRED}
    active.update(path for path in (root / "docs").rglob("*.md")
                  if "archive" not in path.relative_to(root / "docs").parts)
    active.update(root / name for name in (
        "CHANGELOG.md", "issues-required-remediation.md",
        "frontend/README.md", ".agent/logs/README.md",
    ))
    active.update(root / name for name in (".agent/README.md", ".agent/MOC.md")
                  if (root / name).is_file())
    link_count = 0
    for path in sorted(active):
        if not path.is_file():
            errors.append(f"Missing active guide: {path.relative_to(root).as_posix()}")
            continue
        content = prose(path)
        for match in LINK.finditer(content):
            target = match.group(1).strip("<>")
            url = urlsplit(target)
            if url.scheme or url.netloc:
                continue
            link_count += 1
            label = f"{path.relative_to(root).as_posix()}:{content.count(chr(10), 0, match.start()) + 1}"
            destination = (path.parent / unquote(url.path)).resolve() if url.path else path.resolve()
            if not destination.is_relative_to(root.resolve()):
                errors.append(f"{label}: local link leaves repository: {target}")
            elif not destination.exists():
                errors.append(f"{label}: missing local target: {target}")
            elif url.fragment and destination.is_file() and destination.suffix.lower() == ".md":
                if unquote(url.fragment) not in anchors(destination):
                    errors.append(f"{label}: missing Markdown heading: {target}")
    return errors, len(active), link_count


def main() -> int:
    errors, files, links = validate()
    if errors:
        print("\n".join(errors))
        return 1
    print(f"Repository context validated: {len(REQUIRED)} required files, {files} active guides, {links} local links.")
    print("Historical bodies and external URLs are excluded; verify behavioral claims against source.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
