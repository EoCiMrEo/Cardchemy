"""One-shot, public, offline reading-usefulness audit; never an Ask runtime path.

The default command only verifies a reviewed 192-group fixture and externally
recorded freeze receipt. Inference additionally requires --execute-approved and
belongs in a credential-free, networkless, disposable 4-CPU/2-GiB container.
This file contains no network, provider, database, or application imports.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
from time import perf_counter
from typing import Callable

import preflight_reading_usefulness_bundle as bundle_admission
import validate_reading_usefulness_fixture as fixture_admission


PROCEDURE = "mixedbread_public_reading_usefulness_logistic_v1"
APPROVED_LEDGER_ROOT = Path("/tmp/cardchemy-reading-usefulness-mixedbread-v1-ledger")
FEATURE_NAMES = (
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
STOPWORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "does",
    "for", "from", "how", "in", "is", "it", "of", "on", "or", "the", "to",
    "what", "when", "where", "which", "who", "why", "with",
})
CONDITIONS = frozenset({
    "after", "above", "before", "below", "during", "except", "if",
    "inside", "outside", "under", "unless", "until", "when", "where",
    "while", "without", "greater", "less", "only",
})
NEGATIONS = frozenset({"no", "not", "never", "neither", "without", "cannot"})
TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)


class AuditError(ValueError):
    """A deliberately content-free, allowlisted audit failure."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise AuditError(code)


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def canonical_bytes(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True, allow_nan=False) + "\n").encode("utf-8")


def write_exclusive(path: Path, value: dict) -> str:
    raw = canonical_bytes(value)
    with path.open("xb") as stream:
        stream.write(raw)
    return hashlib.sha256(raw).hexdigest()


def _words(value: str) -> set[str]:
    return set(TOKEN_RE.findall(value.casefold())) - STOPWORDS


def pair_text(group: dict, index: int) -> tuple[str, str]:
    question = group["question"]
    previous = group["prior_question_context_if_followup"]
    if previous is not None:
        question = "Previous question: " + previous + "\nCurrent question: " + question
    return question, group["four_exact_candidate_windows"][index]


def features(group: dict, logits: list[float]) -> list[list[float]]:
    require(len(logits) == 4 and all(type(x) in (int, float) and math.isfinite(x)
                                     for x in logits), "score_invalid")
    bounded = [max(-20.0, min(20.0, float(x))) for x in logits]
    ordered = sorted(bounded, reverse=True)
    question = _words(pair_text(group, 0)[0])
    question_conditions = set(TOKEN_RE.findall(pair_text(group, 0)[0].casefold())) & CONDITIONS
    rows: list[list[float]] = []
    for index, logit in enumerate(bounded):
        cue = group["four_exact_candidate_windows"][index]
        cue_words = _words(cue)
        first_line = cue.splitlines()[0].split(":", 1)[0][:100]
        title_words = _words(first_line)
        overlap = len(question & cue_words)
        lexical_f1 = (2 * overlap / (len(question) + len(cue_words))
                      if question or cue_words else 0.0)
        title_overlap = (len(question & title_words) / len(question)
                         if question else 0.0)
        cue_conditions = set(TOKEN_RE.findall(cue.casefold())) & CONDITIONS
        condition_coverage = (len(question_conditions & cue_conditions) /
                              len(question_conditions) if question_conditions else 0.0)
        rows.append([
            logit, logit - ordered[0], ordered[0] - ordered[1], lexical_f1,
            title_overlap, condition_coverage,
            float(bool(question & NEGATIONS) == bool(cue_words & NEGATIONS)),
            min(len(cue), 480) / 480.0,
        ])
    return rows


def _sigmoid(values):
    import numpy as np

    return 1.0 / (1.0 + np.exp(-np.clip(values, -40.0, 40.0)))


