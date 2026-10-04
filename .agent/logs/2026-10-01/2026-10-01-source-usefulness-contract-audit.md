# Source usefulness contract: post-stop audit

Date: 2026-10-01 (America/Chicago). Read-only investigation following the
[transport v2 quality stop](2026-10-01-high-thinking-transport-v2-quality-stop.md).
This record does not change frozen labels, thresholds, consumed approvals,
runtime policy or the Lane 6 checklist. Ask remains disabled at **3/7**.

## Execution and scoring findings

The supervised pilot is terminal: 12 physical calls, 11 valid responses and
one unretried timeout, with no heldout attempt. Under its frozen labels the
observed display has 12/14 useful cards, not a complete calibration score.
Known conservative usage cost is USD 0.036482; the timeout cost is unknown.

An independent code audit confirmed the early-stop arithmetic and found no
false-failure defect in the inspected helper, scorer, ID binding or parser.
The two-useful stratum requires 15/17 exact selections. Two completed cases
each selected both useful IDs plus one frozen-negative ID, and one timed out;
the best possible final result was therefore 14/17. Synthetic in-memory
controls confirmed that zero, one and two such misses remain reachable,
while three stop. The parser does not itself pad the selection to three.

This is distinct from the precision gate: hypothetical perfect remaining
results could still reach 105/107 useful cards. The subset's 85.7% therefore
was not the mathematical reason to stop. None of these findings permits
resuming the consumed run or opening heldout.

## Independent original-PDF diagnostic

A separate reviewer inspected all twelve candidate pages for exposed groups
G004, G008 and G012 against the original rendered public PDFs. The reviewer
did not read the old labels, provider choices or heldout. On the first pass,
G004/S04 and G012/S02 were rejected for lacking the requested operative
relationship. After the existing `USEFUL_BRIDGE` clause was made explicit,
the same reviewer recorded **Unsure**, with the original judgments retained:

| Candidate | Original public source | Unresolved boundary |
| --- | --- | --- |
| G004/S04 | lec05, physical page 22 | Whether scenario framing adds a concrete learning step beyond information already supplied by the question. |
| G012/S02 | lec04, physical page 11 | Whether prerequisite categories without an explicit link to the requested comparison constitute useful context. |

These are exactly the two excess IDs in the accepted pilot selections.
That correspondence was checked only after the independent review. It does
not prove that either page is useful, that the old labels are wrong, or that
the model achieved 90%. This diagnostic subset was chosen after observed
failures and cannot estimate general label reliability or model accuracy.
The clarification is a second interpretation by one reviewer, not a second
independent annotation vote. No old gold, receipt or score was altered.

A second reviewer subsequently inspected the same twelve original public
pages without old labels, provider choices or the first review. Given an
explicit exclusion of generic prerequisites and repeated question framing,
that reviewer classified **G004/S04 and G012/S02 as No for both page and
cue**, agreeing with the frozen negatives. All six frozen-positive pairs
in these three groups were independently judged useful. G008/S02 remained
Unsure because its potential contribution required an unstated geometric
step. This strengthens the diagnosis of excess selection under the narrower
question-specific rubric; it does not support converting either excess ID
to a positive. The two reviews still differ on what the broader bridge
wording permits. Their different instructions prevent treating them as a
controlled inter-rater agreement experiment.

Earlier evidence already contained a similar warning. The
[anchor feasibility review](../2026-09-30/2026-09-30-anchor-first-public-pdf-feasibility-result.md)
agreed with original page-utility labels on 53/63 inspected candidate pairs:
21/23 former positives and 32/40 former negatives. Thus **10/63 disagreed**.
That deliberately selected error/challenge set is not a random sample. Its
agreement rate must not be represented as overall dataset reliability.

## Concrete contract discrepancy

The current public review rule in
`scripts/review_fresh_public_source_id_v2.py` asks separately whether the
original PDF page is useful related reading and whether the exact cue helps
a reader **find** that relation on the page. Its response schema permits only
Boolean page/cue labels; unresolved judgments cannot be represented there.

The model instruction in `scripts/prototype_full_cue_high_thinking_v1.py`
requires **both** the shown cue and supplied page text to contain the explicit
relation, or a concrete necessary step/context linking to it. Its four-way
schema has no uncertainty label. The supplied `page_text` is actually a
bounded exact window (at most 1,200 characters), not necessarily the whole
visual page; the cue is at most 480 characters and contained in that window.
These limits are enforced by `backend/app/ai/source_judgment.py` and the
public freezer. A review of a full visual page can therefore use information
that is absent from the model's input. Earlier independent inspection found
two useful relations carried by figures but missing from extracted cues.

Three distinctions need to be explicit in a future measurement contract:

1. A page can help the student learn without containing a complete answer.
2. A cue can locate useful material without restating the complete relation.
3. The model cannot be evaluated as if it saw a diagram or omitted text that
   is available only to the PDF reviewer.

The frozen exact-selection gate additionally assumes an unambiguous useful
set for each question. Borderline labels can change both the expected set
and its one/two/three-useful stratum. The gate is implemented as approved;
silently relaxing it or changing two labels after seeing outputs is not a
repair. Conversely, repeated failures on this set alone do not establish an
intrinsic model limitation. Both selection quality and measurement validity
remain unresolved.

## Scope, checks and preservation

This continuation inspected maintained source, existing aggregate receipts
and prior original-PDF review evidence. It made no new provider request,
download, private-source read, database or environment change. Frozen pilot
files and heldout remain intact. Existing backend offline and transport-test
results remain separate regression evidence, not source-quality evidence.
A follow-up agent contract review hit the account usage limit; its new review
did not complete and is not counted as independent verification. The earlier
completed stop audit and PDF inspection remain the evidence described above.

A prospective offline remedy is described in the
[contract-alignment recommendation](2026-10-01-source-usefulness-contract-alignment-recommendation.md).
An independent design review required fresh reviewer/adjudicator contexts,
wire-only judgments recorded before viewing PDFs, and fixed complete
denominators without retrospective rescoring; those corrections are included.
Context validation passed 37 required files, 79 guides and 1,691 active local
links; whitespace validation passed. No runtime-code tests were repeated for
this documentation-only follow-up.
It needs the owner's plan decision before implementation. This record alone
does not authorize another model candidate, relabeling, heldout or activation.
