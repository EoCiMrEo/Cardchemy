# Approved public calibration audit

## Authority and scope

- Continue Lane 6 on preserved `main` / `6c02d6cf063acf83f4da5c08cfc4a3aa2c94be57`
  and the existing remediation working tree. The owner approved one 96-case
  local measurement/calibration extension on 2026-09-26 before plan changes.
  The earlier three-configuration candidate failed; that historical run is
  not repeated or relabelled as a success.
- Use the same pinned public Qwen3-0.6B INT8 export and exact joint prompt;
  download no model. Keep 1 GiB artifacts, 2 GiB additional peak RSS,
  20-second model startup, 5-second complete-check p95 and a 600-second total
  public run. Keep all evidence intact within the existing 512-token bound.
  No provider call, private Knowledge read, database write, runtime activation,
  dependency change or runtime threshold change is authorized by this audit.
- The large existing diff, root `.env`, original populated volume, backup and
  installed support bundle are preserved. Lane 6 remains 3/7 checked.

## Preregistered selection procedure — before inference

- Independently author and review 96 public cases, calibration 24 supported /
  24 unsupported and heldout 24/24, using distinct scenario/template families.
  Review labels and source membership before freezing the fixture digest.
  No model score or private six-case outcome may guide fixture changes.
- The original full-vocabulary winner and complete source/input/deadline
  guards remain intact. Add numeric-only observations: winner is A/B/C or
  nonlabel, winner probability, total A/B/C probability mass and margin to the
  strongest competing global token. Never decode or output token IDs, logits,
  reasoning, answers or source text. The previous candidate `decide` still
  applies its original 0.80 cutoff; only the isolated audit selects a rule.
- Fixed experimental admissibility: global winner must be A or B, total label
  mass at least **0.50**, margin over the second global token at least **0.01**.
  Try confidence floors **0.80, 0.65, 0.50, 0.25, 0.10**, in that strictest-first
  order. Choose at most the first rule under which all 48 calibration decisions
  are conclusive and correct. This is the only public parameter search; do not
  change prompt, label mapping, mass/margin floors or grid after seeing scores.
  Normalizing only A/B/C is forbidden because it conceals off-format competition.
- Any calibration misclassification, unknown/nonlabel winner, failed inference
  or inability to meet the selected rule/resource gate keeps heldout closed.
  Freeze the selected rule before heldout inference. A first heldout error,
  uncertain decision, unavailable inference or resource failure stops; require
  all 24 heldout positives and zero accepted negatives, with every negative
  conclusive. Unknown/unavailable is not a semantic negative pass.
- Public success alone does not release a candidate. Only a public pass can
  justify a separately bounded private/maintained replay under the frozen rule;
  independent reviewed course holdout and real query-vector retrieval remain
  mandatory. This public harness never reads private cases or activates Ask.

## Implementation and pre-inference review

- Added `scripts/calibrate_local_relation.py` and keyless selection/resource/
  uncertainty contracts. `scripts/local_relation_candidate.py` adds numeric
  `observe`; existing `decide` delegates to it with unchanged acceptance.
  Complete prompts are tokenized and rejected before model inference if any
  exceeds 512 tokens. No source is cropped. Aggregate output separates format,
  confidence bins, input failures and inference/latency failures.
- Initial targeted audit and existing classifier contracts: **39 passed**.
  Fakes prove that calibration failure leaves heldout closed, a selected rule
  cannot adapt to a heldout error, public success is separate from release,
  uncertain negatives never pass, and budget/digest/numeric failures close safely.
  These are boundary tests, not measured model-quality evidence.
- Independent 96-case semantic review found six ambiguous labels before any
  inference. Source exclusive values and full condition/claim wording are being
  corrected. Scenario-family IDs alone did not demonstrate distinct grammatical
  template families; heldout structures are being rewritten and rereviewed.
  Fixture/model inference is pending the completed review and immutable digest.
  The initial fixture is not a frozen evaluation artifact or release evidence.

## Completed independent review and frozen inputs

