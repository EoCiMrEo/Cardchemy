# Lane 6 source-first Ask recommendation

## Scope and current evidence

- This is a **proposal for owner decision**, not a changed Ask policy, plan
  checkbox, database schema or deployment. The retained local installation,
  root `.env`, published Knowledge and eight app services were preserved.
- The enabled two-request Ask policy has independent failure paths: one live
  answer request returned a provider 503; another current-image BLEU run
  retrieved relevant material and generated the expected concept but its short
  citation window omitted the subject and local support rejected it. The
  shipped verifier rejected all six owner-reviewed positive source/claim pairs.
  The user has confirmed eleven additional direct/paraphrase/follow-up source
  positives. A new owner review confirmed one explicit contradiction (N12) and
  one source-supported but question-irrelevant pair (U01); N01 and N11 lacked
  enough counter-evidence and are not valid contradiction labels.
- A real six-query Embedding 001 retrieval batch found the intended pages at
  ranks 2, 3, 1, 1, 3 and 1: recall@5 was 1.0, MRR 0.6944 below the maintained
  0.80 floor. The existing Related Knowledge fallback shows at most two pages,
  so it can hide two rank-3 targets. Page retrieval alone does not prove the
  displayed 480-character window contains the useful fact.
- The public 0.6B local relation candidate did not qualify a calibration rule.
  A separately approved Qwen3-4B diagnostic with seven hash-verified runtime
  files timed out at the 30-second startup bound before any validated case
  result. That is **not a semantic quality measurement** of Qwen or evidence
  that models are unrelated to the problem. It does show that this candidate
  did not satisfy the approved experimental startup envelope. No model policy
  was activated or private case sent to the experiment.

## Recommended product contract for an owner-approved plan change

1. Make `Related published Knowledge` the default Ask result under a new
   versioned `related_knowledge_v1` snapshot. The worker may issue at most one
   Gemini `QUESTION_ANSWERING` embedding request for the user question, with
   zero automatic provider retry, then run the existing Subject-authorized
   published/current-revision/active-space exact top-five retrieval. It makes
   **no answer-model call, no local verifier call and no lecture/history egress
   to an answer model** in this mode.
2. Display up to **three** exact source-contiguous excerpts, each at most 480
   characters, with document/page/section provenance and plain copy that says
   these are related course passages, **not a verified answer**. Three is a
   proposed cap to test, not a quality pass. Select displayed windows by a
   frozen, measured rule; never treat lexical overlap as entailment. If no
   useful authorized source qualifies, return a distinct no-match state,
   rather than an empty successful bundle or a fabricated answer.
3. Preserve durable admission/claim fencing, Subject ownership/enrollment,
   reviewed publication, active revision/index/embedding space, source expiry,
   quota/idempotency and history. Commit a terminal `related_knowledge`
   outcome and its current exact source-offset references atomically under the
   job claim and Knowledge write lock; reauthorize at commit and on every
   read. Hide the entire bundle on any permission, publication, revision,
   source, offset or expiry drift. Keep source text out of logs/duplicate
   persistence and escape it in the browser. Existing verified answers remain
   readable under their original snapshots. A future optional verified-answer
   action stays fenced until a separate quality/cost decision.
4. Add a numbered ADR superseding only ADR-021's fallback presentation
   decision and the affected portion of ADR-019. A new Alembic revision and
   typed API/UI contract must represent the new terminal outcome and up to
   three references; current constraints admit only `answer`/`abstained` and
   current excerpt reads are limited to failed/abstained jobs. Split capability
   admission and cost estimates from answer-model/local-support readiness.
   Browser disclosure must say this mode sends the **question** for one remote
   embedding, not the lecture/history for an answer. No change to root `.env`
   or existing policy snapshots is assumed in this proposal.

## Proposed evidence gate before turning on source-first

- Pre-register a source-window hit/usefulness evaluation on the eleven
  owner-reviewed positives and an independent direct/paraphrase/follow-up
  holdout. Judge the **displayed excerpt**, not just top-five page rank.
  Measure top-three hit, irrelevant-card rate, MRR/overlap, latency and one-call
  physical usage; compare with the maintained RAG corpus. Do not ship a
  three-card cap simply because two target pages currently rank third.
