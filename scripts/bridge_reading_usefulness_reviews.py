"""Carry forward unchanged blind judgments into a revised public audit packet.

Only exact question/context/template and exact source window/offset identities
may be carried. Changed candidates receive a new, separately blinded review.
The bridge never creates labels or scores a model. Its receipt preserves the
provenance of every row in the two complete review files consumed by assembly.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from tempfile import gettempdir

import acquire_reading_usefulness_corpus as corpus


class BridgeError(ValueError):
    pass


BLIND_GROUP_KEYS = {"id", "relation_family", "question_form", "question",
                    "prior_question_context_if_followup", "source_document_sha256",
                    "source_document_path_author_aid", "candidates"}
OFFSET_KEYS = {"page_number", "start", "end", "page_text_sha256"}


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise BridgeError(reason)


def pinned(ref: dict) -> tuple[dict, str]:
    require(type(ref) is dict and set(ref) == {"path", "sha256"}, "reference")
    path = Path(ref["path"])
    temp = Path(gettempdir()).resolve()
    require(path.is_absolute() and path.parent.resolve() == temp and
            path.is_file() and not path.is_symlink() and
            path.stat().st_size <= 4 * 1024 * 1024, "temp_input")
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    require(digest == ref["sha256"], "input_hash")
    try:
        data = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise BridgeError("input_json") from exc
    require(type(data) is dict, "input_object")
    return data, digest


def exclusive(path: Path, value: dict) -> str:
    require(path.is_absolute() and path.parent.resolve() ==
            Path(gettempdir()).resolve() and not path.exists() and
            not path.is_symlink(), "temp_output")
    raw = corpus.canonical_bytes(value)
    with path.open("xb") as stream:
        stream.write(raw)
    return hashlib.sha256(raw).hexdigest()


def _projection(draft: dict, blind: dict, mapping: dict,
                draft_sha: str, blind_sha: str) -> list[dict]:
    groups = draft.get("groups")
    require(type(groups) is list and len(groups) == 96 and
            set(blind) == {"schema", "corpus_id", "manifest_sha256",
                           "groups", "review_instruction"} and
            blind.get("schema") == "cardchemy_reading_usefulness_blind_review_v2" and
            blind.get("corpus_id") == draft.get("corpus_id") and
            blind.get("manifest_sha256") == draft.get("manifest_sha256") and
            type(blind.get("groups")) is list and len(blind["groups"]) == 96 and
            set(mapping) == {"schema", "author_draft_sha256",
                             "blind_packet_sha256", "groups"} and
            mapping.get("schema") == "cardchemy_reading_usefulness_blind_mapping_v1" and
            mapping.get("author_draft_sha256") == draft_sha and
            mapping.get("blind_packet_sha256") == blind_sha and
            type(mapping.get("groups")) is list and len(mapping["groups"]) == 96,
            "projection_identity")
    require(all(type(row) is dict and type(row.get("id")) is str
                for row in groups) and
            len({row["id"] for row in groups}) == 96 and
            all(type(row) is dict and set(row) == BLIND_GROUP_KEYS and
                type(row["id"]) is str and type(row["candidates"]) is list and
                len(row["candidates"]) == 4 for row in blind["groups"]) and
            all(type(row) is dict and set(row) == {
                "opaque_group_id", "author_group_id", "split", "candidates"} and
                type(row["candidates"]) is list and len(row["candidates"]) == 4
                for row in mapping["groups"]), "projection_groups")
    visible = {row["id"]: row for row in blind["groups"]}
    hidden = {row["author_group_id"]: row for row in mapping["groups"]}
    require(len(visible) == len(hidden) == 96, "projection_groups")
    result = []
    all_candidate_ids = set()
    for group in groups:
        author_id = group["id"]
        require(author_id in hidden, "projection_group_missing")
        entry = hidden[author_id]
        require(entry["opaque_group_id"] in visible and
                entry["split"] == group["split"], "projection_group_link")
        projected = visible[entry["opaque_group_id"]]
        require(projected["source_document_path_author_aid"] ==
                group.get("source_document_path_author_aid", group.get("source_pdf")),
                "projection_source")
        for key in ("relation_family", "question_form", "question",
                    "prior_question_context_if_followup", "source_document_sha256"):
            require(projected[key] == group[key], "projection_question")
        expected = group["four_exact_candidate_windows"]
        offsets = group["page_number_and_text_offsets_for_each_window"]
        require(len(expected) == len(offsets) == len(entry["candidates"]) == 4,
                "projection_candidates")
        require(all(type(row) is dict and set(row) == {
                    "id", "exact_window", "source_offset"} and
                    type(row["id"]) is str and type(row["source_offset"]) is dict and
                    set(row["source_offset"]) == OFFSET_KEYS
                    for row in projected["candidates"]), "projection_candidates")
        candidates = {row["id"]: row for row in projected["candidates"]}
        require(len(candidates) == 4 and not all_candidate_ids.intersection(candidates),
                "projection_candidates")
        all_candidate_ids.update(candidates)
        by_index = {}
        for row in entry["candidates"]:
            require(type(row) is dict and set(row) == {
                "opaque_candidate_id", "author_candidate_index"},
                "projection_candidate_link")
            index = row["author_candidate_index"]
            cid = row["opaque_candidate_id"]
            require(type(index) is int and index in range(4) and
                    index not in by_index and cid in candidates and
                    candidates[cid]["exact_window"] == expected[index] and
                    candidates[cid]["source_offset"] == offsets[index],
                    "projection_candidate_link")
            by_index[index] = cid
        require(set(by_index) == set(range(4)), "projection_candidate_coverage")
        result.append({"author": group, "opaque_group_id": projected["id"],
                       "visible": projected, "candidate_ids": by_index})
    return result


def derive(config: dict) -> tuple[dict, dict, dict]:
    require(set(config) == {"schema", "scope", "old_draft", "old_blind",
            "old_mapping", "new_draft", "new_blind", "new_mapping",
            "allowed_question_rewrites"} and
            config["schema"] == "cardchemy_reading_review_bridge_config_v1" and
            config["scope"] in {"train", "evaluation"}, "config")
    values = {key: pinned(config[key]) for key in (
        "old_draft", "old_blind", "old_mapping", "new_draft", "new_blind",
        "new_mapping")}
    require(values["old_draft"][0].get("corpus_id") ==
            values["new_draft"][0].get("corpus_id") and
            values["old_draft"][0].get("manifest_sha256") ==
            values["new_draft"][0].get("manifest_sha256"),
            "corpus_changed")
    old = _projection(values["old_draft"][0], values["old_blind"][0],
                      values["old_mapping"][0], values["old_draft"][1],
                      values["old_blind"][1])
    new = _projection(values["new_draft"][0], values["new_blind"][0],
                      values["new_mapping"][0], values["new_draft"][1],
                      values["new_blind"][1])
    rewrites = {tuple(row) for row in config["allowed_question_rewrites"]}
    require(all(len(pair) == 2 and all(type(x) is str for x in pair)
                for pair in rewrites), "rewrite_config")
    seen_rewrites = set()
    links = []
    changed = set()
    for left, right in zip(old, new, strict=True):
        a, b = left["author"], right["author"]
        require(all(a[key] == b[key] for key in
                    ("split", "relation_family", "question_form",
                     "source_document_sha256")),
                "source_or_form_changed")
        require(a["split"] in ({"train"} if config["scope"] == "train" else
                               {"calibration", "heldout"}), "scope")
        identity = (a["id"], b["id"])
        question_same = all(a[key] == b[key] for key in
                            ("id", "question", "prior_question_context_if_followup",
                             "question_template_id", "question_template"))
        if not question_same:
            require(identity in rewrites, "unregistered_question_rewrite")
            seen_rewrites.add(identity)
        group_changed = False
        for index in range(4):
            old_id, new_id = left["candidate_ids"][index], right["candidate_ids"][index]
            same = question_same and (
                a["four_exact_candidate_windows"][index] ==
                b["four_exact_candidate_windows"][index] and
                a["page_number_and_text_offsets_for_each_window"][index] ==
                b["page_number_and_text_offsets_for_each_window"][index])
            if not same:
                changed.add(new_id)
                group_changed = True
            links.append({"old_candidate_id": old_id,
                          "new_candidate_id": new_id,
                          "old_group_id": left["opaque_group_id"],
                          "new_group_id": right["opaque_group_id"],
                          "source_pdf": right["visible"]["source_document_path_author_aid"],
                          "page_number": b["page_number_and_text_offsets_for_each_window"][index]["page_number"],
                          "changed": not same})
        require(a["authored_by"] == b["authored_by"] or group_changed,
                "unmodified_group_author_changed")
    require(seen_rewrites == rewrites and len(links) == 384 and changed,
            "rewrite_or_delta_coverage")
    packet_groups = []
    for group in values["new_blind"][0]["groups"]:
        candidates = [row for row in group["candidates"] if row["id"] in changed]
        if candidates:
            packet_groups.append({**{key: value for key, value in group.items()
                                     if key != "candidates"},
                                  "candidates": candidates})
    packet = {"schema": "cardchemy_reading_review_delta_v1",
              "full_packet_sha256": values["new_blind"][1],
              "corpus_id": values["new_blind"][0]["corpus_id"],
              "manifest_sha256": values["new_blind"][0]["manifest_sha256"],
              "groups": packet_groups,
              "review_instruction": "Review every displayed original PDF page and exact cue independently; partial context may be useful, a topic mention alone is not. Mark uncertainty."}
    bridge = {"schema": "cardchemy_reading_review_bridge_v1",
              "scope": config["scope"], "full_packet_sha256": values["new_blind"][1],
              "old_packet_sha256": values["old_blind"][1],
              "links": links}
    return packet, bridge, values


def _candidate_identity(packet: dict) -> dict[str, tuple[str, str, int]]:
    groups = packet.get("groups")
    require(type(groups) is list, "packet_groups")
    result = {}
    for group in groups:
        require(type(group) is dict and type(group.get("id")) is str and
                type(group.get("source_document_path_author_aid")) is str and
                type(group.get("candidates")) is list, "packet_group")
        for candidate in group["candidates"]:
            cid = candidate["id"]
            require(type(cid) is str and cid not in result and
                    type(candidate.get("source_offset")) is dict and
                    type(candidate["source_offset"].get("page_number")) is int,
                    "packet_candidate")
            result[cid] = (group["id"],
                           group["source_document_path_author_aid"],
                           candidate["source_offset"]["page_number"])
    return result


def _checked_reviews(packet: dict, packet_sha: str, first: dict,
                     first_sha: str, second: dict, second_sha: str,
                     adjudication: dict, authors: set[str]) -> tuple[dict, dict, dict]:
    expected = _candidate_identity(packet)
    groups = packet["groups"]
    results = []
    for review in (first, second):
        reviewer = review.get("reviewer_id")
        rows = review.get("judgments")
        require(type(reviewer) is str and reviewer.strip() and
                reviewer not in authors and
                review.get("packet_sha256") == packet_sha and
                review.get("reviewed_group_count") == len(groups) and
                review.get("reviewed_candidate_count") == len(expected) and
                type(rows) is list and len(rows) == len(expected),
                "review_identity")
        by_id = {}
        for row in rows:
            cid = row.get("id")
            require(type(cid) is str and cid in expected and cid not in by_id and
                    set(row) == {"id", "group_id", "source_pdf", "page_number",
                                 "original_page_useful", "exact_visible_cue_useful",
                                 "uncertain", "reason"} and
                    (row["group_id"], row["source_pdf"], row["page_number"]) ==
                    expected[cid] and
                    all(type(row[key]) is bool for key in
                        ("original_page_useful", "exact_visible_cue_useful", "uncertain")) and
                    (not row["exact_visible_cue_useful"] or
                     row["original_page_useful"]) and
                    type(row["reason"]) is str and row["reason"].strip(),
                    "review_row")
            by_id[cid] = row
        results.append((reviewer, by_id))
    require(results[0][0] != results[1][0] and first_sha != second_sha,
            "reviewer_independence")
    require(adjudication.get("schema") ==
            "cardchemy_reading_usefulness_adjudication_v1" and
            adjudication.get("blind_packet_sha256") == packet_sha and
            adjudication.get("review_sha256") == sorted((first_sha, second_sha)) and
            type(adjudication.get("rows")) is list, "adjudication_identity")
    needed = set()
    for cid in expected:
        a, b = results[0][1][cid], results[1][1][cid]
        if (a["uncertain"] or b["uncertain"] or
            (a["original_page_useful"], a["exact_visible_cue_useful"]) !=
            (b["original_page_useful"], b["exact_visible_cue_useful"])):
            needed.add(cid)
    adjudicated = {}
    for row in adjudication["rows"]:
        cid = row.get("candidate_id")
        require(type(cid) is str and cid in needed and cid not in adjudicated and
                set(row) == {"candidate_id", "adjudicator_id",
                             "original_page_useful", "exact_cue_useful",
                             "resolution_reason"} and
                type(row["adjudicator_id"]) is str and
                row["adjudicator_id"].strip() and
                row["adjudicator_id"] not in
                {results[0][0], results[1][0], *authors} and
                type(row["original_page_useful"]) is bool and
                type(row["exact_cue_useful"]) is bool and
                (not row["exact_cue_useful"] or row["original_page_useful"]) and
                type(row["resolution_reason"]) is str and
                row["resolution_reason"].strip(), "adjudication_row")
        adjudicated[cid] = row
    require(set(adjudicated) == needed, "adjudication_coverage")
    return results[0][1], results[1][1], adjudicated


def merge(merge_config: dict) -> tuple[dict, dict, dict, dict]:
    require(set(merge_config) == {"schema", "bridge_config", "delta_packet",
            "bridge_map", "old_review_a", "old_review_b", "old_adjudication",
            "delta_review_a", "delta_review_b", "delta_adjudication"} and
            merge_config["schema"] == "cardchemy_reading_review_merge_config_v1",
            "merge_config")
    config, _ = pinned(merge_config["bridge_config"])
    expected_delta, expected_bridge, values = derive(config)
    delta, delta_sha = pinned(merge_config["delta_packet"])
    bridge, bridge_sha = pinned(merge_config["bridge_map"])
    require(delta == expected_delta and bridge == {
                **expected_bridge, "delta_packet_sha256": delta_sha},
            "bridge_projection_mismatch")
    old_a, old_a_sha = pinned(merge_config["old_review_a"])
    old_b, old_b_sha = pinned(merge_config["old_review_b"])
    old_adj, old_adj_sha = pinned(merge_config["old_adjudication"])
    new_a, new_a_sha = pinned(merge_config["delta_review_a"])
    new_b, new_b_sha = pinned(merge_config["delta_review_b"])
    new_adj, new_adj_sha = pinned(merge_config["delta_adjudication"])
    authors = {group["authored_by"] for key in ("old_draft", "new_draft")
               for group in values[key][0]["groups"]}
    old_reviews = _checked_reviews(values["old_blind"][0],
                                   values["old_blind"][1], old_a, old_a_sha,
                                   old_b, old_b_sha, old_adj, authors)
    delta_reviews = _checked_reviews(delta, delta_sha, new_a, new_a_sha,
                                     new_b, new_b_sha, new_adj, authors)
    full_expected = _candidate_identity(values["new_blind"][0])
    delta_expected = _candidate_identity(delta)
    require(len(full_expected) == 384 and
            set(delta_expected) == {row["new_candidate_id"] for row in bridge["links"]
                                    if row["changed"]}, "delta_coverage")
    composite_ids = [f"v4_bridge_{config['scope']}_{side}" for side in ("a", "b")]
    require(set(composite_ids).isdisjoint(authors), "composite_reviewer_identity")
    complete = [{"reviewer_id": reviewer_id,
                 "packet_sha256": values["new_blind"][1],
                 "reviewed_group_count": 96, "reviewed_candidate_count": 384,
                 "judgments": []} for reviewer_id in composite_ids]
    adjudicated = []
    for link in bridge["links"]:
        old_cid, new_cid = link["old_candidate_id"], link["new_candidate_id"]
        source = delta_reviews if link["changed"] else old_reviews
        source_cid = new_cid if link["changed"] else old_cid
        group_id, pdf, page = full_expected[new_cid]
        require((group_id, pdf, page) ==
                (link["new_group_id"], link["source_pdf"], link["page_number"]),
                "new_candidate_identity")
        for index in range(2):
            original = source[index][source_cid]
            complete[index]["judgments"].append({**original,
                "id": new_cid, "group_id": group_id,
                "source_pdf": pdf, "page_number": page})
        if source_cid in source[2]:
            adjudicated.append({**source[2][source_cid], "candidate_id": new_cid})
    for review in complete:
        review["judgments"].sort(key=lambda row: row["id"])
    adjudicated.sort(key=lambda row: row["candidate_id"])
    require(len({row["id"] for row in complete[0]["judgments"]}) == 384,
            "merged_coverage")
    complete_sha = [hashlib.sha256(corpus.canonical_bytes(row)).hexdigest()
                    for row in complete]
    final_adjudication = {
        "schema": "cardchemy_reading_usefulness_adjudication_v1",
        "blind_packet_sha256": values["new_blind"][1],
        "review_sha256": sorted(complete_sha), "rows": adjudicated}
    # Recheck the composite as a complete independently sourced packet.
    _checked_reviews(values["new_blind"][0], values["new_blind"][1],
                     complete[0], complete_sha[0], complete[1], complete_sha[1],
                     final_adjudication, authors)
    receipt = {
        "schema": "cardchemy_reading_review_bridge_receipt_v1",
        "scope": config["scope"], "bridge_map_sha256": bridge_sha,
        "old_packet_sha256": values["old_blind"][1],
        "new_packet_sha256": values["new_blind"][1],
        "delta_packet_sha256": delta_sha,
        "old_review_sha256": [old_a_sha, old_b_sha],
        "old_adjudication_sha256": old_adj_sha,
        "delta_review_sha256": [new_a_sha, new_b_sha],
        "delta_adjudication_sha256": new_adj_sha,
        "actual_old_reviewer_ids": [old_a["reviewer_id"], old_b["reviewer_id"]],
        "actual_delta_reviewer_ids": [new_a["reviewer_id"], new_b["reviewer_id"]],
        "composite_reviewer_ids": composite_ids,
        "complete_review_sha256": complete_sha,
        "complete_adjudication_sha256": hashlib.sha256(
            corpus.canonical_bytes(final_adjudication)).hexdigest(),
        "carried_candidates": sum(not row["changed"] for row in bridge["links"]),
        "newly_reviewed_candidates": len(delta_expected),
        "status": "review_provenance_bridged_no_model_score",
    }
    return complete[0], complete[1], final_adjudication, receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    project = commands.add_parser("project")
    project.add_argument("--config", type=Path, required=True)
    project.add_argument("--config-sha256", required=True)
    project.add_argument("--delta-output", type=Path, required=True)
    project.add_argument("--bridge-output", type=Path, required=True)
    merged = commands.add_parser("merge")
    merged.add_argument("--config", type=Path, required=True)
    merged.add_argument("--config-sha256", required=True)
    merged.add_argument("--review-a-output", type=Path, required=True)
    merged.add_argument("--review-b-output", type=Path, required=True)
    merged.add_argument("--adjudication-output", type=Path, required=True)
    merged.add_argument("--receipt-output", type=Path, required=True)
    args = parser.parse_args()
    try:
        config, _ = pinned({"path": str(args.config),
                            "sha256": args.config_sha256})
        if args.command == "project":
            packet, bridge, _ = derive(config)
            delta_sha = exclusive(args.delta_output, packet)
            bridge["delta_packet_sha256"] = delta_sha
            bridge_sha = exclusive(args.bridge_output, bridge)
            print(json.dumps({"status": "delta_blind_packet_created_no_scoring",
                              "changed_candidates": sum(row["changed"] for row in bridge["links"]),
                              "carried_candidates": sum(not row["changed"] for row in bridge["links"]),
                              "delta_packet_sha256": delta_sha,
                              "bridge_sha256": bridge_sha}, sort_keys=True))
        else:
            a, b, adjudication, receipt = merge(config)
            refs = ((args.review_a_output, a), (args.review_b_output, b),
                    (args.adjudication_output, adjudication),
                    (args.receipt_output, receipt))
            require(len({path for path, _ in refs}) == 4 and
                    all(not path.exists() for path, _ in refs), "outputs_exist")
            hashes = [exclusive(path, value) for path, value in refs]
            print(json.dumps({"status": receipt["status"],
                              "review_sha256": hashes[:2],
                              "adjudication_sha256": hashes[2],
                              "receipt_sha256": hashes[3],
                              "carried_candidates": receipt["carried_candidates"],
                              "newly_reviewed_candidates": receipt["newly_reviewed_candidates"]},
                             sort_keys=True))
    except (BridgeError, OSError, KeyError, TypeError, IndexError) as exc:
        raise SystemExit(f"Review bridge refused: {exc}") from None
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
