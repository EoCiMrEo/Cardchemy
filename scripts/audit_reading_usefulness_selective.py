"""One-shot public, offline selective source-navigation audit; never an Ask path.

Default invocation validates frozen public inputs without inference. Execution
requires --execute-approved, an external freeze digest, and a distinct fixed
persistent ledger in a networkless, bounded Linux container. The group null
decision and card qualification are separate train-only L2 logistic fits.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
from time import perf_counter
from typing import Callable


PROCEDURE = "mixedbread_public_reading_usefulness_selective_v2"
APPROVED_LEDGER_ROOT = Path("/tmp/cardchemy-reading-usefulness-mixedbread-selective-v2-ledger")
HELPER_NAMES = (
    "acquire_reading_usefulness_corpus.py",
    "derive_reading_usefulness_corpus_v4.py",
    "validate_reading_usefulness_fixture.py",
    "preflight_reading_usefulness_bundle.py",
    "audit_reading_usefulness.py",
)
RUNTIME_SCHEMA = "cardchemy_reading_usefulness_selective_runtime_v1"
NULL_FEATURE_NAMES = (
    "pool_top_logit", "pool_top_second_margin", "pool_top_third_margin",
    "pool_logit_range", "pool_mean_logit", "pool_max_lexical_f1",
    "pool_top_lexical_f1", "pool_top_three_mean_lexical_f1",
    "pool_max_title_overlap", "pool_max_condition_coverage",
    "pool_mean_negation_agreement",
)
CARD_FEATURE_NAMES = (
    "bounded_pair_logit", "within_pool_logit_gap", "pool_top_margin",
    "question_cue_lexical_f1", "question_cue_title_overlap",
    "question_condition_coverage", "question_cue_negation_agreement",
    "displayed_cue_length_fraction",
)
REGULARIZATION = 1.0
MAX_PAIR_TOKENS = 256
MAX_STARTUP_SECONDS = 20.0
MAX_TOTAL_SECONDS = 600.0
MAX_POOL_SECONDS = 5.0
MAX_ADDED_RAM_BYTES = 2 * 1024**3
BATCH_SIZE = 30
MAX_OUTPUT_LINE = 65_536


class AuditError(ValueError):
    """Content-free rejection code."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise AuditError(code)


def digest(path: Path) -> str:
    require(path.is_file() and not path.is_symlink(), "file_missing_or_symlink")
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def canonical_bytes(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True, allow_nan=False) + "\n").encode("utf-8")


def write_exclusive(path: Path, value: dict) -> str:
    raw = canonical_bytes(value)
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return hashlib.sha256(raw).hexdigest()


def read_json_bounded(path: Path, limit: int) -> dict:
    require(path.is_file() and not path.is_symlink() and
            path.stat().st_size <= limit, "receipt_invalid")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(type(value) is dict, "receipt_invalid")
    return value


def read_runtime_manifest(path: Path) -> dict:
    require(path.is_file() and not path.is_symlink() and
            path.stat().st_size <= 100_000, "runtime_manifest_invalid")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    require(type(manifest) is dict and manifest.get("schema") == RUNTIME_SCHEMA and
            type(manifest.get("helper_sha256")) is dict and
            set(manifest["helper_sha256"]) == set(HELPER_NAMES) and
            all(type(value) is str and len(value) == 64 and
                all(char in "0123456789abcdef" for char in value)
                for value in manifest["helper_sha256"].values()),
            "runtime_manifest_invalid")
    script_dir = Path(__file__).resolve().parent
    for name in HELPER_NAMES:
        require(digest(script_dir / name) == manifest["helper_sha256"][name],
                "helper_hash_mismatch")
    return manifest


def load_helpers(runtime_manifest: Path):
    """Hash every local transitive helper before any helper import executes."""
    read_runtime_manifest(runtime_manifest)
    validator = importlib.import_module("validate_reading_usefulness_fixture")
    bundle = importlib.import_module("preflight_reading_usefulness_bundle")
    previous = importlib.import_module("audit_reading_usefulness")
    script_dir = Path(__file__).resolve().parent
    for name, module in (("validate_reading_usefulness_fixture.py", validator),
                         ("preflight_reading_usefulness_bundle.py", bundle),
                         ("audit_reading_usefulness.py", previous)):
        require(Path(module.__file__).resolve() == (script_dir / name).resolve(),
                "helper_module_path")
    require(tuple(previous.FEATURE_NAMES) == CARD_FEATURE_NAMES and
            previous.MAX_PAIR_TOKENS == MAX_PAIR_TOKENS and
            previous.MAX_STARTUP_SECONDS == MAX_STARTUP_SECONDS and
            previous.MAX_TOTAL_SECONDS == MAX_TOTAL_SECONDS and
            previous.MAX_POOL_SECONDS == MAX_POOL_SECONDS and
            previous.MAX_ADDED_RAM_BYTES == MAX_ADDED_RAM_BYTES and
            previous.BATCH_SIZE == BATCH_SIZE, "old_scorer_contract")
    return validator, bundle, previous


