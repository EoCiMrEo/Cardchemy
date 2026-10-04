"""Synthetic admission/context projection; no archive, DB, key or provider work."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from uuid import uuid4

import pytest

from app.ai import source_judgment_visual_v5 as contract
from app.ai.source_navigation_context_v1 import resolve_subject_context
from app.services import source_visual_preparation_v5 as preparation
from app.services.source_visual_preparation import PreparedVisualSources
from tests.test_source_judgment_visual import candidates


def fixture(anchored=False):
    now = datetime.now(timezone.utc)
    subject, owner, thread = uuid4(), uuid4(), uuid4()
    question = "How does it work?" if anchored else "What is Bluebird encoding?"
    prior = "Explain Bluebird encoding."
    def message(body, created):
        return contract.AdmissionUserMessage(uuid4(), owner, thread, subject,
            sha256(body.encode()).hexdigest(), created, now + timedelta(days=1))
    snapshot = contract.SubjectAdmissionSnapshot(message(question, now),
        message(prior, now - timedelta(seconds=1)) if anchored else None, 1, "a" * 64, now, not anchored)
    anchor = resolve_subject_context(question, (("user", prior),), raw_navigation_query=None).anchor if anchored else None
    args = dict(db=object(), settings=object(), retriever=object(), subject_id=subject,
        question=question, selections=(object(),), snapshot=snapshot, checked_at=now,
        raw_navigation_query=None if anchored else question,
        preceding_question=prior if anchored else None, anchor=anchor)
    request = contract.v2.build_request(question, candidates(), group_id="G01")
    return args, request


@pytest.mark.parametrize("anchored", [False, True])
async def test_reuses_exact_authorized_page_wire_and_projects_subject_only(monkeypatch, anchored):
    args, old = fixture(anchored)
    bindings = (object(),)
    calls = []
    async def prepare(db, **kwargs):
        calls.append(kwargs)
        return PreparedVisualSources(deepcopy(old), bindings)
    monkeypatch.setattr(preparation, "prepare_visual_sources", prepare)
    actual = await preparation.prepare_visual_sources_v5(**args)
    assert len(calls) == 1 and calls[0]["question"] == args["question"]
    assert actual.bindings == bindings
    assert actual.request["contents"][0]["parts"][1:] == old["contents"][0]["parts"][1:]
    assert actual.request["generationConfig"] == old["generationConfig"]
    envelope = json.loads(actual.request["contents"][0]["parts"][0]["text"])
    assert envelope["question"] == args["question"]
    if anchored:
        assert envelope["referent_context"] == {"literal_subject": "Bluebird encoding",
                                                "purpose": contract.CONTEXT_PURPOSE}
        assert "Explain Bluebird encoding." not in contract.canonical(actual.request).decode()
    else:
        assert contract.canonical(actual.request) == contract.canonical(old)


@pytest.mark.parametrize("mutation", ["subject", "current_hash", "prior_hash", "expired", "anchor", "unresolved"])
async def test_invalid_context_stops_before_archive_preparation(monkeypatch, mutation):
    args, _ = fixture(True)
    snapshot = args["snapshot"]
    if mutation == "subject":
        args["subject_id"] = uuid4()
    elif mutation == "current_hash":
        args["snapshot"] = replace(snapshot, current=replace(snapshot.current, content_sha256="b" * 64))
    elif mutation == "prior_hash":
        args["preceding_question"] = "Explain a different topic."
    elif mutation == "expired":
        args["checked_at"] += timedelta(days=2)
    elif mutation == "anchor":
        args["anchor"] = replace(args["anchor"], subject="another topic")
    else:
        args["snapshot"] = replace(snapshot, preceding=None)
        args["preceding_question"] = args["anchor"] = None
    async def prepare(*args, **kwargs):
        pytest.fail("invalid context reached archive preparation")
    monkeypatch.setattr(preparation, "prepare_visual_sources", prepare)
    with pytest.raises(contract.VisualSourceJudgmentError):
        await preparation.prepare_visual_sources_v5(**args)


async def test_wrong_prepared_current_question_is_rejected(monkeypatch):
    args, old = fixture(True)
    old["contents"][0]["parts"][0]["text"] = '{"group_id":"G01","question":"different"}'
    async def prepare(*args, **kwargs):
        return PreparedVisualSources(old, ())
    monkeypatch.setattr(preparation, "prepare_visual_sources", prepare)
    with pytest.raises(contract.VisualSourceJudgmentError, match="prepared_question_binding_invalid"):
        await preparation.prepare_visual_sources_v5(**args)