def fit_classifier(feature_rows: list[list[float]], labels: list[bool]) -> dict:
    """Fixed L2 logistic fit; standardization and coefficients use train only."""
    import numpy as np

    require(len(feature_rows) == 384 and len(labels) == 384 and
            all(type(label) is bool for label in labels), "training_count")
    matrix = np.asarray(feature_rows, dtype=np.float64)
    require(matrix.shape == (384, len(FEATURE_NAMES)) and np.isfinite(matrix).all(),
            "training_features")
    target = np.asarray(labels, dtype=np.float64)
    require(0 < target.sum() < len(target), "training_labels")
    mean = matrix.mean(axis=0)
    scale = matrix.std(axis=0)
    scale = np.where(scale > 1e-12, scale, 1.0)
    design = np.column_stack((np.ones(len(matrix)), (matrix - mean) / scale))
    penalty = np.diag([0.0] + [REGULARIZATION] * len(FEATURE_NAMES))
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
    return {"procedure": PROCEDURE, "feature_names": list(FEATURE_NAMES),
            "regularization": REGULARIZATION, "means": mean.tolist(),
            "scales": scale.tolist(), "weights": weights.tolist(),
            "training_examples": 384}


def classifier_scores(model: dict, feature_rows: list[list[float]]) -> list[float]:
    import numpy as np

    require(model.get("feature_names") == list(FEATURE_NAMES) and
            model.get("regularization") == REGULARIZATION, "classifier_identity")
    matrix = np.asarray(feature_rows, dtype=np.float64)
    require(matrix.ndim == 2 and matrix.shape[1] == len(FEATURE_NAMES) and
            np.isfinite(matrix).all(), "scoring_features")
    mean = np.asarray(model["means"], dtype=np.float64)
    scale = np.asarray(model["scales"], dtype=np.float64)
    weights = np.asarray(model["weights"], dtype=np.float64)
    require(mean.shape == scale.shape == (len(FEATURE_NAMES),) and
            weights.shape == (len(FEATURE_NAMES) + 1,) and
            np.isfinite(mean).all() and np.isfinite(scale).all() and
            np.isfinite(weights).all() and (scale > 0).all(), "classifier_invalid")
    design = np.column_stack((np.ones(len(matrix)), (matrix - mean) / scale))
    return [float(value) for value in _sigmoid(design @ weights)]


def _candidate(group: dict, index: int, score: float, logit: float) -> dict:
    offset = group["page_number_and_text_offsets_for_each_window"][index]
    page = group["original_page_usefulness_per_window"][index]
    cue = group["exact_cue_usefulness_per_window"][index]
    return {"index": index, "page": offset["page_number"],
            "source_document_sha256": group["source_document_sha256"],
            "page_useful": page, "cue_useful": cue, "useful": page and cue,
            "score": score, "logit": logit}


def scored_rows(groups: list[dict], model: dict,
                scorer: Callable[[list[tuple[str, str]]], list[float]]) -> list[dict]:
    """Score only the supplied split in bounded batches; no hidden fill."""
    pairs = [pair_text(group, index) for group in groups for index in range(4)]
    logits: list[float] = []
    for start in range(0, len(pairs), BATCH_SIZE):
        chunk = pairs[start:start + BATCH_SIZE]
        values = scorer(chunk)
        require(len(values) == len(chunk) and
                all(type(value) in (int, float) and math.isfinite(value)
                    for value in values), "score_invalid")
        logits.extend(float(value) for value in values)
    rows = []
    for number, group in enumerate(groups):
        own_logits = logits[4 * number:4 * number + 4]
        own_features = features(group, own_logits)
        scores = classifier_scores(model, own_features)
        rows.append({"id": group["id"], "form": group["question_form"],
                     "relation": group["relation_family"],
                     "candidates": [_candidate(group, index, scores[index], own_logits[index])
                                    for index in range(4)]})
    return rows


def _ordered(candidates: list[dict], key: str = "score") -> list[dict]:
    require(len(candidates) == 4 and all(type(row[key]) in (int, float) and
                                         math.isfinite(row[key]) for row in candidates),
            "score_invalid")
    return sorted(candidates, key=lambda row: (-row[key],
                                                 row["source_document_sha256"],
                                                 row["page"], row["index"]))