- Include N12's contradiction, U01's true-but-irrelevant pair, unsupported and
  ambiguous follow-ups, provider/embedding failures, prompt injection,
  malformed input, cross-Subject/unpublished/stale/replaced Knowledge and
  source-read drift. Require zero unauthorized/stale exposure, fabricated
  quote, unverified answer assertion or unsafe source rendering. Confirm
  cancellation, manual Retry cost disclosure and no automatic paid retry.
- Run targeted and full offline backend, disposable PostgreSQL migration/race/
  auth checks, deterministic journey, frontend `npm run check`, context and
  manual keyboard/spoken accessibility checks on the candidate. Recreate
  images and verify the local self-hosted cutover/rollback only after these
  gates. Keep the existing Answer-quality checklist open as an optional future
  mode; do not mark it passed because source browsing works.
- Generation remains independent: the adaptive 20-card case yielded 20
  machine-validated cards, and the exact smaller-target choice is implemented.
  All three published private lecture sources are long; none is a genuinely
  reviewed sparse whole document. A one-page offline subset is not that proof.
  Lane 6's final generation/release evidence remains open.

## Decision boundary

The owner previously chose sourced excerpts only, with no unverified AI prose.
Changing the **default** Ask architecture and Lane 6 success criteria is a new
decision beyond ADR-021's existing fallback. Present this concrete proposal
for approval before editing the plan/ADRs or runtime. No further public model
download, inference retry or Gemini request is implied.

## Current-source verification after the diagnostics

- Focused packet plus 4B candidate/calibration/downloader contracts passed
  **199 tests**, with one Windows symlink skip. `python scripts/check_context.py`
  passed 37 required files, 76 guides and 1,207 local links. A scoped
  `git diff --check` passed. These tests validate local harness/packet behavior,
  not Qwen semantic quality or the proposed source-first runtime.

## Owner decision

- On 2026-09-26 the owner explicitly approved updating the product-quality
  plan and a new ADR for this source-first design, **without runtime
  implementation or activation**. The prior recommendation remains evidence
  of the decision basis; the updated plan/ADR own the intended contract.
- The accepted [ADR-022](../../../docs/decisions/ADR-022-related-knowledge-primary-ask.md)
  resolves one design choice left open above: `related_knowledge` and
  `no_match` are **job-level** terminal result kinds with no assistant answer
  message. The new migration must relax completed-job/answer-identity checks
  only for those kinds; it need not add a fake `RagMessage.outcome`. The
  outbound embedding contains only the current question. A bounded local
  history-aware lexical strategy may be evaluated for follow-ups without
  sending prior chat to the provider; unresolved referents need no-match or
  clarification. This is still documentation only.

## Approved documentation update and final checks

- Updated `docs/development/PRODUCT-QUALITY-REMEDIATION-PLAN.md` for the
  source-first default, job-level related/no-match outcomes, atomic exact
  source references, one-embedding/zero-answer request cap, displayed-window
  evaluation and a separate optional verified-answer gate. Lane 6 remains
  **3 checked / 4 open**. No old quality failure was relabelled as a pass.
- Added `docs/decisions/ADR-022-related-knowledge-primary-ask.md`, narrow
  bidirectional supersession notes in ADR-019/021 and the ADR index. Updated
  `CURRENT-STATE.md`, `ROADMAP.md`, the system/Knowledge architecture context,
  `RAG_EVALUATION.md` and `TESTING.md` to distinguish the approved future
  direction from the currently running two-request/fallback behavior. The
  private packet review results and public startup timeout remain accurately
  bounded in the dated evidence.
- Final `python scripts/check_context.py` passed **37 required files, 77 active
  guides and 1,232 local links**. Scoped `git diff --check` passed. A direct
  Lane 6 count confirmed **3/7**. Focused harness/packet tests previously
  passed 199 with one Windows symlink skip; no runtime test was newly required
  by the documentation-only architecture decision. No Gemini/provider request,
  inference retry, DB write, migration, `.env` edit, volume change or runtime
  activation occurred for this approved plan/ADR update.
