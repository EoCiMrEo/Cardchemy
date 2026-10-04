# Lane 6 source-structure v4 validation

Date: 2026-09-27. Status: implementation validated offline/disposably;
independent private quality and release gates remain open. Ask stays disabled.

## Scope and starting context

The owner approved the Lane 6/ADR-022 amendment for exact, same-chunk slide
title plus bullet qualification across all eight source-relation families and
an owner-private authored discovery input for previously unexposed lecture
pages. This work started on `main` at `6c02d6c` with existing Lane 0–6
changes in the shared working tree. Those edits, the retained root `.env`,
Knowledge and volumes were preserved. At the start, the retained containers
predated this selector revision; API/Ask worker were subsequently recreated
from the verified v4 image with Ask still disabled. No live provider request,
reindex, volume reset or Knowledge-content mutation was made for v4.

## Implementation and review

- Lane 6 and ADR-022 now record the approved v4 scope and unchanged quality
  gate. `hybrid_source_sufficiency_v4` binds queued retrieval snapshots;
  `source_relation_units_v4` identifies local selection and safe aggregate
  telemetry. Historical v3 rationale remains intact.
- The selector admits only a contiguous literal title and an owned assertion
  in the same canonical chunk, at most 480 characters. It checks the requested
  relation, entity, qualifiers and explicit body predicate. A process may use
  two numbered owned actions. Other relations do not combine sibling bullets.
  Topic descriptions, another subject's predicate, ambiguous paired titles,
  acronym descriptions without expansion, generic definitions, and unsupported
  measurement contrasts remain unqualified.
- Independent read-only code review reproduced false-primary cases for a
  causal clause about another action, a two-metric title, an entity mentioned
  only as a title object, and an entity-free property with no named metric.
  Each was corrected with a public synthetic negative and corresponding
  positive control. These authored rules select navigation candidates; they
  are not a semantic entailment model or private-course quality evidence.
- The bounded authored review input is validated and stored only in OS Temp.
  Matches remain unreviewed; source fidelity, exact excerpt sufficiency and
  original-PDF-page usefulness require separate owner labels before a gold
  roster or quality result can be claimed.

## Verification and limits

- Focused selector tests passed **104/104** after the final source-ownership
  correction; the packet-builder and private-evaluator focused suite passed
  **80/80** after the authored-ID/roster correction. Earlier focused counts
  are development history, not separate release evidence.
- The final backend offline suite passed **1,595**, with **122 skipped** and
  **2 explicitly live cases deselected**, after the selector and packet-ID
  corrections. This verifies code contracts, not private-source usefulness.
- The first disposable PostgreSQL command could not access the Docker named
  pipe from the restricted sandbox. Docker was available under the approved
  elevated command. The documented disposable run then passed **102 tests**,
  **3 skipped**, **1,614 deselected**, including Alembic head/drift and
  empty-schema downgrade-to-base/re-upgrade at `20260926_0023`. Its owned
  database, container and generated credential file were cleaned.
- Both deterministic offline `rag-on` and `rag-off` browser/database journeys
  passed on the current checkout. Their owned processes, containers, data,
  fixtures and credentials were cleaned. They do not establish private
  displayed-window quality or a paid-provider result.
- `scripts/check_context.py` passed (37 required files, 77 guides, 1,284
  links); `scripts/check_ci.py` and `git diff --check` passed. The shared
  backend image tag was rebuilt from v4 and `scripts/check_images.py backend`
  passed its isolated no-network/no-secret runtime smoke. A separate isolated
  file inspection confirmed both v4 policy identifiers in the built image;
  direct module import without configuration was unavailable because required
  installation keys were intentionally absent. After private diagnostic
  reads completed, API and Ask worker were recreated on v4 and frontend was
  started; all three passed Compose health checks. Runtime reads confirmed
  both v4 policy IDs and both raw/effective Ask gates false. Generation/index
  workers were not started by this step; no paid comparison is claimed.

## Owner-private discovery and labels

The bounded authored input yielded **12 unreviewed positive candidates** on
12 previously unexposed pages in three published documents, four each of
direct/paraphrase/follow-up questions, and **14 proposed insufficient pairs**.
All eight source relations were represented, but mechanism and process each
lacked a second pair. Discovery used the current authorized corpus read-only,
with zero provider requests or DB writes. Temporary PDF renderings and
container scratch files were cleaned; the review packet remains in OS Temp.

The owner then reviewed the packet: **7/12 positive excerpts** and **9/12
positive pages** were useful. Of the 14 proposed insufficient pairs, **12
excerpts** were labeled insufficient and **2 excerpts** useful, so the latter
cannot serve as negative controls. The owner confirmed file/page identity for
all 26 candidates. Five of the 12 excerpt-insufficient pairs are bound to
positive candidates that the owner also found excerpt-insufficient; thus at
most seven pairs currently have both a useful positive control and an
insufficient comparator. These are candidate labels, not a 12-positive gold
roster, a complete 16-pair set, or an actual Ask displayed-window score. Keep any development
tuning on these results separate from a new page-disjoint holdout.
The content-free owner decisions were copied to an OS-Temp development-label
file bound to the candidate-roster file hash; its case IDs and count were
checked against the frozen roster. No source text entered this log or tracked
fixtures.

