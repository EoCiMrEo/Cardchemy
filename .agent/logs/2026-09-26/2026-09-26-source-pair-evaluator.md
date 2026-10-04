# Provider-free source-pair evaluator

## Scope and starting context

Owner-approved source-only v3 covers eight relation families and requires at
least sixteen owner-reviewed insufficient question/source pairs, two per
family, with sufficient controls. Ask remains disabled behind independent
quality/access/release gates. This work owns only the new diagnostic harness,
synthetic tests and supporting evaluation/module-map evidence. Existing shared
changes were preserved; no application policy, database, root environment or
provider configuration was changed.

## Implementation

- `scripts/evaluate_private_source_sufficiency.py` defaults to a no-database,
  no-provider preflight. Explicit execution reads only private OS Temp inputs.
- Frozen controls require reviewed fidelity/sufficiency/page labels, exact
  candidate-record binding, candidate/controls digests and both runtime and
  evaluator-source fingerprints before a DB reader is constructed.
- At most 64 pairs, at least sixteen distinct insufficient spans/two per eight
  families, at most 480 characters per span, 512 KiB per input and 120 seconds
  per audit. Explicit profile contains only a local database URL; values are
  not emitted. Root `.env` is not read by this process.
- SQL reads use read-only repeatable-read transactions with bounded statement
  timeout and current instructor-owner, Subject, selected-document,
  publication/readiness, content/index/corpus revision and embedding-space
  authorization. Canonical page keys include owner and Subject. A second
  independently authorized read rejects drift.
- Exact chunk/page hashes and offset-to-page alignment are checked. The local
  selector sees only the reviewed span, without surrounding body/section hints.
  A sufficient parent-window review does not transfer to a cropped subspan;
  cropped selection is unknown. Any selected subspan of an insufficient window
  counts as a false-primary failure.
- Safe output contains per-family aggregate counts and code fingerprints;
  private questions, content, source identifiers, configuration and raw errors
  are omitted. Unknown cannot count as pass; an empty selector cannot pass
  because sufficient controls must qualify. Release gate always remains false.

## Verification and limits

- Focused evaluator and packet-converter suite: **63 passed** after mandatory
  candidate-manifest/evaluator-fingerprint binding (2026-09-26).
- Earlier safety suite: 27 passed; expanded exact-window/reader guards: 32
  passed. One test-fixture-only failure after schema strengthening was repaired
  (the helper accessed a deliberately removed sufficient-source key before the
  harness could refuse it). No runtime product failure was inferred.
- Synthetic checks cover default zero DB/provider work, incomplete families,
  unreviewed/unknown labels, digest/fingerprint/manifest mismatches, duplicate
  spans, current source/page/offset/revision/space drift, second-read drift,
  non-owner and stale-corpus refusal before source lookup, false-primary and
  empty-selector failures, exact positive-vs-cropped window semantics, and safe
  failure output.
- No private audit was executed, no provider request or DB write was made,
  and no temporary private packet or infrastructure resource was created.
- The paired source check is distinct from paid query retrieval, actual
  displayed-window/page-route review, access testing, manual accessibility and
  release. It cannot infer a whole page or corpus lacks an answer.

## Documentation and cleanup

Updated `docs/RAG_EVALUATION.md`, `backend/MOC.md` and the dated log index.
No diagnostic resources require cleanup. Parent agent owns complete suite,
PostgreSQL integration, plan/ADR status and final aggregate evidence.