def verify_frozen(args: argparse.Namespace) -> dict:
    require(type(args.expected_freeze_sha256) is str and
            len(args.expected_freeze_sha256) == 64, "external_freeze_pin_required")
    validator, bundle, _previous = load_helpers(args.runtime_manifest)
    identity = validator.verify(
        args.corpus, args.fixture, Path(__file__), args.runtime_manifest,
        args.bundle / "manifest.json", args.freeze_receipt,
        args.expected_freeze_sha256)
    bundle_identity = bundle.verify_bundle(args.bundle)
    require(bundle_identity["manifest_sha256"] ==
            validator.MODEL_BUNDLE_MANIFEST_SHA256, "bundle_manifest_pin")
    return {**identity, "bundle_bytes": bundle_identity["bytes"],
            "bundle_manifest_sha256": bundle_identity["manifest_sha256"]}


def _sigmoid(values):
    import numpy as np

    return 1.0 / (1.0 + np.exp(-np.clip(values, -40.0, 40.0)))


def fit_classifier(feature_rows: list[list[float]], labels: list[bool],
                   feature_names: tuple[str, ...], count: int, kind: str) -> dict:
    """Fixed Newton L2 fit, including train-only standardization."""
    import numpy as np

    require(kind in {"null", "card"} and len(feature_rows) == len(labels) == count and
            all(type(label) is bool for label in labels), "training_count")
    matrix = np.asarray(feature_rows, dtype=np.float64)
    require(matrix.shape == (count, len(feature_names)) and np.isfinite(matrix).all(),
            "training_features")
    target = np.asarray(labels, dtype=np.float64)
    require(0 < target.sum() < count, "training_labels")
    mean = matrix.mean(axis=0)
    scale = matrix.std(axis=0)
    scale = np.where(scale > 1e-12, scale, 1.0)
    design = np.column_stack((np.ones(count), (matrix - mean) / scale))
    penalty = np.diag([0.0] + [REGULARIZATION] * len(feature_names))
    weights = np.zeros(design.shape[1], dtype=np.float64)
    weights[0] = math.log(float(target.mean() / (1.0 - target.mean())))
    for _ in range(50):
        probability = _sigmoid(design @ weights)
        gradient = design.T @ (probability - target) + penalty @ weights
        curvature = probability * (1.0 - probability)
        hessian = design.T @ (design * curvature[:, None]) + penalty
        step = np.linalg.solve(hessian, gradient)
        weights -= step
        if float(np.max(np.abs(step))) < 1e-8:
            break
    else:
        raise AuditError("classifier_nonconvergence")
    require(np.isfinite(weights).all(), "classifier_invalid")
    return {"procedure": PROCEDURE, "kind": kind,
            "feature_names": list(feature_names), "regularization": REGULARIZATION,
            "means": mean.tolist(), "scales": scale.tolist(),
            "weights": weights.tolist(), "training_examples": count}


def classifier_scores(model: dict, rows: list[list[float]],
                      feature_names: tuple[str, ...], kind: str) -> list[float]:
    import numpy as np

    require(model.get("procedure") == PROCEDURE and model.get("kind") == kind and
            model.get("feature_names") == list(feature_names) and
            model.get("regularization") == REGULARIZATION, "classifier_identity")
    matrix = np.asarray(rows, dtype=np.float64)
    require(matrix.ndim == 2 and matrix.shape[1] == len(feature_names) and
            np.isfinite(matrix).all(), "scoring_features")
    mean = np.asarray(model["means"], dtype=np.float64)
    scale = np.asarray(model["scales"], dtype=np.float64)
    weights = np.asarray(model["weights"], dtype=np.float64)
    require(mean.shape == scale.shape == (len(feature_names),) and
            weights.shape == (len(feature_names) + 1,) and
            np.isfinite(mean).all() and np.isfinite(scale).all() and
            np.isfinite(weights).all() and (scale > 0).all(), "classifier_invalid")
    design = np.column_stack((np.ones(len(matrix)), (matrix - mean) / scale))
    result = [float(value) for value in _sigmoid(design @ weights)]
    require(all(math.isfinite(value) for value in result), "score_invalid")
    return result