def displayed(candidates: list[dict], threshold: float) -> list[dict]:
    require(type(threshold) in (int, float) and math.isfinite(threshold),
            "threshold_invalid")
    result = []
    pages: set[tuple[str, int]] = set()
    for candidate in _ordered(candidates):
        identity = (candidate["source_document_sha256"], candidate["page"])
        if candidate["score"] >= threshold and identity not in pages:
            result.append(candidate)
            pages.add(identity)
        if len(result) == 3:
            break
    return result


def summarize(rows: list[dict], threshold: float, *, include_grades: bool) -> dict:
    metrics = Counter()
    forms: dict[str, Counter] = defaultdict(Counter)
    strata: dict[int, Counter] = defaultdict(Counter)
    grades = []
    false_primary = []
    for row in rows:
        candidates = row["candidates"]
        available = sum(candidate["useful"] for candidate in candidates)
        require(0 <= available <= 3, "label_count")
        selected = displayed(candidates, threshold)
        raw_top_three = _ordered(candidates, "logit")[:3]
        metrics["groups"] += 1
        metrics["available_useful_cards"] += available
        metrics["pool_original_page_useful"] += sum(c["page_useful"] for c in candidates)
        metrics["pool_exact_cue_useful"] += sum(c["cue_useful"] for c in candidates)
        metrics["pool_raw_logit_useful_at_three"] += sum(c["useful"] for c in raw_top_three)
        metrics["pool_raw_logit_positive_hit_at_three"] += available > 0 and any(
            c["useful"] for c in raw_top_three)
        metrics["displayed_cards"] += len(selected)
        metrics["displayed_useful_cards"] += sum(c["useful"] for c in selected)
        metrics["displayed_original_page_useful"] += sum(c["page_useful"] for c in selected)
        metrics["displayed_exact_cue_useful"] += sum(c["cue_useful"] for c in selected)
        metrics["displayed_page_useful_cue_weak"] += sum(
            c["page_useful"] and not c["cue_useful"] for c in selected)
        if available:
            metrics["positive_groups"] += 1
            metrics["positive_hit_at_three"] += any(c["useful"] for c in selected)
            metrics["useful_first"] += bool(selected and selected[0]["useful"])
            forms[row["form"]]["positive_groups"] += 1
            forms[row["form"]]["positive_hit_at_three"] += any(
                c["useful"] for c in selected)
            strata[available]["groups"] += 1
            strata[available]["exact_count"] += len(selected) == available
        else:
            metrics["no_useful_groups"] += 1
            metrics["no_useful_displayed"] += bool(selected)
        if selected and not selected[0]["useful"]:
            first = selected[0]
            mechanism = ("original_page_not_useful" if not first["page_useful"]
                         else "exact_cue_not_useful")
            false_primary.append({"group_id": row["id"], "candidate_index": first["index"],
                                  "relation": row["relation"], "form": row["form"],
                                  "mechanism": mechanism})
        if include_grades:
            for rank, candidate in enumerate(selected, 1):
                grades.append({"group_id": row["id"], "rank": rank,
                               "candidate_index": candidate["index"],
                               "original_page_number": candidate["page"],
                               "original_page_useful": candidate["page_useful"],
                               "exact_cue_useful": candidate["cue_useful"],
                               "displayed_card_useful": candidate["useful"]})
    precision = (metrics["displayed_useful_cards"] / metrics["displayed_cards"]
                 if metrics["displayed_cards"] else 0.0)
    return {**dict(metrics), "displayed_precision": precision,
            "form": {form: dict(forms[form]) for form in sorted(fixture_admission.FORMS)},
            "count_strata": {str(count): dict(strata[count]) for count in (1, 2, 3)},
            "false_primary": false_primary, "displayed_card_grades": grades}


