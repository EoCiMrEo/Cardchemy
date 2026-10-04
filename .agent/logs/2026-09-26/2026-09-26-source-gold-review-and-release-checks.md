# Lane 6 source gold review and release checks

## Scope and decisions

Continue the operator-approved source-only Ask implementation and measured
Lane 6 gate. Preserve the extensive existing main working tree at
`6c02d6cf063acf83f4da5c08cfc4a3aa2c94be57`, root configuration and current
private corpus. Development reset remains authorized but deferred while that
corpus is needed for measurement. No new provider request is authorized by
this record or by a configured key.

Read root guidance, canonical maps, ADR-022, the active plan, current-state and
relevant dated evidence. Independent subagents audited source-only runtime,
gold selection, guarded transport, and documentation/security consumers.

## Independent holdout review

The owner reviewed all twelve proposed candidate gold pairs:

- T01–T05: No; T06–T08: Yes; T09–T10: No; T11: Yes; T12: No.
- **4 Yes, 8 No.** Original roster is unchanged; labels are recorded in a
  separate owner-private Temp manifest bound to its original SHA.
- These are source-discovery labels, not runtime retrieval/display outcomes.
  A No does not establish corpus absence, a negative question, model failure
  or a retrieval miss. No thresholds or question meanings were changed.

Read-only audit and public synthetic replay found the gold helper minimized
the length of a regex co-occurrence. Bare headings and incomplete acronym
expansions could qualify; greedy page uniqueness did not prove usefulness.
This is a discovery defect independent of the earlier model/verifier failure.

`scripts/refine_private_source_holdout.py` now offers at most two exact
source-context alternatives per rejected case, preserves fixed questions,
previous turns and v1 labels, rejects source/page hash drift, keeps all six
seed source identities available before exclusion, and assigns no new labels.
Targets remain at most 480 characters; adjacent canonical page context is
bounded to 1,200 characters. The owner labels passage and page usefulness
separately. This preparation uses no runtime ranking or provider call.

The generated private packet has thirteen unreviewed alternatives across all
eight rejected cases. Its escaped static HTML and private manifest were copied
to a fresh owner-only host Temp directory and opened for owner review. Four
previously approved candidate pairs remain unchanged. Candidate pages may
overlap; the final frozen holdout still must satisfy the twelve-distinct-page
and seed-disjointness gate, rather than counting alternatives as passes.

Initial preparation attempts failed before corpus reads: copied file ownership
and the diagnostic mount's required TMPDIR/writability were not aligned.
The final one-off local preparation ran under the existing mount owner;
application processes remain UID 10001. Closed failure-stage codes were added;
no raw exceptions/private excerpts enter stdout. No DB writes occurred.

Default preflight for both gold tools now lazily imports application/readers
only during explicit creation. Tests enforce no settings/database import on
default execution, exact bounded slices, escaping, source drift rejection and
unchanged labels. Discovery tests do not claim semantic relevance.

## Guarded displayed-window producer

`scripts/evaluate_private_source_display.py` now has a native SDK binding and
an explicitly guarded CLI. Frozen reviewed roster, runtime/profile SHA,
endpoint/model/task, request/token/time/cost envelope, fresh process approval
and a single-use marker precede reader/provider construction. It reads only
authorized current sources in read-only PostgreSQL transactions and uses the
actual runtime follow-up/selector code. It sends only the current question,
one physical embedding per resolved case, SDK/application retries zero,
preserving the existing rate governor. Root .env is not loaded by execution.

The producer keeps owner window relevance and actual saved-job page-route/
browser opening **pending**, with release false. Direct canonical-page reads
cannot establish that the application's page link was opened. Its thirty-two
tests plus thirteen scorer tests passed using injected readers/HTTP mocks;
no actual provider or operator DB execution occurred.

## Security findings and remediation

The first three-image/secret gate failed on five synthetic generic-key
matches and OCR package `libexpat 2.8.4-r0`, HIGH `CVE-2026-93990`.
Standard backend/frontend and worktree-secret gates passed that run.

Four offending test values were idempotency identifiers, replaced by generated
UUID strings without changing test semantics. The remaining value was the
public tokenizer artifact SHA in the calibration log. Its metadata label was
editorially clarified; the exact hash and historical result are unchanged.
Scanner configuration/ignores/severity thresholds were not relaxed.

OCR was rebuilt without cached APK layers and installed `libexpat 2.8.5-r0`.
The [upstream 2.8.5 change log](https://github.com/libexpat/libexpat/blob/R_2_8_5/expat/Changes)
confirms the fix for malformed UTF-16 handling in CVE-2026-93990. This is a
system-package rebuild, not a Python lock or application behavior change.
Exact rescans and smoke results are appended below when available.

## Evidence limits and cleanup

Full backend offline: **1,406 passed, 118 skipped, 2 live deselected**.
Frontend: 4 unit, 46 component, 68 Chromium passed; 1 live reset skipped.
PostgreSQL: 98 passed, 3 skipped, including source stage-parent guard and
head/drift/downgrade/re-upgrade. Retained local stack was migrated to verified
0023 after private backup/disposable restore and remains healthy with Ask off.

No live embedding/answer/verifier call, private window-quality score, spoken
screen-reader approval, sparse whole-source proof, data reset, hosted CI or
publication is claimed. Lane 6 remains **3/7**. Temporary diagnostic resources
are removed only after their private review files have been copied successfully.

## Subsequent owner review and final checks

- All thirteen proposed alternatives were reviewed **Excerpt: No / Page: No**.
  The owner confirmed correct file/page identity but content that did not help
  investigate the question. Labels are bound to the unchanged private manifest;
  no rejected pair was overwritten or counted as a negative whole question.
  The four earlier Yes cases remain usefulness labels, not complete-evidence
  labels. This reviewed set becomes development data if used to tune a selector.
- Final local security metadata reports `failed_gates=[]` for the standard
  backend, OCR backend and frontend, together with secret gates. The patched
  OCR image also passed its network-free runtime smoke. Five synthetic test
  idempotency values in total were replaced with generated UUID strings; the
  earlier four-value summary above omitted one legacy choice test corrected
  after the second scan. Public tokenizer digest metadata remains unchanged
  apart from its clarified label. No scanner ignore or threshold was relaxed.
- The latest deterministic source-only RAG-on journey passed after migration
  0023 and the canonical-page highlighting changes. It exercised two searches,
  exact current-page opening, no-match, private history and cross-Subject
  rejection with an offline provider. An initial host-interpreter attempt lacked
  Alembic and cleaned up; the corrected backend-venv run passed. The earlier
  RAG-off journey remains scoped to its earlier source revision.
- Nine exact owned source-holdout diagnostic containers and their unused,
  labelled temporary volume were removed after private review files had been
  copied. A subsequent read-only Docker check found none and confirmed all six
  application processes healthy. Application volumes, private host review files
  and the verified backup remain intact. The first sandboxed verification was
  denied Docker-pipe/config access; authorized read-only escalation succeeded.
- The operator requested evidence-sufficiency retrieval and reaffirmed
  source-only output. The concrete ordered proposal and primary research
  references are in the [new recommendation](2026-09-26-evidence-sufficiency-recommendation.md).
  Plan/ADR expansion remains pending approval; no new runtime selector, model,
  paid request, reindex or release activation is claimed.
