# Lane 6 related Knowledge fallback and local cutover

## Scope and starting state

- Continued the owner-approved Lane 6 investigation and the separately approved
  **Related published Knowledge** presentation. The owner confirmed all six
  selected private source/question/claim/control pairs, and allowed local
  database/configuration operations. No private source text, prompts, raw model
  output, secrets, or identifiers are included here.
- The checkout began on `main` at `6c02d6c` with substantial existing Lane 0–6
  work. It was preserved. The populated local database was at Alembic
  `20260925_0019`; all app services were stopped when Docker Desktop resumed.
  Only the existing database container was started for the backup and checks.
- Lane 6 remains 3/7 checked. The six reviewed positive pairs bind to the
  staged source-unit contract but the local verifier rejects all six, while
  wrong-claim and unrelated-question controls reject. No new answer policy or
  retrieval cutover has been activated.

## Implemented source-browsing fallback

- Added deterministic, bounded exact source windows from retrieved canonical
  chunks and job-owned source offsets. At most two related excerpts may appear
  after a failed answer or a completed abstention. They are labeled as related
  Knowledge, separate from a verified answer and its citations.
- Reads reauthorize the current owner/enrollment, selected documents,
  publication, revision, corpus and embedding space; the whole bundle hides on
  drift. The database stores only source references and offsets, not duplicate
  passage text. Terminal cleanup, expiry, cancellation and dead-lease recovery
  clear references. No extra provider request or automatic paid retry was added.
- Added typed browser rendering, historical failed/abstained job handling,
  stale-history clearing, accessibility copy and private export boundaries.
  Revision `20260925_0021` adds the private reference table and constraints.

## Verification so far

- Full backend offline suite: 1002 passed, 116 skipped, 2 deselected before
  the final recovery cleanup. Focused recovery checks passed afterward.
- Guarded disposable PostgreSQL suite after the cleanup: 100 passed, 3 skipped,
  1020 deselected. This included actual authorized excerpt reads, unpublication
  and enrollment-revocation hiding, dead-lease cleanup, schema/head/drift and
  upgrade/downgrade/re-upgrade. It did not use the populated app database.
- Full frontend `npm run check -- --workers=2`: 45 component tests, four unit
  tests and 68 Chromium tests passed; one separately gated live-reset case was
  skipped. The built frontend image also completed successfully.
- Deterministic, keyless cross-stack journey passed RAG-off and RAG-on paths,
  including disposable migration through `0021`. Its processes, data and
  generated credentials were cleaned up.
- Root configuration migration preflight and `docker compose config --quiet`
  passed without printing configuration values.
- Before local migration, created a private ignored custom-format archive of
  the original `0019` database. Restored it into a separately named database;
  Alembic head and exact row counts across seven content-free tables matched.
  The rehearsal database was removed; original database/volume and archive
  remain. The archive SHA-256 was recorded in the operator session.

## Current boundary and follow-up

- The local stack has not yet been migrated/recreated at the time of this
  record. The `0021` schema and fallback are staged in source, while the live
  database remains at `0019`.
- A separately fenced extractive/relation-scoped local support candidate is
  under offline review. It may only replace the v1 policy after reviewed
  positives and adversarial negatives pass. Source-oracle retrieval ranks do
  not substitute for real question-vector evidence, so retrieval and the
  overall Ask quality gate remain open.
- Live-provider requests in this continuation: zero. Existing operator
  authorization for a limited future Ask retry does not establish that a
  release candidate is safe or that prior uncertain charges were zero.

## Local cutover completed

- Before migration, the original database had no queued or running generation,
  Knowledge-index, Ask or email work. The migration image was built from this
  checkout; `docker compose run --rm migrate` applied `0019→0020→0021` to the
  original database after the separate archive rehearsal. The seven checked
  table counts were unchanged. Running-image `alembic current --check-heads`
  reported `20260925_0021 (head)` and `alembic check` reported no new upgrade
  operations.