def choose_threshold(calibration_rows: list[dict]) -> tuple[float, dict]:
    require(len(calibration_rows) == 48, "calibration_count")
    all_scores = sorted({candidate["score"] for row in calibration_rows
                         for candidate in row["candidates"]})
    require(len(all_scores) >= 2, "calibration_scores")
    best: tuple[int, float, dict] | None = None
    for lower, upper in zip(all_scores, all_scores[1:], strict=False):
        threshold = (lower + upper) / 2.0
        metrics = summarize(calibration_rows, threshold, include_grades=False)
        if (metrics["positive_groups"] != 36 or metrics["no_useful_groups"] != 12
                or metrics["no_useful_displayed"] != 0
                or metrics["displayed_cards"] == 0
                or metrics["displayed_useful_cards"] * 10 < metrics["displayed_cards"] * 9
                or metrics["positive_hit_at_three"] < 30):
            continue
        rank = (metrics["displayed_useful_cards"], threshold)
        if best is None or rank > best[:2]:
            best = (rank[0], rank[1], metrics)
    require(best is not None, "calibration_gate_rejected")
    return best[1], best[2]


def heldout_passed(metrics: dict) -> bool:
    return (metrics.get("groups") == 48 and metrics.get("positive_groups") == 36
            and metrics.get("no_useful_groups") == 12
            and metrics.get("positive_hit_at_three", 0) >= 33
            and all(metrics.get("form", {}).get(form, {}).get("positive_groups") == 12 and
                    metrics["form"][form].get("positive_hit_at_three", 0) >= 10
                    for form in fixture_admission.FORMS)
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


def peak_rss() -> int:
    for line in Path("/proc/self/status").read_text(encoding="utf-8").splitlines():
        if line.startswith("VmHWM:"):
            return int(line.split()[1]) * 1024
    raise AuditError("memory_measurement_unavailable")


def require_networkless_linux() -> None:
    """Require the network-none execution shape before importing model code."""
    interfaces = Path("/sys/class/net")
    require(os.name == "posix" and interfaces.is_dir() and
            {entry.name for entry in interfaces.iterdir()} <= {"lo"},
            "network_isolation_required")


def require_bounded_container() -> None:
    """Fail closed unless the approved network, CPU and RAM sandbox is active."""
    require_networkless_linux()
    try:
        cpu_quota, cpu_period = Path("/sys/fs/cgroup/cpu.max").read_text(
            encoding="ascii").split()
        memory_limit = Path("/sys/fs/cgroup/memory.max").read_text(
            encoding="ascii").strip()
        quota = int(cpu_quota)
        period = int(cpu_period)
        memory = int(memory_limit)
    except (OSError, ValueError):
        raise AuditError("container_resource_limits_required") from None
    require(0 < quota <= 4 * period and 0 < memory <= MAX_ADDED_RAM_BYTES,
            "container_resource_limits_required")


def verify_frozen(args: argparse.Namespace) -> dict:
    require(args.expected_freeze_sha256 is not None, "external_freeze_pin_required")
    identity = fixture_admission.verify(
        args.corpus, args.fixture, Path(__file__), args.runtime_manifest,
        args.bundle / "manifest.json", args.freeze_receipt,
        args.expected_freeze_sha256)
    bundle = bundle_admission.verify_bundle(args.bundle)
    require(bundle["manifest_sha256"] == fixture_admission.MODEL_BUNDLE_MANIFEST_SHA256,
            "bundle_manifest_pin")
    return {**identity, "bundle_bytes": bundle["bytes"],
            "bundle_manifest_sha256": bundle["manifest_sha256"]}


def require_approved_ledger() -> None:
    """Keep the one approved attempt on a persistent, fixed bind mount.

    A marker beside a caller-selected freeze receipt could be bypassed by
    copying that receipt to another filename. This ledger belongs to the
    experiment, independent of the fixture, receipt, or output names.
    """
    root = APPROVED_LEDGER_ROOT
    require(root.parent == Path("/tmp") and root.is_dir() and
            not root.is_symlink() and os.path.ismount(root),
            "persistent_audit_ledger_required")


def attempt_marker_path() -> Path:
    return APPROVED_LEDGER_ROOT / "approved-audit-attempt.json"


def child_claim_path() -> Path:
    return APPROVED_LEDGER_ROOT / "approved-audit-child-claimed.json"


def check_attempt_marker(args: argparse.Namespace) -> None:
    marker, _raw = fixture_admission.read_json(attempt_marker_path(),
                                                4096)
    require(marker == {"procedure": PROCEDURE,
                       "freeze_sha256": args.expected_freeze_sha256,
                       "harness_sha256": digest(Path(__file__)),
                       "one_shot_attempt": True}, "audit_attempt_marker")


def _model_scorer(bundle: Path, start: float, baseline_rss: int):
    load_start = perf_counter()
    require_networkless_linux()
    import numpy as np
    import onnxruntime as ort
    from tokenizers import Tokenizer

    tokenizer = Tokenizer.from_file(str(bundle / "tokenizer.json"))
    tokenizer.no_truncation()
    tokenizer.no_padding()
    config = json.loads((bundle / "config.json").read_text(encoding="utf-8"))
    pad = config.get("pad_token_id")
    require(type(pad) is int and pad >= 0, "padding_configuration")
    options = ort.SessionOptions()
    options.intra_op_num_threads = 4
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.log_severity_level = 4
    session = ort.InferenceSession(str(bundle / bundle_admission.MODEL),
                                   sess_options=options,
                                   providers=["CPUExecutionProvider"])
    names = {item.name for item in session.get_inputs()}
    require({"input_ids", "attention_mask"} <= names <=
            {"input_ids", "attention_mask", "token_type_ids"} and
            len(session.get_outputs()) == 1, "model_contract")
    startup = perf_counter() - load_start
    require(startup <= MAX_STARTUP_SECONDS and
            peak_rss() - baseline_rss <= MAX_ADDED_RAM_BYTES and
            perf_counter() - start <= MAX_TOTAL_SECONDS, "startup_resource_budget")
    timings: list[float] = []
    max_tokens_seen = 0
    pairs_scored = 0
    model_run_calls = 0

    def score(pairs: list[tuple[str, str]]) -> list[float]:
        nonlocal max_tokens_seen, pairs_scored, model_run_calls
        require(1 <= len(pairs) <= BATCH_SIZE, "pool_budget")
        tick = perf_counter()
        encoded = [tokenizer.encode(question, cue, add_special_tokens=True)
                   for question, cue in pairs]
        sizes = [len(row.ids) for row in encoded]
        require(all(0 < size <= MAX_PAIR_TOKENS for size in sizes),
                "complete_input_budget")
        max_tokens_seen = max(max_tokens_seen, max(sizes))
        width = max(sizes)
        ids = np.full((len(pairs), width), pad, dtype=np.int64)
        mask = np.zeros_like(ids)
        types = np.zeros_like(ids)
        for index, row in enumerate(encoded):
            ids[index, :sizes[index]] = row.ids
            mask[index, :sizes[index]] = row.attention_mask
            types[index, :sizes[index]] = row.type_ids
        payload = {"input_ids": ids, "attention_mask": mask,
                   "token_type_ids": types}
        output = session.run(None, {name: payload[name] for name in names})
        model_run_calls += 1
        pairs_scored += len(pairs)
        elapsed = perf_counter() - tick
        if len(pairs) == BATCH_SIZE:
            timings.append(elapsed)
        require(len(output) == 1 and output[0].shape in
                ((len(pairs),), (len(pairs), 1)), "model_output")
        values = [float(value) for value in output[0].reshape(-1)]
        require(all(math.isfinite(value) for value in values), "score_invalid")
        require(perf_counter() - start <= MAX_TOTAL_SECONDS and
                peak_rss() - baseline_rss <= MAX_ADDED_RAM_BYTES,
                "scoring_resource_budget")
        return values

    def resources() -> dict:
        require(timings, "pool_timing_unavailable")
        ordered = sorted(timings)
        p95 = ordered[math.ceil(0.95 * len(ordered)) - 1]
        return {"startup_ms": round(startup * 1000, 3),
                "pool30_p95_ms": round(p95 * 1000, 3),
                "max_pair_tokens": max_tokens_seen,
                "pairs_scored": pairs_scored, "model_run_calls": model_run_calls,
                "peak_added_ram_mib": round(max(0, peak_rss() - baseline_rss) / 1024**2, 3),
                "elapsed_ms": round((perf_counter() - start) * 1000, 3),
                "resource_passed": p95 <= MAX_POOL_SECONDS and
                    perf_counter() - start <= MAX_TOTAL_SECONDS and
                    peak_rss() - baseline_rss <= MAX_ADDED_RAM_BYTES}

    return score, resources, startup


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
    # The parent's exclusive attempt marker is also verified by the child.
    # Claim the child execution itself so manually invoking --child cannot
    # replay the one approved inference attempt after a crash or partial run.
    write_exclusive(child_claim_path(), {
        "procedure": PROCEDURE,
        "freeze_sha256": args.expected_freeze_sha256,
        "harness_sha256": digest(Path(__file__)),
        "child_claimed_once": True,
    })
    fixture, _raw = fixture_admission.read_json(args.fixture,
                                                 fixture_admission.MAX_FIXTURE_BYTES)
    groups = fixture["groups"]
    baseline_rss = peak_rss()
    _emit({"event": "preflight_ready", "freeze_sha256": identity["freeze_sha256"]})
    scorer, resources, startup = _model_scorer(args.bundle, start, baseline_rss)
    _emit({"event": "startup_ready", "startup_ms": round(startup * 1000, 3)})
    train_groups = [group for group in groups if group["split"] == "train"]
    calibration_groups = [group for group in groups if group["split"] == "calibration"]
    heldout_groups = [group for group in groups if group["split"] == "heldout"]
    require(len(train_groups) == 96 and len(calibration_groups) == 48 and
            len(heldout_groups) == 48, "split_counts")

    # Training logits are obtained before fitting; only public train labels fit.
    train_logits = []
    train_pairs = [pair_text(group, index) for group in train_groups for index in range(4)]
    for offset in range(0, len(train_pairs), BATCH_SIZE):
        train_logits.extend(scorer(train_pairs[offset:offset + BATCH_SIZE]))
    train_features = []
    train_labels = []
    for number, group in enumerate(train_groups):
        train_features.extend(features(group, train_logits[4 * number:4 * number + 4]))
        train_labels.extend(page and cue for page, cue in zip(
            group["original_page_usefulness_per_window"],
            group["exact_cue_usefulness_per_window"], strict=True))
    model = fit_classifier(train_features, train_labels)
    calibration = scored_rows(calibration_groups, model, scorer)
    try:
        threshold, calibration_metrics = choose_threshold(calibration)
    except AuditError as exc:
        if str(exc) != "calibration_gate_rejected":
            raise
        result = {"status": "calibration_rejected_no_heldout", "candidate_passed": False,
                  "heldout_scored": False, "release_gate_passed": False,
                  "provider_requests": 0, "database_writes": 0,
                  "calibration": summarize(calibration, math.nextafter(1.0, math.inf),
                                           include_grades=False),
                  "resources": resources(), "freeze_sha256": identity["freeze_sha256"]}
        write_exclusive(args.output / "audit-result.json", result)
        _emit({"event": "result", "result": result})
        return
    rule = {**model, "threshold": threshold, "calibration": calibration_metrics,
            "fixture_sha256": digest(args.fixture),
            "freeze_sha256": identity["freeze_sha256"], "heldout_scored": False}
    rule_hash = write_exclusive(args.output / "calibration-rule.json", rule)
    _emit({"event": "calibration_frozen", "rule_sha256": rule_hash})
    heldout = scored_rows(heldout_groups, model, scorer)
    require(digest(args.output / "calibration-rule.json") == rule_hash and
            digest(args.fixture) == rule["fixture_sha256"], "measurement_drift")
    heldout_metrics = summarize(heldout, threshold, include_grades=True)
    resource = resources()
    quality_passed = heldout_passed(heldout_metrics)
    passed = quality_passed and resource["resource_passed"]
    status = ("public_passed" if passed else "public_resource_rejected" if
              not resource["resource_passed"] else "public_quality_rejected")
    result = {"status": status,
              "candidate_passed": passed, "release_gate_passed": False,
              "heldout_scored": True, "provider_requests": 0, "database_writes": 0,
              "calibration": calibration_metrics, "heldout": heldout_metrics,
              "resources": resource, "rule_sha256": rule_hash,
              "freeze_sha256": identity["freeze_sha256"]}
    write_exclusive(args.output / "audit-result.json", result)
    _emit({"event": "result", "result": result})


def supervise(args: argparse.Namespace) -> dict:
    require_bounded_container()
    require_approved_ledger()
    require(perf_counter() - args.audit_start < MAX_TOTAL_SECONDS,
            "total_timeout")
    marker = attempt_marker_path()
    require(not marker.exists() and not marker.is_symlink(), "audit_attempt_consumed")
    require(not args.output.exists(), "output_exists")
    write_exclusive(marker, {"procedure": PROCEDURE,
                             "freeze_sha256": args.expected_freeze_sha256,
                             "harness_sha256": args.harness_sha256,
                             "one_shot_attempt": True})
    args.output.mkdir(mode=0o700)
    command = [sys.executable, str(Path(__file__)), "--child", "--execute-approved",
               "--corpus", str(args.corpus),
               "--fixture", str(args.fixture), "--bundle", str(args.bundle),
               "--runtime-manifest", str(args.runtime_manifest),
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
    started = args.audit_start
    preflight_at: float | None = None
    startup_ready = False
    heldout_may_have_opened = False
    result = {"status": "child_unavailable", "candidate_passed": False,
              "release_gate_passed": False, "heldout_scored": False,
              "provider_requests": 0, "database_writes": 0}
    try:
        while True:
            elapsed = perf_counter() - started
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
            elif event == "calibration_frozen" and startup_ready:
                heldout_may_have_opened = True
                continue
            elif event == "result" and startup_ready and type(message.get("result")) is dict:
                result = message["result"]
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
    if heldout_may_have_opened and result["status"] not in (
            "public_passed", "public_quality_rejected", "public_resource_rejected"):
        result["heldout_scored"] = "unknown_after_calibration"
    result_path = args.output / "audit-result.json"
    if result_path.is_file():
        try:
            saved, _raw = fixture_admission.read_json(result_path, 300_000)
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
        if (not isinstance(heldout, dict) or not isinstance(resource, dict)
                or not heldout_passed(heldout) or not resource.get("resource_passed")
                or result.get("status") != "public_passed"):
            result["status"] = "result_mismatch"
            result["candidate_passed"] = False
    if result_path.exists() and result_path.is_file():
        # A child result is an immutable receipt. Any supervisor correction is a
        # separate file, never a rewrite of the original observation.
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
        require(not args.child or args.output is not None, "output_required")
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
                                          "calibration_rejected_no_heldout") else 1
    except (AuditError, fixture_admission.FixtureError, OSError, ValueError,
            ImportError) as exc:
        reason = str(exc) if isinstance(exc, (AuditError, fixture_admission.FixtureError)) \
            else type(exc).__name__
        if args.child:
            _emit({"event": "failed", "reason": reason})
        else:
            _emit({"status": "audit_unavailable" if args.execute_approved else
                   "audit_rejected_no_scoring", "reason": reason,
                   "provider_requests": 0,
                   "database_writes": 0, "candidate_passed": False,
                   "release_gate_passed": False})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
