"""Freeze visually reviewed private original-PDF gold before v4 selection.

The authored questions and source pointers must live in OS Temp. This reader
uses the current authorized published Subject scope in read-only transactions,
binds exact source revisions and PDF archives, and emits only aggregate stdout.
It never retrieves candidates, calls a provider, or labels model output.
"""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile


SCHEMA = "private_source_gold_v4"
FORMS = ("direct", "paraphrase", "followup")
SHA = re.compile(r"[0-9a-f]{64}\Z")


def _stamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, default=str).encode("utf-8")).hexdigest()


def _temp_input(path: Path, expected_sha: str) -> dict:
    if SHA.fullmatch(expected_sha) is None:
        raise ValueError("invalid_input_digest")
    root = Path(tempfile.gettempdir()).resolve(strict=True)
    resolved = path.resolve(strict=True)
    if (resolved == root or not resolved.is_relative_to(root) or path.is_symlink()
            or any(parent.is_symlink() for parent in path.parents)
            or not resolved.is_file() or resolved.stat().st_size > 64 * 1024):
        raise ValueError("invalid_private_input")
    raw = resolved.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise ValueError("input_digest_changed")
    return json.loads(raw)


def _validate(raw: object) -> list[dict]:
    if (not isinstance(raw, dict) or set(raw) != {
            "schema", "reviewer_kind", "review_method", "candidate_selection_seen",
            "reviewed_at_utc", "cases"
    } or raw["schema"] != SCHEMA + "_authored"
            or raw["reviewer_kind"] != "agent_self_review"
            or raw["review_method"] != "authenticated_original_pdf_browser"
            or raw["candidate_selection_seen"] is not False
            or not isinstance(raw["reviewed_at_utc"], str)
            or not isinstance(raw["cases"], list)):
        raise ValueError("invalid_authored_review")
    try:
        reviewed = datetime.fromisoformat(raw["reviewed_at_utc"].replace("Z", "+00:00"))
        if reviewed.utcoffset() != timezone.utc.utcoffset(reviewed) or reviewed > datetime.now(timezone.utc):
            raise ValueError
    except ValueError:
        raise ValueError("invalid_review_time") from None
    rows = raw["cases"]
    if len(rows) != 12:
        raise ValueError("invalid_case_count")
    counts: Counter[str] = Counter()
    pages: set[tuple[int, int]] = set()
    questions: set[tuple[str, str]] = set()
    for index, row in enumerate(rows, 1):
        if (not isinstance(row, dict) or set(row) != {
                "case_id", "form", "question", "previous_turn", "document_slot",
                "page_number", "page_useful"
        } or row["case_id"] != f"T{index:02}"
                or row["form"] not in FORMS
                or not isinstance(row["question"], str)
                or not 8 <= len(row["question"].strip()) <= 400
                or not isinstance(row["previous_turn"], str)
                or len(row["previous_turn"]) > 400
                or (row["form"] == "followup") != bool(row["previous_turn"].strip())
                or type(row["document_slot"]) is not int
                or not 1 <= row["document_slot"] <= 3
                or type(row["page_number"]) is not int
                or not 1 <= row["page_number"] <= 100
                or row["page_useful"] != "Yes"):
            raise ValueError("invalid_review_case")
        pointer = (row["document_slot"], row["page_number"])
        if pointer in pages:
            raise ValueError("duplicate_gold_page")
        question_key = (" ".join(row["previous_turn"].casefold().split()),
                        " ".join(row["question"].casefold().split()))
        if question_key in questions:
            raise ValueError("duplicate_question")
        pages.add(pointer)
        questions.add(question_key)
        counts[row["form"]] += 1
    if any(counts[form] != 4 for form in FORMS):
        raise ValueError("invalid_form_balance")
    return rows