- Rebuilt the backend, generation/index/email/answer-worker and frontend images
  and recreated only the app services; the existing database container and
  populated volume were retained. All eight running services were healthy;
  routed `/api/health/ready` returned HTTP 200. The running API reported only
  the non-secret flags `rag_enabled=True`, `ask_enabled=True`, and
  `local_support=True`. Opening the local site showed the new Cardchemy login
  page; no user credentials were entered and no paid Ask job was submitted.
- The archive rehearsal proved format, schema and seven exact row counts. Its
  separate restored database was removed after comparison. The deterministic
  browser journey ran on another disposable database, so the archive has not
  yet had an authenticated application journey against that restored clone.
  The archive itself remains private under the ignored `backups/` directory.

## Remaining source/answer investigation

- A read-only source audit found no demonstrated loss in the six inspected
  original PDF/canonical pages. Standalone headings currently move to the
  chunk `section`, while body-only text feeds embedding, text search and
  citation containment. An exact heading-to-answer page span helped one
  entailment score but did not resolve the other reviewed false rejections.
- A fenced, provider-free strict relation prototype supported one of six
  reviewed positives and rejected every wrong-claim and unrelated-question
  control in that small replay. This is insufficient for activation. The
  current v1 policy and two-request cap remain unchanged. Real question-vector
  retrieval, general positive yield and the full Lane 6 release gate remain
  unproven.

## Restored application-read rehearsal

- A further rehearsal restored the retained pre-upgrade archive into another
  separately named database, migrated that clone from `0019` to `0021`, and
  passed Alembic drift checks. Application services successfully read an
  authorized instructor's Subject, two sets and private Ask history from that
  clone. The seven previously checked row counts still matched the live
  database. This adds application-read proof to the earlier archive check;
  it is not an authenticated browser journey or a restored student journey.
  The archive contained no student principal, so no student-read claim is made.
  The clone was removed after verification; the original volume and private
  ignored archive remain intact.

## Approved larger local verifier experiment

- The owner explicitly approved an isolated NLI/QA experiment on 2026-09-26,
  with ceilings of 1 GiB public artifacts, 2 GiB additional RSS, 20 seconds
  startup and 5 seconds p95 verification. The plan now records that permission
  separately from runtime release budgets. It did not authorize activation.
- Added `scripts/evaluate_larger_local_support.py` and keyless safety tests.
  The harness validates public repository revisions and artifact hashes,
  checks the candidate NLI label order, fails closed on unavailable inference,
  uses authorized current Knowledge reads, and outputs only fixed labels and
  aggregate verdict/resource measurements. Source text stays in memory.
- Downloaded the public quantized DeBERTa-v3-base MNLI/FEVER/ANLI and
  RoBERTa-base SQuAD2 artifacts into an ignored experiment directory. The
  eight-file manifest records pinned revisions, lengths and SHA-256 digests;
  total size is 381,768,174 bytes (364.08 MiB). The installed runtime bundle was
  preserved. A slow initial download was stopped after identifying only the
  task-owned launcher/child; the remaining QA download completed with bounded
  connection/total time and no automatic retries. The zero-length task-owned
  partial file was removed before resuming. No application process was stopped.
- Ran disposable answer-worker containers with two CPUs, a 2 GiB total-memory
  limit and read-only script/artifact/fixture mounts. Current-quote and separate
  canonical-page-hypothesis experiments each used three repetitions of six
  reviewed positives, six wrong claims, six unrelated questions and eleven
  maintained cases. Current baseline: 0/6 positives. Larger NLI: 1/6. Larger QA:
  0/6. Both larger: 1/6. All combinations retained 11/11 maintained-case passes,
  with no sampled wrong claims or unrelated questions accepted. Private
  verdicts repeated consistently. The larger NLI recovered only the acronym.
