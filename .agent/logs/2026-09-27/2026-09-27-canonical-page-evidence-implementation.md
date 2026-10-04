# Canonical-page evidence implementation

Date: 2026-09-27. In progress; no quality or release completion claim.

## Scope and starting context

The operator approved the canonical-page evidence recommendation and its
implementation, preserving source-only Ask and every existing budget/gate.
Starting checkout: main at `6c02d6c`, with extensive prior Lane 0–6 changes
preserved. Retained API/Ask worker run v5 with Ask disabled at schema `0023`.
Original/canonical review and a provider-free representation prototype are
recorded in the [recommendation](2026-09-27-canonical-heading-loss-recommendation.md).
The new independently reviewed PAGE gold is frozen before runtime selection;
private source/question/label artifacts remain in OS Temp.

## Approved changes

- Plan and ADR-022 now record v6 canonical-page units, explicit reference kind
  and kind-specific offsets, eligible chunk anchors and atomic authorized
  source reads. The historical same-chunk requirement is explicitly superseded.
- Independent bounded agents own selector/retriever, persistence/migration and
  contract review; the root owns worker integration, documentation and evidence.
- Inspected pages count inside the existing cumulative local budget. No
  indexing, provider spending, answer model or answer verifier is introduced.
- Subsequent source evaluation is delegated to independent agents; existing
  owner labels remain immutable and no additional owner review packet is needed.

Implementation, verification results, failures and cleanup will be appended
as they occur. No Lane 6 checkbox or Ask enablement changes follow from approval.

## Implemented source contract

- `source_sufficiency.py` and `knowledge_retrieval.py` snapshot v6. Production
  qualification requires an authorized canonical page and a unique literal
  chunk-body alignment plus owning section; missing/over-budget/unproven pages
  cannot fall back to a chunk primary. Exact section headings accept sentence
  case, and explicit numbered action sequences retain their entity title.
- Full inspected page text and admitted chunks share the existing cumulative
  inspection budget. SQL contains current principal, Subject, document,
  publication/readiness, revision and embedding-space predicates.
- `RagRelatedEvidence.source_kind` distinguishes historical chunk offsets from
  exact canonical-page offsets. Additive migration `0024` validates the current
  authorized source on insertion and refuses downgrade while page refs exist.
  No copied source text is persisted.
- Worker completion rereads the anchor and full page under the Knowledge lock,
  compares identity/content/section/slice, and atomically commits refs plus the
  terminal result. API bundle reads batch pages by corpus/space in groups of at
  most 100 anchors; drift hides the entire bundle. Page-open uses saved offsets,
  including when identical quote text appears more than once on a page.
- The display producer/scorer records kind-specific exact-source checks without
  falsely asserting page quotes are contained in indexed chunks. Account export
  includes the source kind needed to interpret offsets, with no duplicate quote.
- Current maps, Knowledge flow, database rollback guidance, evaluation guide,
  current state and changelog describe the approved implementation boundary.

## Verification and failures

- Full backend offline run: **1,697 passed, 124 skipped, 2 live deselected**.
  A later privacy-export correction and final focused read/scorer/worker checks
  passed **154 tests**; the full-run count does not include later test additions.
- Full guarded PostgreSQL run: **107 passed, 3 skipped, 1,716 deselected**.
  `0024` upgrade/head/drift, empty downgrade to base, re-upgrade and second drift
  checks passed. Maintained retrieval ablations retained their thresholds.
- Both deterministic browser journeys (RAG on and off) passed, including
  source-only references/page opening. The current backend image built and
  passed its isolated native/runtime smoke. Disposable resources were removed.
- The first PostgreSQL attempt was blocked by Docker sandbox permissions before
  service work. The first authorized run exposed an incomplete synthetic job
  provider-boundary timestamp and missing per-test cleanup. Those caused two
  direct failures and six later quota/queue failures. Corrected fixtures record
  the boundary and remove only their own users/dependents; the next full run
  passed. This was test isolation repair, not a relaxed application constraint.
- Context validation passed: 37 required files, 77 guides, 1,293 local links.
  Normal repository `git diff --check` passed with line-ending notices only.

## Frozen private diagnostic: source recall still fails

After the public corrections and current v6 image build, a single provider-free
diagnostic froze runtime/source/harness hashes before inspecting the twelve
independent positives and sixteen insufficient controls. It reauthorized the
current thirteen published canonical pages and their anchors in read-only SQL
before and after measurement; all hashes, scope and revision checks matched.
Each case was deliberately supplied its reviewed page anchor, with no vector
search or neighbor source supplied. Therefore this measures isolated source
qualification conditional on a correct anchor, not end-to-end retrieval,
display/page-open quality or a release pass.

Only **1/12 positives** produced a selection; **0/16 control cases** selected
a span. The selected positive window differs from the original reviewed span
and is undergoing independent review. A control with no selection is not a
complete paired quality pass when its sufficient control is missed. Maximum
examined context was **319 estimated tokens**, well below the existing ceiling.

An unchanged-runtime static diagnostic classified the eleven missed positives:
**3 unknown question intents, 1 unresolved follow-up, 7 source-relation
qualification failures**. All twelve had proven canonical anchor ownership;
none failed source alignment or the inspection budget. The seven qualification
failures had candidate units but no match for the authored relation-cue patterns.
This exposes another selector coverage defect after recovering heading access.
It does not establish model quality or corpus-wide absence of evidence.

Original labels and measured output remain immutable in owner-private OS Temp.
An independent reviewer is checking the actual selected window and original
sources; no additional owner review packet is requested. No private text,
questions, IDs or source paths appear in this log. No provider call, retained DB
write, reindex, root setting change or data reset occurred. The diagnostic
container was removed after copying its private result. The retained runtime
is still v5/schema `0023` with Ask disabled; the diagnostic ran the new v6 image.
Lane 6 remains **3/7**, and no quality/release checkbox is closed.

## Independent review completed

The independent evaluator subsequently rendered and inspected all thirteen
original PDF pages without reading selector source or rerunning qualification.
All twelve original positive windows remain sufficient, source-faithful and
useful; all sixteen controls remain insufficient. The one actual selected
window is sufficient and exact at its canonical offsets, also verified against
the original PDF. The eleven missed forms are five heading-owned bullet/list
structures, four examples/explicit interpretations, one parenthetical expansion
inside a multi-entity list and one cause/consequence across labeled blocks.

All twenty-eight reviewed original windows fit 480 characters and match their
original extraction offsets; twenty are byte-identical to the canonical text
and all twenty-eight match after whitespace normalization. The actual selected
window is byte-identical to the canonical page. Source review cannot replace
the still-missing retrieval, visible-window and current-page integration gates.
The follow-up [structural recommendation](2026-09-27-structural-source-qualification-recommendation.md)
was awaiting the operator's required plan/ADR approval at that point; the
subsequent explicit approval is recorded in the linked recommendation.

## Final privacy-export verification

The focused disposable canonical-reference suite passed **4/4**, including
own-account export of source kind and exact offsets without copied source text.
The initial export assertion reused an already active transaction, contrary
to the export helper's fresh-snapshot contract; the test now opens a fresh
session. No application transaction rule was relaxed. Migration head/drift,
empty downgrade/re-upgrade checks and disposable cleanup passed again.
The earlier image build/smoke preceded the final export allowlist addition;
the 154 focused backend tests and this PostgreSQL run cover that final source
change. A future runtime deployment must rebuild the image from current code.
