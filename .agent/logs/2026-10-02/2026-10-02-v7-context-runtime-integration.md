# Dormant v7 admission-context integration

## Authority and preservation

Standing operator authority covers aligned Lane 6 implementation/context
updates. Provider/private-transfer and release gates remain separate. Dirty
`main` at `6c02d6c`, populated data, root `.env`, exact PDFs, ignored backups
and all historical used migrations/trial files are preserved. Retained v6
still uses head `0031`; this record describes checkout/disposable checks.

## Implemented contract

Required checkout policy is `related_knowledge_navigation_v7` with
`visual_source_id_v3`. Admission captures the current question and, only for
an unresolved follow-up, the strictly preceding user message under the thread
lock. Additive `20261002_0032` stores metadata, hashes, timestamps and literal
offsets instead of copied history. Deferred admission and immutable database
guards keep job/context binding atomic. Historical policies stay separate.

The sole embedding input remains the raw current question. Local retrieval can
use a unique literal subject of at most 160 characters/twelve words. Only that
exact subject may accompany an unresolved question to the source judge, with
explicit referent purpose and untrusted-input treatment. No full preceding
question, assistant answer or history is transmitted. Ambiguous, expired,
deleted or changed context fails safely or requests clarification.

The worker rechecks admission identity before expensive work, after rendering,
after provider quota waits immediately before HTTP, and inside atomic reference
completion. It also rechecks grants/session/corpus/space/exact cues/PDF archive
bindings. The adapter uses a per-invocation callback, avoiding shared mutable
job context. One HIGH-thinking source-ID judgment permits at most 120 seconds
inside the finite whole-job budget, with no answer/verifier or automatic retry.

Typed API/UI capability and disclosure identify literal-subject transfer before
admission or manual retry; a changed capability cancels pending operations.
Template/Compose defaults permit 120 seconds; real `.env` is unchanged.

## Verification so far

- Full frontend check passed types/lint, six Node tests, 83 component tests
  with coverage, build and **84 Chromium passes**. One opt-in live reset skipped.
- Bundle: initial JS gzip **123,452/130,000**, total **756,471/780,000**,
  largest raw **1,265,413/1,350,000** bytes, all passed.
- Current targeted admission/model/migration offline suite: **84/84 passed**.
- Disposable migration head/drift/downgrade-to-base/re-upgrade passed,
  including twenty-six new context PostgreSQL cases.
- Full PostgreSQL: **177 passed/10 failed/3 skipped**. Full offline:
  **4,206 passed/51 failed/207 skipped/2 deselected**. Failures after current
  policy changes are under investigation; neither full suite is passing yet.

Independent agents own bounded fixture/contract alignment and distinguish real
defects from stale policy expectations. Provider/private judge, retained
migration and Ask activation did not occur. Journey, candidate image/security,
independent display quality and spoken assistive-technology checks remain.
Lane 6 remains **3/7**, Ask disabled.