def null_features(logits: list[float], card_features: list[list[float]]) -> list[float]:
    """Only pooled scorer and question/cue features; no fixture metadata."""
    require(len(logits) == len(card_features) == 4 and
            all(len(row) == len(CARD_FEATURE_NAMES) for row in card_features),
            "pool_feature_count")
    bounded = [max(-20.0, min(20.0, float(value))) for value in logits]
    require(all(math.isfinite(value) for value in bounded), "score_invalid")
    ordered = sorted(range(4), key=lambda index: (-bounded[index], index))
    top, second, third = (ordered[index] for index in range(3))
    lexical = [row[3] for row in card_features]
    return [bounded[top], bounded[top] - bounded[second],
            bounded[top] - bounded[third], max(bounded) - min(bounded),
            sum(bounded) / 4.0, max(lexical), lexical[top],
            sum(lexical[index] for index in ordered[:3]) / 3.0,
            max(row[4] for row in card_features),
            max(row[5] for row in card_features),
            sum(row[6] for row in card_features) / 4.0]


def score_only_pools(groups: list[dict], scorer: Callable, previous) -> list[dict]:
    """Build model inputs without copying labels, reviewer data, or strata."""
    question_views = [{
        "question": group["question"],
        "prior_question_context_if_followup": group["prior_question_context_if_followup"],
        "four_exact_candidate_windows": group["four_exact_candidate_windows"],
    } for group in groups]
    pairs = [previous.pair_text(view, index) for view in question_views
             for index in range(4)]
    logits: list[float] = []
    for start in range(0, len(pairs), BATCH_SIZE):
        chunk = pairs[start:start + BATCH_SIZE]
        values = scorer(chunk)
        require(len(values) == len(chunk) and
                all(type(value) in (int, float) and math.isfinite(value)
                    for value in values), "score_invalid")
        logits.extend(float(value) for value in values)
    pools = []
    for number, group in enumerate(groups):
        own_logits = logits[4 * number:4 * number + 4]
        card_features = previous.features(question_views[number], own_logits)
        candidates = []
        for index, logit in enumerate(own_logits):
            candidates.append({
                "index": index,
                "page": group["page_number_and_text_offsets_for_each_window"][index]
                             ["page_number"],
                "source_document_sha256": group["source_document_sha256"],
                "logit": logit,
            })
        pools.append({"null_features": null_features(own_logits, card_features),
                      "card_features": card_features, "candidates": candidates})
    return pools


def qualify_pools(pools: list[dict], null_model: dict, card_model: dict) -> list[dict]:
    null_scores = classifier_scores(null_model, [row["null_features"] for row in pools],
                                    NULL_FEATURE_NAMES, "null")
    card_scores = classifier_scores(card_model,
                                    [features for row in pools for features in
                                     row["card_features"]], CARD_FEATURE_NAMES, "card")
    rows = []
    for number, pool in enumerate(pools):
        rows.append({"null_score": null_scores[number],
                     "candidates": [{**candidate, "card_score": card_scores[4 * number + index]}
                                    for index, candidate in enumerate(pool["candidates"])]})
    return rows


def _ordered(candidates: list[dict], key: str) -> list[dict]:
    require(len(candidates) == 4 and all(type(row.get(key)) in (int, float) and
                                         math.isfinite(row[key]) for row in candidates),
            "score_invalid")
    return sorted(candidates, key=lambda row: (-row[key],
                                               row["source_document_sha256"],
                                               row["page"], row["index"]))


def select(row: dict, null_threshold: float, card_threshold: float) -> tuple[str, list[dict]]:
    """Select from score-only rows; unknown scorer failures never become no-match."""
    require(all(type(value) in (int, float) and math.isfinite(value)
                for value in (row.get("null_score"), null_threshold, card_threshold)),
            "threshold_or_score_invalid")
    # Validate the complete scored pool even when the null head says no match.
    # A malformed or unavailable card head is an unavailable audit, never a
    # confident no-match observation.
    ordered = _ordered(row["candidates"], "card_score")
    if row["null_score"] < null_threshold:
        return "no_match", []
    selected = []
    seen_pages: set[tuple[str, int]] = set()
    for candidate in ordered:
        identity = (candidate["source_document_sha256"], candidate["page"])
        if candidate["card_score"] >= card_threshold and identity not in seen_pages:
            selected.append(candidate)
            seen_pages.add(identity)
        if len(selected) == 3:
            break
    return ("qualified" if selected else "null_positive_card_none"), selected


def _confusion(predicted: bool, actual: bool, counts: Counter) -> None:
    if predicted:
        counts["tp" if actual else "fp"] += 1
    else:
        counts["fn" if actual else "tn"] += 1