- The author corrected all six label ambiguities and rewrote heldout source
  constructions/questions. Independent reviewer then reviewed **96/96** cases
  before any model inference and found no remaining semantic label defect.
  Each split retains 24 positive/24 negative cases; exact quote offsets and
  unique public scenario/source families are verified. Shared semantic categories
  are intentional, while declared source constructions and interrogative versus
  imperative question forms differ across splits. This is an authored public
  construction holdout, not an independently labelled private course corpus.
- Frozen fixture SHA-256:
  `f87855899d54ce89f11979fe1876f6c5495c2803f94c886e38de293f39b51369`.
  The harness and integrity tests require that digest. Do not edit it after
  viewing scores. Reviewer made no model/provider call or test run.
- Independent harness review caught tokenizer allocation before pinned size
  checks and inference-only latency measurement. Added root/file/size guards
  and streaming SHA before tokenizer construction. Per-case timing now begins
  before source binding/unit/prompt construction, includes inference tokenization
  and the selected rule, and rechecks the complete five-second deadline.
- Added actual full-vocabulary fake-ONNX tests proving global nonlabel winners
  are never forced to A/B/C, label mass uses the full softmax, winner margin
  uses the global runner-up, and malformed/NaN outputs fail closed. Existing
  `decide` still uses the original 0.80 acceptance. **43** targeted contracts
  passed after those repairs; no model-quality result is claimed yet.

## Completed one public audit

- Final pre-inference checks: **55** classifier/audit/fixture contracts passed.
  Independent harness rereview found no remaining blocker. Reviewer confirmed
  complete-case timing, streamed artifact preflight, global-vocabulary tests,
  frozen fixture and closed heldout/private paths; it made no inference call.
- Executed once in a task-owned read-only container with two CPUs and a
  2 GiB total-memory limit. Same five-file public bundle: **626,816,674 bytes**.
  Startup **14,897.15 ms**, maximum complete input **418 tokens**, peak RSS
  increase **2,000.70 MiB**, complete-case p95 **3,170.07 ms**. These meet
  experimental ceilings; sampled container memory was 1.997 GiB of its 2 GiB
  total limit, so there is little headroom. Routed app readiness remained 200.
- All **48** calibration inferences completed: A winners 15, B winners 3,
  C winners 0, nonlabel global winners **30**. Only **7/48** had the correct
  A/B global label. The unchanged 0.80 confidence rule yielded three correct
  conclusive labels. No inference failure was counted as a negative success.
  Nonlabel winners were not decoded or logged; their exact text/category was
  not retained and cannot be inferred from these aggregate counts.
- Frozen bins [0, .10, .25, .50, .65, .80, 1]: winner confidence counts
  [0, 0, 7, 13, 5, 23]; label-mass counts [17, 6, 7, 2, 2, 14]; global
  margin counts [1, 7, 12, 4, 10, 14]. All are full-vocabulary probabilities,
  not calibrated probabilities that a claim is true. They expose format
  uncertainty; **11/18** valid A/B winners were also wrong, so merely accepting
  lower-confidence or off-format decisions cannot solve this audit.
- Result **`calibration_no_rule`**, selected rule null. Heldout was **not
  evaluated**, private cases zero, provider requests zero, database writes zero,
  release gate false and runtime unchanged. No further configuration, fixture
  edit, repetition, private replay or model activation follows from this run.
  This candidate/procedure fails; the result does not prove all local models
  incapable or identify the nonlabel output's unretained token.

## Verification and remaining work

- Full backend offline after the new audit and repaired retrieval contracts:
  **1152 passed, 119 skipped, 2 deselected**, 146.96 seconds. Skips/deselections
  are not provider, PostgreSQL, hosted-CI or manual assistive-technology proof.
- Runtime factory, installed support bundle, original volume/root `.env` and
  the current two-request policy remain preserved. Public research artifacts
  remain ignored and outside runtime mounts. No new model/dependency was added.
- Lane 6 remains 3/7: representative reviewed course holdout, real-query
  retrieval, general answer/support improvement and release gates remain open.
  Do not select another candidate or expand a budget without a concrete new
  proposal and the owner's required plan approval. The approved source-browsing
  fallback remains available on eligible failed/abstained attempts.

