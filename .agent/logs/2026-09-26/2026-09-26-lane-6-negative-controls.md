# Lane 6 Ask negative-control coverage

## Scope and starting context

- The private review packet supplied eleven owner-reviewed feasible
  source/question/claim pairs but did not execute unavailable-provider,
  malformed-output, unpublished or cross-Subject controls. Its N01 quote was
  judged insufficient to refute the wrong claim, so it is not a validated
  contradiction label.
- This pass audited existing backend contracts and added only missing
  deterministic controls. It did not select a new Ask policy, read private
  Knowledge, call a provider, mutate the retained database or change plan
  checkboxes.

## Changes and checks

- Added worker tests proving that malformed/unfinished model output and answer
  transport failure can retain only bounded source references for the separate
  Related published Knowledge path; empty retrieval and a successful verified
  answer do not retain that fallback state.
- Added a guarded PostgreSQL test with a student enrolled in two published
  Subjects: a read for one Subject cannot return the other Subject's source,
  even when both chunk IDs are supplied. Existing tests cover unpublished Ask
  admission, unpublish/unenroll redaction, unauthorized private threads,
  unsupported/contradictory local support, invalid citations and provider
  unavailable/timeout handling. These synthetic controls do not substitute
  for the missing independently reviewed private negatives.
- Affected worker matrix: **15 passed**. Related/local-support/v2 contracts:
  **58 passed, 4 skipped**. Guarded disposable PostgreSQL suite: **101 passed,
  3 skipped**, including migration/head/drift/downgrade/re-upgrade checks;
  disposable cleanup confirmed. No live provider test was run.

## Open gate

- The user chose a source-only, clearly labelled Related published Knowledge
  display when no answer can be verified. ADR-021 currently defines this as a
  fallback browsing aid, so source-first presentation requires a separately
  approved plan/ADR/runtime-policy change and fresh quality evidence. The
  negative tests above establish boundaries, not approval for that change.