def summarize(groups: list[dict], rows: list[dict], null_threshold: float,
              card_threshold: float) -> dict:
    require(len(groups) == len(rows), "graded_row_count")
    metrics = Counter()
    forms: dict[str, Counter] = defaultdict(Counter)
    strata: dict[int, Counter] = defaultdict(Counter)
    states = Counter()
    null_confusion = Counter()
    card_confusion = Counter()
    effective_card_confusion = Counter()
    for group, row in zip(groups, rows, strict=True):
        labels = [page and cue for page, cue in zip(
            group["original_page_usefulness_per_window"],
            group["exact_cue_usefulness_per_window"], strict=True)]
        pages = group["original_page_usefulness_per_window"]
        cues = group["exact_cue_usefulness_per_window"]
        available = sum(labels)
        require(0 <= available <= 3, "label_count")
        state, selected = select(row, null_threshold, card_threshold)
        states[state] += 1
        null_predicted = row["null_score"] >= null_threshold
        _confusion(null_predicted, available > 0, null_confusion)
        selected_indices = {candidate["index"] for candidate in selected}
        for candidate in row["candidates"]:
            index = candidate["index"]
            require(type(index) is int and 0 <= index < 4, "candidate_index")
            _confusion(candidate["card_score"] >= card_threshold,
                       labels[index], card_confusion)
            _confusion(index in selected_indices, labels[index],
                       effective_card_confusion)
        raw_top_three = _ordered(row["candidates"], "logit")[:3]
        metrics["groups"] += 1
        metrics["available_useful_cards"] += available
        metrics["pool_original_page_useful"] += sum(pages)
        metrics["pool_exact_cue_useful"] += sum(cues)
        metrics["pool_raw_logit_useful_at_three"] += sum(
            labels[candidate["index"]] for candidate in raw_top_three)
        metrics["pool_raw_logit_positive_hit_at_three"] += available > 0 and any(
            labels[candidate["index"]] for candidate in raw_top_three)
        metrics["displayed_cards"] += len(selected)
        metrics["displayed_useful_cards"] += sum(labels[c["index"]] for c in selected)
        metrics["displayed_original_page_useful"] += sum(pages[c["index"]] for c in selected)
        metrics["displayed_exact_cue_useful"] += sum(cues[c["index"]] for c in selected)
        metrics["displayed_page_useful_cue_weak"] += sum(
            pages[c["index"]] and not cues[c["index"]] for c in selected)
        if available:
            metrics["positive_groups"] += 1
            metrics["positive_hit_at_three"] += any(labels[c["index"]] for c in selected)
            metrics["useful_first"] += bool(selected and labels[selected[0]["index"]])
            metrics["positive_no_match_errors"] += state == "no_match"
            metrics["positive_no_qualified_card_errors"] += state == "null_positive_card_none"
            forms[group["question_form"]]["positive_groups"] += 1
            forms[group["question_form"]]["positive_hit_at_three"] += any(
                labels[c["index"]] for c in selected)
            strata[available]["groups"] += 1
            strata[available]["exact_count"] += len(selected) == available
        else:
            metrics["no_useful_groups"] += 1
            metrics["no_useful_displayed"] += bool(selected)
        metrics["first_card_errors"] += bool(selected and not labels[selected[0]["index"]])
        metrics["first_page_wrong"] += bool(selected and not pages[selected[0]["index"]])
        metrics["first_page_right_cue_weak"] += bool(selected and
                                                      pages[selected[0]["index"]] and
                                                      not cues[selected[0]["index"]])
    displayed = metrics["displayed_cards"]
    return {**dict(metrics),
            "displayed_precision": metrics["displayed_useful_cards"] / displayed
                                   if displayed else 0.0,
            "form": {form: dict(forms[form]) for form in ("direct", "paraphrase", "follow-up")},
            "count_strata": {str(count): dict(strata[count]) for count in (1, 2, 3)},
            "outcome_states": dict(states),
            "null_confusion": {key: null_confusion[key] for key in ("tp", "tn", "fp", "fn")},
            "card_confusion": {key: card_confusion[key] for key in ("tp", "tn", "fp", "fn")},
            "effective_card_confusion": {key: effective_card_confusion[key]
                                         for key in ("tp", "tn", "fp", "fn")}}


def threshold_grid(values: list[float]) -> list[float]:
    require(values and all(type(value) in (int, float) and math.isfinite(value)
                           for value in values), "calibration_scores")
    ordered = sorted(set(values))
    return ([math.nextafter(ordered[0], -math.inf)] +
            [(lower + upper) / 2.0 for lower, upper in zip(ordered, ordered[1:])]
            + [math.nextafter(ordered[-1], math.inf)])


def calibration_passed(metrics: dict) -> bool:
    return (metrics.get("groups") == 48 and metrics.get("positive_groups") == 36 and
            metrics.get("no_useful_groups") == 12 and
            metrics.get("no_useful_displayed", 0) == 0 and
            metrics.get("displayed_cards", 0) > 0 and
            metrics.get("displayed_useful_cards", 0) * 10 >=
                metrics["displayed_cards"] * 9 and
            metrics.get("positive_hit_at_three", 0) >= 30)