async def _freeze(rows: list[dict], input_sha: str, output_root: Path) -> dict:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
    from sqlalchemy import text
    from app.database import async_session_maker
    from app.models.knowledge import SubjectDocumentPdf
    from evaluate_private_ask_support_v2 import _eligible_owner_chunks

    async def snapshot() -> tuple[dict, dict]:
        chunks, active, page_text, slots = await _eligible_owner_chunks(with_pages=True, all_pages=True)
        if not active or not chunks:
            raise ValueError("scope_unavailable")
        by_page: dict[tuple[int, int], list] = {}
        for chunk in chunks:
            if chunk.chunk_id in page_text and chunk.document_id in slots:
                by_page.setdefault((slots[chunk.document_id], chunk.page_number), []).append(chunk)
        selected = {}
        for row in rows:
            pointer = (row["document_slot"], row["page_number"])
            matches = by_page.get(pointer, [])
            if not matches or len({(item.document_id, item.content_revision_id,
                                   item.index_revision_id,
                                   hashlib.sha256(page_text[item.chunk_id].encode("utf-8")).hexdigest())
                                  for item in matches}) != 1:
                raise ValueError("gold_page_unavailable")
            chunk = matches[0]
            selected[pointer] = {
                "document_id": str(chunk.document_id),
                "content_revision_id": str(chunk.content_revision_id),
                "index_revision_id": str(chunk.index_revision_id),
                "page_sha256": hashlib.sha256(page_text[chunk.chunk_id].encode("utf-8")).hexdigest(),
                "page_key": _digest([str(chunk.document_id), chunk.page_number]),
            }
        scope = {"corpus_revision": chunks[0].corpus_revision,
                 "embedding_space_hash": chunks[0].embedding_space_hash}
        return scope, selected

    scope, first = await snapshot()
    async with async_session_maker() as db:
        await db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        pdfs = {}
        for pointer, source in first.items():
            from uuid import UUID
            pdf = await db.get(SubjectDocumentPdf, UUID(source["content_revision_id"]))
            if (pdf is None or str(pdf.document_id) != source["document_id"]
                    or pdf.page_count < pointer[1] or pdf.byte_size <= 0):
                raise ValueError("original_pdf_unavailable")
            pdfs[pointer] = {"original_pdf_sha256": pdf.source_sha256,
                             "original_pdf_page_count": pdf.page_count}
        await db.rollback()
    later_scope, later = await snapshot()
    if scope != later_scope or first != later:
        raise ValueError("source_changed_during_freeze")

    result = {
        "schema": SCHEMA + "_stage1", "authored_input_sha256": input_sha,
        "reviewer_kind": "agent_self_review", "review_method": "authenticated_original_pdf_browser",
        "candidate_selection_seen": False, "frozen_at_utc": _stamp(), "scope": scope,
        "cases": [{
            "case_id": row["case_id"], "form": row["form"],
            "question": row["question"], "previous_turn": row["previous_turn"],
            "document_slot": row["document_slot"], "page_number": row["page_number"],
            "page_useful": row["page_useful"],
            **first[(row["document_slot"], row["page_number"])],
            **pdfs[(row["document_slot"], row["page_number"])],
        } for row in rows],
    }
    directory = Path(tempfile.mkdtemp(prefix="cardchemy-v4-private-gold-", dir=output_root))
    directory.chmod(0o700)
    body = json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    target = directory / "stage1-gold.json"
    with target.open("xb") as stream:
        stream.write(body)
    target.chmod(0o600)
    return {"status": "frozen", "case_count": len(rows),
            "forms": dict(Counter(row["form"] for row in rows)),
            "distinct_original_pdfs": len({row["original_pdf_sha256"] for row in result["cases"]}),
            "stage1_sha256": hashlib.sha256(body).hexdigest(),
            "packet_directory": directory.name,
            "provider_requests": 0, "database_writes": 0,
            "candidate_selection_seen": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--authored-input", type=Path)
    parser.add_argument("--authored-sha256")
    args = parser.parse_args()
    if not args.freeze:
        print(json.dumps({"status": "preflight", "provider_requests": 0,
                          "database_reads": 0, "database_writes": 0}))
        return 0
    try:
        if args.authored_input is None or args.authored_sha256 is None:
            raise ValueError("missing_input")
        rows = _validate(_temp_input(args.authored_input, args.authored_sha256))
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
        from build_private_lane6_review_packet import validated_output_root
        from app.database import close_database
        async def run() -> dict:
            try:
                return await _freeze(rows, args.authored_sha256, validated_output_root())
            finally:
                await close_database()
        output = asyncio.run(run())
    except Exception:
        print(json.dumps({"status": "freeze_failed", "provider_requests": 0,
                          "database_writes": 0}))
        return 1
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
