# Approved isolated local relation-checker experiment

## Scope and preserved context

- The owner approved the proposed local instruction-model relation checker
  after the classical larger NLI/QA experiment recovered only one of six
  reviewed positives. The Lane 6 plan now records this experimental branch.
  Approval covers one candidate and at most three declared configurations,
  not activation, new release budgets, Gemini calls or a paid reindex.
- Started on `main` at `6c02d6c`; preserved the substantial prior working tree,
  original populated volume, root `.env`, private backup and installed model
  bundle. The existing local app remains at schema `0021` with v1 Ask enabled.
- Reviewed current plan, dated fallback/cutover evidence, ADR-019, source-unit
  binding and offline-test commands. No private source text, user questions,
  claims, quotes, IDs, credentials or raw model output enter this record.

## Candidate and frozen design

- Candidate: public `Qwen/Qwen3-0.6B`, Apache-2.0, using the ONNX-community
  INT8 export at revision `da1453100cf3ff33ef56d17983fc7a8648706db6`.
  The five pinned files total **626,816,674 bytes**. Model SHA-256 is
  `d93222c672992a398eeea3a4a1ca025738efd9a18ba5f1691419ff8ae23a8e75`.
  All model/tokenizer/config/template/card file lengths and digests were
  verified before inference. Public artifacts remain in an ignored cache.
- The first model download reached its 180-second limit. Manually resumed
  only the task-owned partial file with a 300-second limit and zero automatic
  retries; the completed file matched its public digest. Nothing private was
  transmitted in those download requests.
- Added `scripts/local_relation_candidate.py` and
  `scripts/evaluate_local_relation.py`, separate from the runtime factory.
  The classifier scores one decision token; it never generates a replacement
  answer or reasoning text. Source units remain exact server-derived slices;
  current quote membership and source binding precede model evaluation.
  Source text and logits stay in memory. The export uses CPU-only inference,
  two inference threads, empty bounded KV inputs and the pinned hard
  non-thinking chat-template prefix.
- Three configurations were declared before private evaluation: joint
  support/answerability/conflict decision; decomposed three-check decision;
  joint decision with reversed-label agreement. A single decision requires
  its token to be the global-vocabulary winner with probability at least
  0.80. This is a conservative experimental cutoff, not calibrated accuracy.
  Unknown, inconsistent, malformed, unavailable or over-budget decisions
  safely reject and do not count as successful semantic negatives.
- Experimental ceilings remain 1 GiB artifacts, 2 GiB additional peak RSS,
  20-second startup and 5-second complete-check p95. The disposable container
  imposes a stricter 2 GiB total-memory limit and two CPUs. The experiment has
  before/after per-case resource guards and a 600-second aggregate guard.
  Model runs have a cancellable complete-check deadline; evidence is never
  truncated to make a verdict fit. Public CPU preflight led to a frozen
  512-token input bound before the private probe because memory was already
  close to the ceiling.

## Independent controls and review

- A subagent authored 24 public synthetic cases, with three per adversarial
  class (same-proposition conflict, different-proposition distractor,
  ambiguity, negation, altered numbers, mixed claims, prompt injection) plus
  three clean positives. Matching conflict/distractor pairs vary only the
  additional evidence. This development corpus is not a private reviewed
  holdout or a replacement for the maintained eleven-case corpus.
- The same subagent independently reviewed source binding, resource guards,
  private-output boundaries and metrics. Fixed its findings about unknown/C
  decisions incorrectly passing negative metrics, full-check deadlines,
  public fixture identity before emitting labels, every-case resource checks
  and smoke inference-versus-quality reporting. A follow-up review confirmed
  those fixes; the final minor smoke post-inference RSS check was also added.
- Focused keyless contracts: **36 passed**, including the existing larger
  experiment contracts. These tests load no model and make no provider calls.

## Public CPU preflight

- Startup: **12,983.45 ms**; one public complete check: **3,449.41 ms**;
  peak resident-memory increase: **1,849.71 MiB**. CPU inference completed,
  but its decision was unknown and the positive quality check did not pass.
  These figures prove the export runs, not answerability or release safety.