def choose_thresholds(groups: list[dict], rows: list[dict]) -> tuple[float, float, dict, int]:
    """Frozen midpoint grid; maximize useful cards, hits, then precision.

    Ties choose fewer displayed cards, then higher null and card thresholds.
    Threshold comparison is inclusive (>=) in both decisions. No labels tune
    model weights or feature selection; labels only choose this one pair.
    """
    require(len(groups) == len(rows) == 48, "calibration_count")
    null_grid = threshold_grid([row["null_score"] for row in rows])
    card_grid = threshold_grid([candidate["card_score"] for row in rows
                                for candidate in row["candidates"]])
    best: tuple[tuple[int, int, int, float, float], float, float, dict] | None = None
    attempts = 0
    for null_threshold in null_grid:
        for card_threshold in card_grid:
            attempts += 1
            metrics = summarize(groups, rows, null_threshold, card_threshold)
            if not calibration_passed(metrics):
                continue
            rank = (metrics["displayed_useful_cards"], metrics["positive_hit_at_three"],
                    -metrics["displayed_cards"], null_threshold, card_threshold)
            if best is None or rank > best[0]:
                best = (rank, null_threshold, card_threshold, metrics)
    require(best is not None, "calibration_gate_rejected")
    return best[1], best[2], best[3], attempts


def heldout_passed(metrics: dict) -> bool:
    """The exact previous public heldout quality gate, including every stratum."""
    return (metrics.get("groups") == 48 and metrics.get("positive_groups") == 36
            and metrics.get("no_useful_groups") == 12
            and metrics.get("positive_hit_at_three", 0) >= 33
            and all(metrics.get("form", {}).get(form, {}).get("positive_groups") == 12 and
                    metrics["form"][form].get("positive_hit_at_three", 0) >= 10
                    for form in ("direct", "paraphrase", "follow-up"))
            and metrics.get("useful_first", 0) >= 31
            and metrics.get("displayed_cards", 0) > 0
            and metrics.get("displayed_useful_cards", 0) * 10 >=
                metrics["displayed_cards"] * 9
            and metrics.get("available_useful_cards") == 72
            and metrics.get("displayed_useful_cards", 0) >= 60
            and all(metrics.get("count_strata", {}).get(str(count), {}).get("groups") == 12 and
                    metrics["count_strata"][str(count)].get("exact_count", 0) >= 10
                    for count in (1, 2, 3))
            and metrics.get("no_useful_displayed", 0) == 0)


def require_bounded_container() -> None:
    interfaces = Path("/sys/class/net")
    require(os.name == "posix" and interfaces.is_dir() and
            {entry.name for entry in interfaces.iterdir()} <= {"lo"},
            "network_isolation_required")
    try:
        quota, period = Path("/sys/fs/cgroup/cpu.max").read_text(
            encoding="ascii").split()
        memory = Path("/sys/fs/cgroup/memory.max").read_text(
            encoding="ascii").strip()
        q, p, m = int(quota), int(period), int(memory)
    except (OSError, ValueError):
        raise AuditError("container_resource_limits_required") from None
    require(0 < q <= 4 * p and 0 < m <= MAX_ADDED_RAM_BYTES,
            "container_resource_limits_required")


def require_approved_ledger() -> None:
    root = APPROVED_LEDGER_ROOT
    require(root.parent == Path("/tmp") and root.is_dir() and
            not root.is_symlink() and os.path.ismount(root),
            "persistent_audit_ledger_required")


def attempt_marker_path() -> Path:
    return APPROVED_LEDGER_ROOT / "approved-audit-attempt.json"


def child_claim_path() -> Path:
    return APPROVED_LEDGER_ROOT / "approved-audit-child-claimed.json"


def check_attempt_marker(args: argparse.Namespace) -> None:
    marker = read_json_bounded(attempt_marker_path(), 4096)
    require(marker == {"procedure": PROCEDURE,
                       "freeze_sha256": args.expected_freeze_sha256,
                       "harness_sha256": digest(Path(__file__)),
                       "one_shot_attempt": True}, "audit_attempt_marker")


def _emit(value: dict) -> None:
    print(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False),
          flush=True)


