"""Keyless contracts for the private original-PDF gold freeze boundary."""

from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "freeze_private_source_gold_v4.py"
SPEC = importlib.util.spec_from_file_location("freeze_private_source_gold_v4", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def authored():
    forms = ["direct"] * 4 + ["paraphrase"] * 4 + ["followup"] * 4
    return {"schema": "private_source_gold_v4_authored",
            "reviewer_kind": "agent_self_review",
            "review_method": "authenticated_original_pdf_browser",
            "candidate_selection_seen": False,
            "reviewed_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "cases": [
                {"case_id": f"T{index:02}", "form": form,
                 "question": f"What does example {index} explain?",
                 "previous_turn": "Which topic is being discussed?" if form == "followup" else "",
                 "document_slot": 1 + (index % 3), "page_number": index,
                 "page_useful": "Yes"}
                for index, form in enumerate(forms, 1)
            ]}


def test_balanced_review_accepts_distinct_pages_without_database():
    rows = module._validate(authored())
    assert len(rows) == 12
    assert {row["form"] for row in rows} == {"direct", "paraphrase", "followup"}


@pytest.mark.parametrize("mutation", [
    lambda value: value["cases"][1].update(document_slot=value["cases"][0]["document_slot"],
                                            page_number=value["cases"][0]["page_number"]),
    lambda value: value["cases"][8].update(previous_turn=""),
    lambda value: value.update(candidate_selection_seen=True),
    lambda value: value["cases"][0].update(page_useful="Unsure"),
    lambda value: value["cases"][0].update(form="followup"),
    lambda value: value["cases"][1].update(question=value["cases"][0]["question"]),
])
def test_rejects_nonindependent_or_incomplete_review(mutation):
    value = authored()
    mutation(value)
    with pytest.raises(ValueError):
        module._validate(value)


def test_temp_input_requires_exact_digest(tmp_path):
    source = tmp_path / "authored.json"
    source.write_text(json.dumps(authored()), encoding="utf-8")
    digest = __import__("hashlib").sha256(source.read_bytes()).hexdigest()
    assert module._temp_input(source, digest)["schema"] == "private_source_gold_v4_authored"
    with pytest.raises(ValueError, match="input_digest_changed"):
        module._temp_input(source, "0" * 64)