A provider-free development diagnostic then passed each of the 26 reviewed
exact excerpts to the current selector as a synthetic single chunk. It
selected **2/9 owner-Yes excerpts** and **0/17 owner-No excerpts**. One of the
two selections cropped the owner-reviewed window, so even that selection has
no independent displayed-span label. The seven Yes misses include absent
lexical qualifiers, a missing explicit entity in the chosen span, one unknown
question relation, and useful wording without the selector's verb cue. This
initial diagnostic did not test full canonical chunks, retrieval rank,
neighbor pages, actual Ask output or page opening. A subsequent read-only
two-snapshot probe on a separate current-v4 backend container supplied each
full canonical chunk. It produced the same 2/9 useful-case selections;
same-chunk context did not recover the misses. Only one selected span exactly
matched its owner-reviewed excerpt. Selection on a source with an excerpt-No
label remained zero, but that is not a whole-page semantic label. The owned
diagnostic container and retained-container scratch were removed after the
private artifacts were preserved in OS Temp. The first attempt on the earlier
retained container could not import the new neighbor contract; it was stopped
before DB access and rerun on the current image rather than adapting stale code.
The candidate packet is development data; the next independent holdout must
use different, previously unexposed pages.

Two subagent tasks stopped on a reported account usage limit. Their partial
private discovery artifacts were inspected and recovered rather than treated
as finished work. A recovered broader source-unit scan offered twelve primary
and six reserve candidates. Each of the **18 exact spans on 18 distinct new
pages** was reauthorized and checked against current chunk/page hashes twice;
all **48 previously exposed/seed pages** were excluded. A separate versioned
context-candidate packet was frozen before runtime evaluation, with unique
X70–X87 IDs, source-artifact/exclusion fingerprints and every label unreviewed.
It remains owner-private in OS Temp and was sent for owner review. It is not
compatible gold merely by existing, and has no insufficient-pair or Ask score.

## Scoring registration correction

The aggregate scorer retains its original T01–T12 fixture and thresholds but
now offers opt-in private X-ID registration. It requires twelve independently
owner-approved exact-source candidates, matching question/page/history probe
roster, 4/4/4 groups, twelve pages in two or more documents, current runtime and
scorer fingerprints, and unchanged threshold digest before measurement. It
checks bound prior gold/alternative/development artifact bytes and rejects
reused pages. Pattern-derived seed IDs are absent from the discovery manifest,
so that limitation is explicit and measured seed/holdout disjointness remains
a separate check. **97 focused scorer/packet/display tests** passed after the
review correction. No actual private roster registration or score was run:
the first source set was incomplete and the context packet is unreviewed.

## Remaining gate

An independently reviewed twelve-positive/four-per-group holdout and sixteen
paired insufficient cases are still missing. The exact displayed windows and
page opens have not met their private gate; maintained retrieval, access and
spoken assistive-technology release checks have not been closed for v4. No
Lane 6 checkbox was changed on the strength of these tests. Ask remains off;
no answer-model or verifier path is restored.

## Subsequent operator labels and evaluation delegation

The owner reviewed X70–X87: **8/18 exact excerpts** and **10/18 original
pages** were useful. Source fidelity was not supplied by the owner for this
packet. A separate agent inspected original PDFs without reading the runtime
selector: **18/18 normalized exact spans and excerpt hashes matched**, and
its eight sufficient/ten insufficient judgments agreed with the owner. A
useful page did not repair the two insufficient exact excerpts on useful pages.
The owner then explicitly delegated all subsequent source evaluations to the
agents and requested no more review packets. Plan/ADR/evaluation guidance now
record that instruction, retaining owner labels and all existing thresholds.
This delegation does not convert a discovery score into an independent label.

## Narrow v5 intent correction

The first packet's development diagnostic exposed unrecognized definition and
application interrogative forms. The same eight-family parser now recognizes
those request forms and separates intent scaffolding from factual qualifiers.
The change snapshots `source_relation_units_v5` and
`hybrid_source_sufficiency_v5`, retaining entity, source-ownership, polarity,
numeric/context qualifiers, exact-source and resource guards. Coordinated
interrogatives remain ambiguous. Four paired public controls cover the new
forms and an application-domain mismatch; stale v4 snapshots remain fenced.
The focused selector/source-only/observability run passed **136 tests**.
One earlier targeted run failed only the stale v4 identifier assertion, which
was corrected before the passing run. No paid calls or DB writes occurred.
At this checkpoint the running local API/Ask worker still use v4; Ask remains
disabled. Full v5 validation and image recreation are separate subsequent
steps, and no v5 private-quality measurement is claimed here.

## Final v5 checks and retained runtime

Independent code review found that family-wide intent stopwords could remove
meaningful suffix qualifiers. The final parser removes only the matched
interrogative prefix/auxiliary positions; repeated words in factual suffixes
remain required. Six public regression controls reproduce the distinction.
The final focused selector/source-only/telemetry run passed **142 tests**.
The broader offline run begun before those six new controls completed with
**1,609 passed, 122 skipped, 2 live deselected**; its count does not include the
six subsequently added controls. Disposable PostgreSQL passed **102**, with
**3 skipped and 1,634 deselected**, and verified head/drift/downgrade/re-upgrade
at `0023`; its owned resources were cleaned.

The current v5 image built and passed the isolated runtime smoke. The optional
development bind mount failed in Docker Desktop, so the documented built
reference stack was recreated instead. API and Ask worker are healthy, both
report v5 and raw/effective Ask disabled. One initial boolean inspection used
an incorrect Settings property name; the corrected allowlisted read passed.
No root settings, data, volume, embedding space or indexed representation
changed. The source-only worker makes no paid request while Ask is off.

The read-only v5 development probe still selected **2/9** useful sources and
**0/17** rejected sources; one selected span remains unreviewed. Correct intent
parsing alone did not recover private source recall. Subsequent independent
original/canonical review isolated the heading omission described in the
[separate recommendation](2026-09-27-canonical-heading-loss-recommendation.md).
The new twelve-positive/sixteen-insufficient original-source set has not been
used to tune or measure runtime source selection.