def run_child(args: argparse.Namespace) -> None:
    start = perf_counter()
    require_bounded_container()
    require_approved_ledger()
    identity = verify_frozen(args)
    check_attempt_marker(args)
    require(args.output.is_dir() and not args.output.is_symlink(), "output_directory")
    # A crash or partial run consumes the child claim. It is never replayed.
    write_exclusive(child_claim_path(), {"procedure": PROCEDURE,
                                        "freeze_sha256": args.expected_freeze_sha256,
                                        "harness_sha256": digest(Path(__file__)),
                                        "child_claimed_once": True})
    validator, _bundle, previous = load_helpers(args.runtime_manifest)
    fixture, _raw = validator.read_json(args.fixture, validator.MAX_FIXTURE_BYTES)
    groups = fixture["groups"]
    train_groups = [group for group in groups if group["split"] == "train"]
    calibration_groups = [group for group in groups if group["split"] == "calibration"]
    require(len(train_groups) == 96 and len(calibration_groups) == 48 and
            len(groups) == 192, "split_counts")
    baseline_rss = previous.peak_rss()
    _emit({"event": "preflight_ready", "freeze_sha256": identity["freeze_sha256"]})
    scorer, resources, startup = previous._model_scorer(args.bundle, start, baseline_rss)
    _emit({"event": "startup_ready", "startup_ms": round(startup * 1000, 3)})

    train_pools = score_only_pools(train_groups, scorer, previous)
    null_labels = [any(page and cue for page, cue in zip(
        group["original_page_usefulness_per_window"],
        group["exact_cue_usefulness_per_window"], strict=True)) for group in train_groups]
    card_labels = [page and cue for group in train_groups for page, cue in zip(
        group["original_page_usefulness_per_window"],
        group["exact_cue_usefulness_per_window"], strict=True)]
    null_model = fit_classifier([pool["null_features"] for pool in train_pools],
                                null_labels, NULL_FEATURE_NAMES, 96, "null")
    card_model = fit_classifier([features for pool in train_pools for features in
                                 pool["card_features"]], card_labels,
                                CARD_FEATURE_NAMES, 384, "card")
    calibration_pools = score_only_pools(calibration_groups, scorer, previous)
    calibration_rows = qualify_pools(calibration_pools, null_model, card_model)
    # The old scorer accounts for tokenizer preprocessing, every full 30-pair
    # batch, peak added RAM and elapsed time. A resource miss stops here.
    calibration_resource = resources()
    if not calibration_resource["resource_passed"]:
        result = {"status": "resource_rejected_no_heldout", "candidate_passed": False,
                  "heldout_scored": False, "release_gate_passed": False,
                  "provider_requests": 0, "database_writes": 0,
                  "resources": calibration_resource,
                  "freeze_sha256": identity["freeze_sha256"]}
        write_exclusive(args.output / "audit-result.json", result)
        _emit({"event": "result", "result": result})
        return
    try:
        null_threshold, card_threshold, calibration_metrics, search_count = \
            choose_thresholds(calibration_groups, calibration_rows)
    except AuditError as exc:
        if str(exc) != "calibration_gate_rejected":
            raise
        result = {"status": "calibration_rejected_no_heldout", "candidate_passed": False,
                  "heldout_scored": False, "release_gate_passed": False,
                  "provider_requests": 0, "database_writes": 0,
                  "calibration": {"status": "no_qualifying_threshold_pair",
                                  "groups": 48,
                                  "raw_pool": {"available_useful_cards": sum(
                                      page and cue for group in calibration_groups
                                      for page, cue in zip(
                                          group["original_page_usefulness_per_window"],
                                          group["exact_cue_usefulness_per_window"], strict=True)),
                                               "raw_logit_positive_hit_at_three": sum(
                                      any(group["original_page_usefulness_per_window"][c["index"]]
                                          and group["exact_cue_usefulness_per_window"][c["index"]]
                                          for c in _ordered(row["candidates"], "logit")[:3])
                                      for group, row in zip(calibration_groups,
                                                            calibration_rows, strict=True))}},
                  "resources": calibration_resource,
                  "freeze_sha256": identity["freeze_sha256"]}
        write_exclusive(args.output / "audit-result.json", result)
        _emit({"event": "result", "result": result})
        return
    rule = {"procedure": PROCEDURE, "null_model": null_model, "card_model": card_model,
            "null_threshold": null_threshold, "card_threshold": card_threshold,
            "calibration": calibration_metrics, "calibration_grid_pairs": search_count,
            "fixture_sha256": digest(args.fixture),
            "freeze_sha256": identity["freeze_sha256"], "heldout_scored": False}
    rule_hash = write_exclusive(args.output / "calibration-rule.json", rule)
    _emit({"event": "calibration_frozen", "rule_sha256": rule_hash})

    # This is the first split-specific heldout access after the rule receipt.
    heldout_groups = [group for group in groups if group["split"] == "heldout"]
    require(len(heldout_groups) == 48, "heldout_count")
    heldout_pools = score_only_pools(heldout_groups, scorer, previous)
    heldout_rows = qualify_pools(heldout_pools, null_model, card_model)
    require(digest(args.output / "calibration-rule.json") == rule_hash and
            digest(args.fixture) == rule["fixture_sha256"], "measurement_drift")
    heldout_metrics = summarize(heldout_groups, heldout_rows, null_threshold, card_threshold)
    resource = resources()
    quality_passed = heldout_passed(heldout_metrics)
    passed = quality_passed and resource["resource_passed"]
    status = ("public_passed" if passed else "public_resource_rejected" if
              not resource["resource_passed"] else "public_quality_rejected")
    result = {"status": status, "candidate_passed": passed,
              "release_gate_passed": False, "heldout_scored": True,
              "provider_requests": 0, "database_writes": 0,
              "calibration": calibration_metrics, "heldout": heldout_metrics,
              "resources": resource, "rule_sha256": rule_hash,
              "freeze_sha256": identity["freeze_sha256"]}
    write_exclusive(args.output / "audit-result.json", result)
    _emit({"event": "result", "result": result})