- A subsequent code-only hardening disables ONNX platform telemetry and
  checks smoke peak memory after inference. That code was not loaded into
  the already-running full benchmark; no repeated model result is claimed
  for it. No application image/dependency or provider policy changed.

## Private and public benchmark

- The bounded probe compares six reviewed authored positive/negative pairs,
  six unrelated-question controls, the maintained eleven cases and the new
  24 public controls. It is single-source authored-claim evidence, not a
  generated-model-answer replay or real-query retrieval test. A configuration
  failing any development case stops after one repetition; only a complete
  pass may advance to three repetitions.
- The benchmark is in progress at the time of this initial record. Results,
  resource failures and cleanup will be appended; no release checkbox is
  changed based on preliminary progress.

## Primary references

- [Qwen model card and hard non-thinking mode](https://huggingface.co/Qwen/Qwen3-0.6B)
- [Pinned public ONNX export](https://huggingface.co/onnx-community/Qwen3-0.6B-ONNX/tree/da1453100cf3ff33ef56d17983fc7a8648706db6)
- [ONNX Runtime termination and telemetry APIs](https://onnxruntime.ai/docs/api/python/api_summary.html)

## Completed benchmark and decision

- All three declared configurations completed their first development replay;
  each accepted **0/6** reviewed private positives. None qualified for the
  three-repeat acceptance gate, so no extra repetitions were performed.
  The candidate remains unselected; this is a failure of this candidate and
  frozen configuration, not evidence that every local instruction model is
  incapable of the task.
- Full-run startup was **13,273.29 ms**; measured peak RSS increase was
  **2,000.94 MiB**. These are within the experimental startup/additional-RSS
  ceilings, but container memory reached its stricter 2 GiB total limit.
  The joint configuration p95 was **5,080.50 ms**, exceeding the 5-second
  latency ceiling. Source/input budget and unavailable inference remain
  distinct from conclusive semantic rejections.
- Joint configuration: 0/6 private positives; zero accepted private wrong
  claims or unrelated questions; **2/11** conclusive maintained-case passes
  and **1/24** conclusive adversarial passes. Across its 53 cases, nine
  inferences were unavailable and 39 decisions uncertain/inconsistent. Those
  outcomes are safe abstentions, not successful semantic negatives. The
  aggregate captured output for the other configurations confirms 0/6 private
  positives but does not retain all their per-category totals; no missing
  metric has been reconstructed or filled in. No whole benchmark was replayed
  merely to recover that output.
- The immutable model and fixed 0.80 full-vocabulary decision cutoff were
  not tuned against the six private cases. This cutoff is uncalibrated and
  token-level uncertainty may explain some refusals; the result does not
  isolate model capability from prompt/decision-policy calibration. It does
  establish that the tested policy cannot pass the required positive gate.
- No remote AI request, generated answer or database mutation occurred.
  The app's installed bundle, factory, release-resource thresholds,
  two-request policy, active embedding space and schema remain unchanged.
- Subsequent code-only hardening reserves one complete call plus cleanup time
  before the aggregate deadline and exposes only a fixed resource-failure
  classification. It was added after the completed run and is not represented
  as another measured model result.

## Final checks and cleanup

- Full backend offline suite after the new experiment/control contracts:
  **1062 passed, 119 skipped, 2 deselected**, 182.77 seconds. Skips/deselections
  do not establish live-provider, hosted-CI or manual assistive-technology proof.
- Both isolated model containers were automatically removed. Final Docker
  inventory showed no one-off container; all eight original app services were
  healthy and routed readiness returned HTTP 200. Original database, volume,
  root `.env`, private archive and installed runtime bundle were preserved.
- Public experiment artifacts remain ignored and outside runtime mounts for
  reproducibility. No new package was installed in the operator environment or
  added to runtime requirements. The private benchmark used existing worker
  environment/configuration but accessed no provider credential for a request.
- A Docker memory-read command initially used an unsupported `stats --filter`
  option. Repeated the read with the exact task-owned container name; no
  container mutation was involved.
- No further instruction-model configurations or live Ask answer test are
  selected from these results. Lane 6 remains 3/7; real query-vector retrieval,
  independent reviewed holdout, support quality and overall release evidence
  remain outstanding.