## Concrete next proposal — not approved or implemented

- Keep the exact retrieval baseline: the separately approved repaired batch
  finds all six confirmed source pages in top five, while lexical variants
  rank worse. The reviewed general support blocker remains; another same-policy
  paid answer call is not an independent verifier improvement.
- Independently preflighted one public larger candidate's metadata only:
  `onnx-community/Qwen3-4B-ONNX`, revision
  `98ddba15d05dede4435afb63f13280abcdbc2a48`, export path
  `onnxruntime/cpu_and_mobile/cpu-int4-kld-block-128`. The eight-file graph,
  external data, tokenizer/config/template/README bundle is **2,897,393,599
  bytes (2.698408 GiB)** according to immutable public API metadata. This is
  the CPU mixed INT4/INT8 export, not the similarly named WebGPU variant.
  No new graph/weights were downloaded and no new-model inference occurred.
- Public graph digest:
  `b4547cf9327bd532cb81703cf013f958117ba5a3e5a81c7c79a33aba534ff337`;
  external-data digest:
  `d6003acd70841b99a44ce4c21d13dc42244e3ec3b7c12d70919f9b55440bbc45`;
  public artifact SHA-256 (tokenization file; label clarified after scanner false positive):
  `979d160e081df25a1bf7f4e2e8f4c441b5dfdc9a8e84aec9f32e80445e1b59b8`.
  Verify all complete-file lengths/digests before any inference; metadata alone
  does not verify the bytes or operator compatibility.
- The [official base model card](https://huggingface.co/Qwen/Qwen3-4B)
  identifies Apache-2.0 and 36 layers. The community export README has no
  separate license metadata. Check provenance and retained upstream notices
  before distribution. Its public GenAI config indicates 36 layers, eight KV
  heads, head size 128 and vocabulary 151,936, with input IDs, attention mask
  and past KV inputs; no named position-ID input. The existing 28-layer scorer
  cannot load it unmodified. Plain pinned ONNX Runtime CPU kernel/input/output
  compatibility remains unproven; validate graph metadata/session before scoring
  and stop on incompatibility rather than installing a new runtime secretly.
- Proposed separate experiment: at most **3 GiB** public artifacts, **4 GiB**
  additional peak RSS, **5 GiB** container total memory, **4 CPU**, **30-second**
  startup, **10-second** complete-check p95, **600-second** total public audit.
  Host aggregate capacity is 15.77 GiB RAM/16 logical CPUs; Docker currently
  7.637 GiB/16 CPUs. Eight app services sampled about 1.077 GiB together,
  leaving about 1.56 GiB nominal Docker margin with a 5 GiB experiment. These
  are current samples, not peak/headroom guarantees; stop on pressure/failure.
  No Docker allocation or runtime support budget would change in this experiment.
- Preserve the frozen 96-case public corpus, exact joint instruction task and
  full-source/global-label rules. Same public-only calibration procedure may
  select one rule, then 24/24 heldout positives and zero accepted negatives with
  all negatives conclusive. Require public success before any separate reviewed
  private/maintained replay. At a 10-second ceiling, 96 cases may not finish in
  600 seconds; a timeout is incomplete/failure, never permission to extend the
  run, shrink the corpus or accept unknowns. No paid-provider call is proposed.
- This is a hypothesis that a larger model could recognize the relations, not
  a quality guarantee. Candidate/version/resource changes require the owner's
  explicit plan approval before downloads, implementation or execution. Runtime
  activation still needs measured quality/resources and a separately approved
  versioned policy/ADR/release change; do not lower the current safety gate.

Primary metadata sources:

- [Pinned community export](https://huggingface.co/onnx-community/Qwen3-4B-ONNX/tree/98ddba15d05dede4435afb63f13280abcdbc2a48)
- [Pinned CPU export config](https://huggingface.co/onnx-community/Qwen3-4B-ONNX/raw/98ddba15d05dede4435afb63f13280abcdbc2a48/onnxruntime/cpu_and_mobile/cpu-int4-kld-block-128/genai_config.json)