def supervise(args: argparse.Namespace) -> dict:
    require_bounded_container()
    require_approved_ledger()
    require(perf_counter() - args.audit_start < MAX_TOTAL_SECONDS, "total_timeout")
    marker = attempt_marker_path()
    require(not marker.exists() and not marker.is_symlink(), "audit_attempt_consumed")
    require(not args.output.exists(), "output_exists")
    write_exclusive(marker, {"procedure": PROCEDURE,
                             "freeze_sha256": args.expected_freeze_sha256,
                             "harness_sha256": args.harness_sha256,
                             "one_shot_attempt": True})
    args.output.mkdir(mode=0o700)
    command = [sys.executable, str(Path(__file__)), "--child", "--execute-approved",
               "--corpus", str(args.corpus), "--fixture", str(args.fixture),
               "--bundle", str(args.bundle), "--runtime-manifest", str(args.runtime_manifest),
               "--freeze-receipt", str(args.freeze_receipt),
               "--expected-freeze-sha256", args.expected_freeze_sha256,
               "--output", str(args.output)]
    child_env = {key: os.environ[key] for key in
                 ("PATH", "LD_LIBRARY_PATH", "SystemRoot", "TMPDIR", "LANG", "LC_ALL")
                 if key in os.environ}
    child_env.update(OMP_NUM_THREADS="4", TOKENIZERS_PARALLELISM="false",
                     HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    process = subprocess.Popen(command, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, text=True, env=child_env)
    mailbox: queue.Queue[str | None] = queue.Queue()

    def reader() -> None:
        assert process.stdout is not None
        for line in iter(lambda: process.stdout.readline(MAX_OUTPUT_LINE + 1), ""):
            mailbox.put(line)
        mailbox.put(None)

    threading.Thread(target=reader, daemon=True).start()
    preflight_at: float | None = None
    startup_ready = False
    heldout_may_have_opened = False
    frozen_rule_hash: str | None = None
    result = {"status": "child_unavailable", "candidate_passed": False,
              "release_gate_passed": False, "heldout_scored": False,
              "provider_requests": 0, "database_writes": 0}
    got_result = False
    try:
        while True:
            elapsed = perf_counter() - args.audit_start
            remaining = MAX_TOTAL_SECONDS - elapsed
            if preflight_at is not None and not startup_ready:
                remaining = min(remaining, MAX_STARTUP_SECONDS - (perf_counter() - preflight_at))
            if remaining <= 0:
                result["status"] = "total_timeout" if startup_ready else "startup_timeout"
                break
            try:
                line = mailbox.get(timeout=remaining)
            except queue.Empty:
                result["status"] = "total_timeout" if startup_ready else "startup_timeout"
                break
            if line is None:
                break
            if len(line) > MAX_OUTPUT_LINE:
                result["status"] = "protocol_invalid"
                break
            try:
                message = json.loads(line)
            except (TypeError, ValueError):
                result["status"] = "protocol_invalid"
                break
            if type(message) is not dict:
                result["status"] = "protocol_invalid"
                break
            event = message.get("event")
            if event == "preflight_ready" and preflight_at is None:
                preflight_at = perf_counter()
            elif event == "startup_ready" and preflight_at is not None and not startup_ready:
                startup_ready = True
            elif event == "calibration_frozen" and startup_ready and not heldout_may_have_opened:
                heldout_may_have_opened = True
                claimed_hash = message.get("rule_sha256")
                try:
                    rule_hash_valid = (type(claimed_hash) is str and
                                       len(claimed_hash) == 64 and
                                       all(char in "0123456789abcdef" for char in claimed_hash) and
                                       digest(args.output / "calibration-rule.json") == claimed_hash)
                except (OSError, ValueError):
                    rule_hash_valid = False
                if not rule_hash_valid:
                    result["status"] = "protocol_invalid"
                    break
                frozen_rule_hash = claimed_hash
                continue
            elif event == "result" and startup_ready and type(message.get("result")) is dict:
                candidate = message["result"]
                before_rule = {"calibration_rejected_no_heldout",
                               "resource_rejected_no_heldout"}
                after_rule = {"public_passed", "public_quality_rejected",
                              "public_resource_rejected"}
                status = candidate.get("status")
                valid_stage = (
                    (status in before_rule and not heldout_may_have_opened and
                     candidate.get("heldout_scored") is False and
                     candidate.get("candidate_passed") is False and
                     "rule_sha256" not in candidate) or
                    (status in after_rule and heldout_may_have_opened and
                     candidate.get("heldout_scored") is True and
                     candidate.get("rule_sha256") == frozen_rule_hash and
                     candidate.get("candidate_passed") is (status == "public_passed")))
                valid_stage = (valid_stage and
                               candidate.get("release_gate_passed") is False and
                               candidate.get("provider_requests") == 0 and
                               candidate.get("database_writes") == 0)
                if not valid_stage:
                    result["status"] = "protocol_invalid"
                    break
                result = candidate
                got_result = True
                break
            elif event == "failed":
                result["status"] = message.get("reason", "child_unavailable")
                break
            else:
                result["status"] = "protocol_invalid"
                break
    finally:
        if process.poll() is None:
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
    # A rule receipt can precede the event by a few instructions. If the
    # protocol ends there, the safe report is still unknown-after-calibration.
    if (args.output / "calibration-rule.json").exists():
        heldout_may_have_opened = True
    if heldout_may_have_opened and result["status"] not in (
            "public_passed", "public_quality_rejected", "public_resource_rejected"):
        result["heldout_scored"] = "unknown_after_calibration"
    if frozen_rule_hash is not None:
        try:
            rule_unchanged = digest(args.output / "calibration-rule.json") == frozen_rule_hash
        except (OSError, ValueError):
            rule_unchanged = False
        if not rule_unchanged:
            result["status"] = "measurement_drift"
            result["candidate_passed"] = False
            result["heldout_scored"] = "unknown_after_calibration"
    if got_result and process.returncode != 0:
        result["status"] = "result_mismatch"
        result["candidate_passed"] = False
    result_path = args.output / "audit-result.json"
    if result_path.is_file():
        try:
            saved = read_json_bounded(result_path, 300_000)
            if saved != result:
                result["status"] = "result_mismatch"
                result["candidate_passed"] = False
        except (OSError, ValueError):
            result["status"] = "result_mismatch"
            result["candidate_passed"] = False
    try:
        frozen_unchanged = verify_frozen(args)["freeze_sha256"] == args.expected_freeze_sha256
    except (OSError, ValueError, ImportError):
        frozen_unchanged = False
    if (digest(Path(__file__)) != args.harness_sha256 or
            digest(args.fixture) != args.fixture_sha256 or
            digest(args.runtime_manifest) != args.runtime_sha256 or
            not frozen_unchanged):
        result["status"] = "measurement_drift"
        result["candidate_passed"] = False
    if result.get("candidate_passed"):
        heldout = result.get("heldout")
        resource = result.get("resources")
        if (not isinstance(heldout, dict) or not isinstance(resource, dict) or
                not heldout_passed(heldout) or not resource.get("resource_passed") or
                result.get("status") != "public_passed" or process.returncode != 0):
            result["status"] = "result_mismatch"
            result["candidate_passed"] = False
    if result_path.is_file():
        write_exclusive(args.output / "supervisor-result.json", result)
    else:
        write_exclusive(result_path, result)
    return result


def main(argv: list[str] | None = None) -> int:
    audit_start = perf_counter()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--runtime-manifest", type=Path, required=True)
    parser.add_argument("--freeze-receipt", type=Path, required=True)
    parser.add_argument("--expected-freeze-sha256", required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--execute-approved", action="store_true")
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    args.audit_start = audit_start
    try:
        require(not args.execute_approved or args.output is not None, "output_required")
        require(not args.child or args.execute_approved, "child_execution_flag_required")
        if args.child:
            run_child(args)
            return 0
        identity = verify_frozen(args)
        if not args.execute_approved:
            _emit({"status": "frozen_preflight_no_scoring", **identity,
                   "model_inferences": 0, "provider_requests": 0,
                   "database_writes": 0, "candidate_passed": False,
                   "release_gate_passed": False})
            return 0
        args.harness_sha256 = digest(Path(__file__))
        args.fixture_sha256 = digest(args.fixture)
        args.runtime_sha256 = digest(args.runtime_manifest)
        result = supervise(args)
        _emit(result)
        return 0 if result["status"] in ("public_passed", "public_quality_rejected",
                                          "public_resource_rejected",
                                          "resource_rejected_no_heldout",
                                          "calibration_rejected_no_heldout") else 1
    except (AuditError, OSError, ValueError, ImportError) as exc:
        reason = str(exc) if isinstance(exc, AuditError) else type(exc).__name__
        if args.child:
            _emit({"event": "failed", "reason": reason})
        else:
            _emit({"status": "audit_unavailable" if args.execute_approved else
                   "audit_rejected_no_scoring", "reason": reason,
                   "provider_requests": 0, "database_writes": 0,
                   "candidate_passed": False, "release_gate_passed": False})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
