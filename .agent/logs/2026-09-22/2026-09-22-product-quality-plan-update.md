# Product quality remediation plan update

Date: 2026-09-22

## Scope and starting context

This is the documentation follow-up to the same-day read-only
[plan audit](2026-09-22-product-quality-plan-audit.md). Branch `main` remained at
`6c02d6c`. The existing untracked plan and 2026-09-21 investigation log, plus
pre-existing `ROADMAP.md` and log-index edits, were preserved. The audit read
current code, architecture, ADRs, tests, operational guides and relevant logs;
two bounded read-only follow-ups checked Gemini-only migration and Ask shutdown.

## Operator decisions applied

- Retire the current three-remote-call Ask path. The first implementation gate
  disables new Ask admission and answer execution while preserving Knowledge
  capture/indexing and private history reads. Ask stays disabled until an
  independently local semantic verifier and at most one query embedding plus
  one answer request per attempt meet the existing quality/safety gates. No
  automatic provider retry or three-call fallback is allowed. A local model is
  eligible only after resource, latency, license/commercial-use and quality
  review.
- Progress counts cards answered correctly at least once. Accuracy is correct
  attempts divided by all attempts, including timeout/no-answer. Attempted and
  mastery remain separate. Trophy and `Review Again` depend on 100% Progress.
- Same-Subject duplicate upload requires a choice. Cancel ends the whole job.
  An unchanged explicit revision is a no-op for revision/index/storage work.
  Reuse requires a ready compatible index and preserves private/published state
  and the document through later generation cancellation.
- New Flashcard, Ask and embedding work supports only verified native Gemini
  profiles. `openai_compatible` and custom endpoints are retired without
  deleting or reinterpreting historical jobs and embedding spaces.
- `gemini-embedding-001` remains the default; embedding-2 can stage and cut over
  with a short Ask maintenance window. Independent Study, duplicate, model
  preflight/catalog and embedding work may release before Ask reopens.
- Every explicit Ask manual Retry needs its own confirmation and cost disclosure;
  unknown prior spend is labeled unknown. Certain pre-provider infrastructure
  recovery needs no user confirmation.

## Documentation changed

- `docs/development/PRODUCT-QUALITY-REMEDIATION-PLAN.md`: records the operator
  decisions, replaces sequential phases with independent release lanes, makes
  Ask shutdown first, removes the three-call fallback, specifies attempt-level
  cost/request accounting, no-op revision and reuse semantics, Gemini-only
  legacy migration, staged model-2 cutover, new-ADR requirements, manual
  accessibility and per-lane release evidence. A final source review found that
  answer/index workers use one deployment-wide embedding profile; the plan now
  requires a consistent space across all Ask-enabled Subjects before reopening,
  with rollback or continued Ask shutdown after a partial cutover.
- `ROADMAP.md`: clarifies approved plan scope and that runtime Ask shutdown has
  not happened through this documentation update.
- `.agent/logs/README.md`: indexes this dated record.

## Verification and limits

This update changes plans and navigation only. It did not edit runtime code,
the real root `.env`, database data, provider settings, Compose containers or
deployment. No paid AI call, live provider evaluation, runtime suite or hosted
CI was run. `python scripts/check_context.py` passed with 37 required files,
68 active guides and 984 local links. `git diff --check` passed. These
documentation checks cannot prove future runtime behavior.