- Current-quote startup was 13.88 seconds; sampled RSS increase 973.92 MiB.
  Variant p95 values were 123.02 / 372.23 / 154.08 / 422.03 ms. The separate
  page-window experiment had 15.17-second startup, 973.65 MiB sampled RSS
  increase, and p95 139.36 / 442.32 / 173.09 / 402.45 ms in the same order.
  Sampled RSS is not peak RSS. The second deterministic selector found all
  six exact page windows; three are not citable under current chunk contracts.
  It produced the same positive yields, not a deployable citation policy.
- These experiments met their resource ceilings but did not solve reviewed
  answerability. No runtime model, factory, support threshold, release budget,
  retrieval representation or embedding space changed. No Gemini call,
  database write or paid reindex occurred. The model-answer and real-query
  retrieval gates remain open; sampled negative success is not general safety.

## Subsequent verification

- Full backend offline suite after the recovery cleanup and acronym prototype:
  **1026 passed, 119 skipped, 2 deselected**. The skips/deselections do not
  establish live-provider success.
- Focused larger-experiment and acronym contracts after the evaluator's
  unavailable-inference handling: **30 passed**. An unavailable verifier cannot
  count as a successful negative evaluation. Public-artifact path and role
  guards and unchanged v1 release policy are covered.
- Lane 6 remains **3/7** complete; none of the larger-model results justifies
  checking the support-quality or overall release item.
- Final context validation passed: 37 required files, 76 active guides and
  1157 local links. Whitespace/diff validation passed. All eight local services
  remained healthy and no disposable one-off container remained. A read-only
  application-connection query confirmed zero remaining restore databases.
  An initial direct `psql` cleanup check used an unavailable database role and
  failed without changing data; the validated application connection resolved
  that check. The private backup and ignored, public-only model cache are
  retained; the experimental override is not used by running app services.
- Follow-up source/release subagent runs were unavailable because their usage
  limit was reached. The root agent completed the restored-clone read check
  and larger-model benchmark; no additional independent review is claimed.

## Recommended next decision — not implemented

- Do not select the larger classical NLI/QA combination: one of six positives
  is inadequate. The measured blocker persists across model size and exact
  page-window variants; the experiments do not demonstrate an extraction bug
  or a retrieval fix that would remove it.
- Evaluate a separate local instruction model as an independent, bounded
  relation checker. It would judge whether the cited source entails the claim,
  whether that claim answers the question, and whether other source statements
  contradict the same proposition. It must never generate a replacement answer
  or use a Gemini self-check. Server-issued source-unit IDs, exact source
  membership and current authorization remain mandatory; source instructions
  and model output remain untrusted. Unknown scope, malformed decisions and
  inference/resource failure must abstain.
- The experimental budget would remain 1 GiB artifacts, 2 GiB additional RSS,
  20-second startup and 5-second p95 complete verification. Preflight the public
  export, immutable revision/digests, license, CPU input/output contract and
  total artifact size before downloading or loading it. A single quantized
  candidate and at most three predeclared configurations would prevent another
  open-ended model search. No runtime dependencies, installed bundle, API
  contract, factory, policy snapshot, database or embedding representation
  would change during the experiment; no remote AI calls would be made.
- Freeze acceptance criteria before the probe: all six reviewed positives and
  all eleven maintained cases must pass across three repetitions, with no
  wrong-claim or unrelated-question acceptance. Add explicit same-proposition
  conflicts, different-proposition distractors, ambiguous relations, negation,
  altered numbers, mixed claims and document/prompt injection controls before
  considering release. The six private cases remain development diagnostics;
  an independent reviewed holdout and the real-query retrieval gate are still
  required. No universal accuracy guarantee follows from a finite corpus.
- This changes the proposed checker design, so it needs the owner's approval
  under their instruction to approve recommendations before changing the
  remediation plan. The larger classical-model approval alone has not been
  treated as authorization for this new design or for runtime activation.
