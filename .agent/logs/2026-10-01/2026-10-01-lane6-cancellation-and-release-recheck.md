# Lane 6 cancellation boundary and offline release recheck

Date: 2026-10-01 (America/Chicago).

## Scope and preservation

Continued authorized Lane 6 implementation and verification while the
[release-metric recommendation](2026-10-01-source-navigation-release-metric-alignment-recommendation.md)
awaits a specific decision. No metric, prompt, source label, frozen public
receipt, consumed provider ledger or Ask policy was changed. Ask remains off;
Lane 6 remains 3/7. No provider call or private corpus review occurred here.

Starting checkout: `main`, HEAD
`6c02d6cf063acf83f4da5c08cfc4a3aa2c94be57`, with substantial pre-existing tracked
and untracked work preserved. Root `.env`, retained database, populated volumes,
original PDFs and ignored backups were not modified. Service inspection found
all eight retained containers healthy; this is health evidence, not a deployed
quality or schema check.

## Independent finding and fix

An independent bounded audit found a worker exception-boundary gap: cancellation
or lease loss after `insufficient_grounded_cards` but before the real encrypted
staging transaction escaped the shortfall handler. Cancellation would wait for
lease recovery instead of performing immediate cleanup.

`backend/app/workers/generation.py` now handles cancellation through the existing
fenced cleanup and treats lease loss as a safe finalizer stop. The change adds
no retry or provider execution. `backend/tests/test_generation_card_choice.py`
reproduces durable cancellation, expired lease and replaced claim at that
transaction boundary. All three regressions failed before the four-line fix
and passed afterward. Cancellation leaves no source, candidate stage or set;
stale workers preserve the current authority and cannot stage or commit cards.
The pipeline runs once and is not requeued. A separate static review cleared
the patch; the root inspected the actual exception handler and regression.

The audit also verified existing extracted-PDF-to-pending-choice coverage,
exact smaller-count confirmation without another provider call, concurrent
confirmation tests, and PDF bundle reauthorization/stale-source rejection.
These contracts do not prove real lecture card yield or reference usefulness.

## Verification

- Fresh focused generation tests: **35 passed**, 27.71 seconds. Scoped
  whitespace validation passed.
- Backend offline suite started before the repair: **3,144 passed, 151 skipped,
  two live tests deselected**, 298.67 seconds. Treat this as pre-fix/overlapping
  evidence. A separate complete **post-fix** offline run passed **3,147 tests**,
  with 151 skipped and two live tests deselected, in 327.87 seconds.
- Full frontend `npm run check`: **passed**. Typechecks, lint, six Node tests,
  65 component tests, coverage, production build and **83 Chromium tests**
  passed; one separate opt-in live password-reset browser case was skipped.
  Coverage: 96.66% statements, 85.71% branches, 93.22% functions, 97.84% lines.
  Original-PDF tests rendered real synthetic PDF bytes through authenticated
  ranges, including distant cross-reference tables, page navigation, revocation,
  malformed/missing originals and close/reopen during text streaming. The
  expected injected-error console messages came from negative tests.
- Disposable PostgreSQL harness: **131 passed, three skipped, 3,166 deselected**,
  176.07 seconds. Current-head/drift, empty-schema downgrade to base and
  re-upgrade passed. The harness removed its owned containers and generated
  credential file; retained data was not migrated or downgraded. The synthetic
  retrieval ablation is not private/source usefulness evidence.
- Deterministic real-application journey: **rag-off and rag-on passed**, including
  generation, independent Knowledge publication, source-only page references,
  enrollment, email and study progress. Both disposable runs reported cleanup
  of their processes, containers, data, fixture and generated credentials.
- Retained API non-secret switch verification: `ask_enabled=false` and
  `source_judge_enabled=false`. No credential value was printed.
- The host-managed browser failed to initialize twice, including after reset:
  `failed to write kernel assets` / missing path. No retained browser action
  occurred. The maintained Chromium suite is the available deterministic
  browser verification; it does not refresh the earlier retained PDF smoke.
- Repository context and scoped whitespace checks passed. Hosted CI, a
  packaged-image cutover and manual spoken assistive-technology checks were
  not performed in this repair/recheck.

## Remaining boundaries

The public visual run still stopped after four valid calls, with 4/5 useful
displayed cards and an unreachable exact-two-set gate. It is not a 90% quality
pass. The pending gate amendment is not authorized by generic continuation;
the existing scorer and one-use ledgers remain unchanged. Different-PDF
holdout, private measured selection, a deployable successor policy, original
page opening and spoken assistive-technology/release evidence remain separate.
No runtime recreation, Ask enablement or provider replay is performed here.

The dormant runtime remains the older v4/text-only/Gemini 3.8 contract; the
visual public prototype uses a different wire/model and cannot be enabled
through a flag change. A future measured pass still needs an immutable
successor runtime policy, matching request and disclosure, migration/access
proof and independent deployed page-usefulness measurements. The earlier
[runtime-gap audit](../2026-09-30/2026-09-30-lane6-pdf-browser-and-v2-runtime-gap.md)
explains the version boundary; source inspection confirms it still applies.
