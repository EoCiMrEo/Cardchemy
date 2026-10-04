"""Pure v7 display scoring with unchanged independently signed v6 reviews.

The bridge accepts only identical current questions and issued source parts.
The sole permitted wire difference is visual-v3's admission-bound literal
subject envelope/system suffix. Changed pages, cues, images or questions need
a new independent review. Inputs are caller-supplied SHA-bound bytes; this
module performs no file, settings, provider, clock or database access.

Diagnostic admission snapshots (including synthetic IDs) do not prove SQL
ordering, source authorization or actual provider execution. Those remain
separate runtime/integration evidence. A component pass never enables Ask.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from hashlib import sha256
import json
import re
from uuid import UUID

from app.ai import source_judgment_visual_v3 as context
from app.ai.source_navigation_context_v1 import resolve_subject_context
import score_private_source_display_v6 as legacy
from navigation_raw_query_projection_v1 import RawQueryResolver


SCHEMA = "private_source_display_v7"
POLICY = "related_knowledge_navigation_v7"
CONTRACT = "visual_source_id_v3"
MAX_REQUEST_PACKET_BYTES = 48 * 1024 * 1024
ScoreError = legacy.ScoreError
require = legacy.require
FORMS = legacy.FORMS
SEEDS = legacy.SEEDS
INTEGRITY = legacy.INTEGRITY


def _encode(value: object) -> bytes:
    return context.canonical(value)


def _legacy_request_bytes(value: object) -> bytes:
    # The consumed v6 review generator used ASCII JSON for its request hash.
    # Keep that historical identity; actual visual-v3 HTTP uses UTF-8 JSON.
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _packet(raw: bytes, expected: str) -> dict:
    require(type(raw) is bytes and 0 < len(raw) <= MAX_REQUEST_PACKET_BYTES
            and legacy._sha(expected) and sha256(raw).hexdigest() == expected,
            "request_packet_sha_invalid")
    try:
        value = json.loads(raw, object_pairs_hook=legacy._unique, parse_constant=legacy._constant)
    except (UnicodeError, ValueError, RecursionError):
        raise ScoreError("request_packet_invalid") from None
    require(type(value) is dict, "request_packet_invalid")
    return value


def _utc(value: object) -> datetime:
    require(type(value) is str and re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)", value) is not None,
        "context_time_invalid")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ScoreError("context_time_invalid") from None


def _uuid(value: object) -> UUID:
    require(type(value) is str, "context_identity_invalid")
    try:
        result = UUID(value)
    except ValueError:
        raise ScoreError("context_identity_invalid") from None
    require(result.int > 0 and str(result) == value, "context_identity_invalid")
    return result


def admission_packet(snapshot: context.SubjectAdmissionSnapshot) -> dict:
    """Serialize a supplied pure snapshot; do not create message identities."""
    require(type(snapshot) is context.SubjectAdmissionSnapshot, "context_snapshot_invalid")
    return {"schema_version": snapshot.schema_version,
            "current": context._message_identity(snapshot.current),
            "preceding": context._message_identity(snapshot.preceding) if snapshot.preceding else None,
            "corpus_revision": snapshot.corpus_revision,
            "embedding_space_hash": snapshot.embedding_space_hash,
            "captured_at": snapshot.captured_at.isoformat(),
            "raw_question_clear": snapshot.raw_question_clear}


def _message(value: object) -> context.AdmissionUserMessage:
    require(type(value) is dict and set(value) == {
        "message_id", "user_id", "thread_id", "subject_id", "content_sha256",
        "role", "created_at", "expires_at"}, "context_message_invalid")
    return context.AdmissionUserMessage(
        *(_uuid(value[key]) for key in ("message_id", "user_id", "thread_id", "subject_id")),
        value["content_sha256"], _utc(value["created_at"]), _utc(value["expires_at"]), value["role"])


def _snapshot(value: object) -> context.SubjectAdmissionSnapshot:
    require(type(value) is dict and set(value) == {
        "schema_version", "current", "preceding", "corpus_revision", "embedding_space_hash",
        "captured_at", "raw_question_clear"}, "context_snapshot_invalid")
    return context.SubjectAdmissionSnapshot(
        _message(value["current"]), _message(value["preceding"]) if value["preceding"] is not None else None,
        value["corpus_revision"], value["embedding_space_hash"], _utc(value["captured_at"]),
        value["raw_question_clear"], value["schema_version"])


def _review(roster_bytes: bytes, labels_bytes: bytes, receipt_bytes: bytes, *,
            roster_sha: str, labels_sha: str, receipt_sha: str, trusted_key_sha: str) -> tuple[dict, dict]:
    """Use the unchanged v6 validator, discarding its zero-observation metrics."""
    roster = legacy._bound(roster_bytes, roster_sha)
    labels = legacy._bound(labels_bytes, labels_sha)
    legacy._roster(roster)
    checked = legacy._time(labels.get("frozen_at_utc")) + timedelta(microseconds=1)
    validation_only = {"schema": legacy.SCHEMA + "_measurement", "policy": legacy.POLICY,
        "contract": legacy.CONTRACT, "runtime_sha256": roster["runtime_sha256"],
        "roster_sha256": roster_sha, "labels_sha256": labels_sha,
        "executed_at_utc": checked.isoformat().replace("+00:00", "Z"), "cases": []}
    raw = _encode(validation_only)
    legacy.score(roster_bytes, labels_bytes, raw, roster_sha256=roster_sha,
        labels_sha256=labels_sha, measurement_sha256=sha256(raw).hexdigest(),
        review_receipt_bytes=receipt_bytes, review_receipt_sha256=receipt_sha,
        trusted_review_key_sha256=trusted_key_sha)
    return roster, labels


def _wire(row: dict, case: dict, *, scope: dict, freeze_time: datetime, gold: dict,
          raw_query_resolver: RawQueryResolver) -> dict:
    """Prove reviewed evidence is unchanged and v3 adds no conversation facts."""
    require(type(row) is dict and set(row) == {"case_id", "legacy_request", "request",
        "admission_snapshot", "raw_navigation_query", "preceding_question", "checked_at_utc", "source_bindings"},
        "request_case_invalid")
    old = row["legacy_request"]
    require(type(old) is dict and case["candidates"]
            and sha256(_legacy_request_bytes(old)).hexdigest() == case["request_sha256"], "fresh_review_required")
    try:
        parts = old["contents"][0]["parts"]
        require(type(parts) is list and len(parts) == 1 + 2 * len(case["candidates"])
                and type(parts[0]) is dict and set(parts[0]) == {"text"}, "reviewed_wire_invalid")
        envelope = json.loads(parts[0]["text"], object_pairs_hook=legacy._unique, parse_constant=legacy._constant)
        require(type(envelope) is dict and set(envelope) == {"group_id", "question"}
                and type(envelope["group_id"]) is str and type(envelope["question"]) is str,
                "reviewed_wire_invalid")
        require(raw_query_resolver(envelope["question"]) == row["raw_navigation_query"],
                "raw_question_binding_invalid")
        require(envelope["question"] == gold["question"]
                and (row["preceding_question"] == (gold["previous_turn"] or None)
                     if row["raw_navigation_query"] is None else row["preceding_question"] is None),
                "fresh_review_required")
        # Provider document IDs are server aliases. Bind them to separately
        # reviewed local UUID/page identities; never hash an alias as a UUID.
        require(type(row["source_bindings"]) is list and len(row["source_bindings"]) == len(case["candidates"]),
                "source_alias_binding_invalid")
        aliases = {}
        for ordinal, candidate in enumerate(case["candidates"]):
            binding = row["source_bindings"][ordinal]
            require(type(binding) is dict and set(binding) == {
                "id", "document_id", "content_revision_id", "page_number"}
                and binding["id"] == candidate["id"]
                and type(binding["page_number"]) is int and binding["page_number"] > 0,
                "source_alias_binding_invalid")
            _uuid(binding["document_id"])
            _uuid(binding["content_revision_id"])
            aliases.setdefault(binding["content_revision_id"], {
                "alias": f"D{len(aliases) + 1:02}", "document_id": binding["document_id"], "pdf_sha256": candidate["pdf_sha256"]})
            alias = aliases[binding["content_revision_id"]]
            require(alias["document_id"] == binding["document_id"] and alias["pdf_sha256"] == candidate["pdf_sha256"],
                    "source_alias_binding_invalid")
            source = json.loads(parts[1 + 2 * ordinal]["text"], object_pairs_hook=legacy._unique,
                                parse_constant=legacy._constant)
            require(type(source) is dict and source["id"] == candidate["id"]
                    and sha256(source["cue"].encode("utf-8")).hexdigest() == candidate["cue_sha256"]
                    and source["pdf_sha256"] == candidate["pdf_sha256"]
                    and source["document_id"] == alias["alias"] and source["page"] == binding["page_number"]
                    and sha256(_encode([binding["document_id"], binding["page_number"]])).hexdigest()
                    == candidate["page_key"], "fresh_review_required")
        require(old["model"] == context.MODEL and old["store"] is False
                and old["generationConfig"]["maxOutputTokens"] == context.MAX_OUTPUT_TOKENS
                and old["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "HIGH"},
                "reviewed_wire_invalid")
    except ScoreError:
        raise
    except (KeyError, IndexError, TypeError, UnicodeError, ValueError, RecursionError):
        raise ScoreError("reviewed_wire_invalid") from None
    snapshot = _snapshot(row["admission_snapshot"])
    checked = _utc(row["checked_at_utc"])
    require(checked <= freeze_time and str(snapshot.current.user_id) == scope["principal_id"]
            and str(snapshot.current.subject_id) == scope["subject_id"]
            and snapshot.corpus_revision == scope["corpus_revision"]
            and snapshot.embedding_space_hash == scope["embedding_space_hash"], "context_scope_invalid")
    history = (("user", row["preceding_question"]),) if row["preceding_question"] is not None else ()
    resolved = resolve_subject_context(envelope["question"], history,
                                      raw_navigation_query=row["raw_navigation_query"])
    try:
        bound = context.bind_question_context(envelope["question"], snapshot, checked_at=checked,
            raw_navigation_query=row["raw_navigation_query"], preceding_question=row["preceding_question"],
            anchor=resolved.anchor)
        require(bound.status != "needs_clarification", "fresh_review_required")
        expected = deepcopy(old)
        if bound.anchor is not None:
            expected["contents"][0]["parts"][0]["text"] = _encode({**envelope, "referent_context": {
                "literal_subject": bound.anchor.subject, "purpose": context.CONTEXT_PURPOSE}}).decode("utf-8")
            expected["systemInstruction"]["parts"][0]["text"] += context.CONTEXT_SYSTEM_SUFFIX
        require(type(row["request"]) is dict and _encode(row["request"]) == _encode(expected),
                "fresh_review_required")
        require(len(_encode(expected)) <= context.MAX_REQUEST_BYTES
                and context.estimate_input_tokens(expected) <= context.MAX_INPUT_TOKENS,
                "request_budget_invalid")
    except context.VisualSourceJudgmentError:
        raise ScoreError("question_context_binding_invalid") from None
    return {"case_id": case["case_id"], "request_sha256": sha256(_encode(expected)).hexdigest(),
            "current_question_sha256": bound.current_question_sha256,
            "admission_sha256": bound.admission_sha256, "context_status": bound.status}


def freeze_bridge(roster_bytes: bytes, labels_bytes: bytes, stage1_bytes: bytes,
                  request_packet_bytes: bytes, *,
                  roster_sha256: str, labels_sha256: str, request_packet_sha256: str,
                  review_receipt_bytes: bytes, review_receipt_sha256: str,
                  trusted_review_key_sha256: str, runtime_sha256: str, frozen_at_utc: str,
                  raw_query_resolver: RawQueryResolver) -> dict:
    """Prepare a new SHA-pinnable v7 bridge before outcomes, without rewriting reviews."""
    roster, labels = _review(roster_bytes, labels_bytes, review_receipt_bytes,
        roster_sha=roster_sha256, labels_sha=labels_sha256, receipt_sha=review_receipt_sha256,
        trusted_key_sha=trusted_review_key_sha256)
    frozen = legacy._time(frozen_at_utc)
    require(legacy._sha(runtime_sha256) and runtime_sha256 != roster["runtime_sha256"]
            and frozen > legacy._time(labels["frozen_at_utc"]), "bridge_runtime_invalid")
    require(type(raw_query_resolver) is RawQueryResolver
            and legacy._sha(raw_query_resolver.source_sha256), "raw_query_resolver_invalid")
    packet = _packet(request_packet_bytes, request_packet_sha256)
    require(set(packet) == {"schema", "legacy_roster_sha256", "scope", "cases"}
            and packet["schema"] == SCHEMA + "_requests" and packet["legacy_roster_sha256"] == roster_sha256
            and type(packet["scope"]) is dict and set(packet["scope"]) == {
                "principal_id", "subject_id", "corpus_revision", "embedding_space_hash"}
            and type(packet["scope"]["corpus_revision"]) is int and packet["scope"]["corpus_revision"] >= 1
            and legacy._sha(packet["scope"]["embedding_space_hash"])
            and type(packet["cases"]) is list, "request_packet_invalid")
    for key in ("principal_id", "subject_id"):
        _uuid(packet["scope"][key])
    cases = legacy._roster(roster)
    stage1 = legacy._bound(stage1_bytes, roster["stage1_sha256"])
    require(type(stage1.get("cases")) is list, "gold_question_binding_invalid")
    questions = {}
    for row in stage1["cases"]:
        require(type(row) is dict and type(row.get("case_id")) is str and row["case_id"] in cases
                and row["case_id"] not in questions and type(row.get("question")) is str
                and 0 < len(row["question"]) <= context.MAX_QUESTION_CHARS
                and type(row.get("previous_turn")) is str,
                "gold_question_binding_invalid")
        questions[row["case_id"]] = row
    require(set(questions) == set(cases), "gold_question_binding_invalid")
    bound, seen = [], set()
    for row in packet["cases"]:
        require(type(row) is dict and type(row.get("case_id")) is str and row["case_id"] in cases
                and row["case_id"] not in seen, "request_case_invalid")
        seen.add(row["case_id"])
        require(_utc(row.get("checked_at_utc")) > legacy._time(labels["frozen_at_utc"]),
                "bridge_time_invalid")
        bound.append(_wire(row, cases[row["case_id"]], scope=packet["scope"], freeze_time=frozen,
                           gold=questions[row["case_id"]], raw_query_resolver=raw_query_resolver))
    require(seen == set(cases), "incomplete_request_binding")
    return {"schema": SCHEMA + "_bridge", "policy": POLICY, "contract": CONTRACT,
            "component": roster["component"], "runtime_sha256": runtime_sha256,
            "legacy_request_encoding": "v6_review_ascii_json_v1",
            "current_request_encoding": "visual_wire_utf8_json_v3",
            "raw_query_source_sha256": raw_query_resolver.source_sha256,
            "legacy_roster_sha256": roster_sha256, "labels_sha256": labels_sha256,
            "review_receipt_sha256": review_receipt_sha256,
            "trusted_review_key_sha256": trusted_review_key_sha256,
            "stage1_sha256": roster["stage1_sha256"], "request_packet_sha256": request_packet_sha256,
            "scope_sha256": sha256(_encode(packet["scope"])).hexdigest(),
            "frozen_at_utc": frozen_at_utc, "cases": sorted(bound, key=lambda row: row["case_id"])}


def score(roster_bytes: bytes, labels_bytes: bytes, stage1_bytes: bytes, request_packet_bytes: bytes,
          bridge_bytes: bytes, measurement_bytes: bytes, *, roster_sha256: str,
          labels_sha256: str, request_packet_sha256: str, bridge_sha256: str,
          measurement_sha256: str, review_receipt_bytes: bytes, review_receipt_sha256: str,
          trusted_review_key_sha256: str, runtime_sha256: str,
          raw_query_resolver: RawQueryResolver) -> dict:
    """Validate the new wire/runtime and every observation before unchanged metric reuse."""
    bridge = legacy._bound(bridge_bytes, bridge_sha256)
    expected = freeze_bridge(roster_bytes, labels_bytes, stage1_bytes, request_packet_bytes,
        roster_sha256=roster_sha256, labels_sha256=labels_sha256,
        request_packet_sha256=request_packet_sha256, review_receipt_bytes=review_receipt_bytes,
        review_receipt_sha256=review_receipt_sha256, trusted_review_key_sha256=trusted_review_key_sha256,
        runtime_sha256=runtime_sha256, frozen_at_utc=bridge.get("frozen_at_utc"),
        raw_query_resolver=raw_query_resolver)
    require(bridge == expected, "bridge_binding_invalid")
    measured = legacy._bound(measurement_bytes, measurement_sha256)
    require(set(measured) == {"schema", "policy", "contract", "runtime_sha256", "bridge_sha256",
        "executed_at_utc", "cases"} and measured["schema"] == SCHEMA + "_measurement"
        and measured["policy"] == POLICY and measured["contract"] == CONTRACT
        and measured["runtime_sha256"] == runtime_sha256 and measured["bridge_sha256"] == bridge_sha256
        and legacy._time(measured["executed_at_utc"]) > legacy._time(bridge["frozen_at_utc"])
        and type(measured["cases"]) is list, "measurement_binding_invalid")
    rows = {row["case_id"]: row for row in bridge["cases"]}
    packets = {row["case_id"]: row for row in _packet(request_packet_bytes, request_packet_sha256)["cases"]}
    projected, context_failures = [], 0
    extras = {"request_sha256", "admission_sha256", "embedding_input_sha256", "context_rechecked"}
    for row in measured["cases"]:
        require(type(row) is dict and extras <= set(row) and type(row.get("case_id")) is str
                and row["case_id"] in rows and type(row["context_rechecked"]) is bool,
                "measurement_context_invalid")
        binding = rows[row["case_id"]]
        require(row["request_sha256"] == binding["request_sha256"]
                and row["admission_sha256"] == binding["admission_sha256"]
                and row["embedding_input_sha256"] == binding["current_question_sha256"],
                "measurement_context_invalid")
        try:
            context.admission_identity(_snapshot(packets[row["case_id"]]["admission_snapshot"]),
                                       checked_at=legacy._time(measured["executed_at_utc"]))
        except context.VisualSourceJudgmentError:
            raise ScoreError("measurement_context_invalid") from None
        context_failures += not row["context_rechecked"]
        projected.append({key: value for key, value in row.items() if key not in extras})
    # This is an internal compatibility projection, not a v6 execution receipt.
    roster = legacy._bound(roster_bytes, roster_sha256)
    compatibility = {"schema": legacy.SCHEMA + "_measurement", "policy": legacy.POLICY,
        "contract": legacy.CONTRACT, "runtime_sha256": roster["runtime_sha256"],
        "roster_sha256": roster_sha256, "labels_sha256": labels_sha256,
        "executed_at_utc": measured["executed_at_utc"], "cases": projected}
    raw = _encode(compatibility)
    result = legacy.score(roster_bytes, labels_bytes, raw, roster_sha256=roster_sha256,
        labels_sha256=labels_sha256, measurement_sha256=sha256(raw).hexdigest(),
        review_receipt_bytes=review_receipt_bytes, review_receipt_sha256=review_receipt_sha256,
        trusted_review_key_sha256=trusted_review_key_sha256)
    result["gates"]["admission_context"] = context_failures == 0
    result.update(schema=SCHEMA + "_aggregate", policy=POLICY, contract=CONTRACT,
        runtime_sha256=runtime_sha256, bridge_sha256=bridge_sha256, unchanged_review_reused=True,
        context_failures=context_failures, component_passed=all(result["gates"].values()))
    return result
