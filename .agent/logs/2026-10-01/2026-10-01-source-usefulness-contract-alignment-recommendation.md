# Recommendation: align source usefulness before another model trial

Date: 2026-10-01 (America/Chicago). **Proposal only.** No plan/ADR amendment,
new caller, model request, runtime change or Ask activation is made here.
The [post-stop contract audit](2026-10-01-source-usefulness-contract-audit.md)
identifies a measurement problem that should be resolved before spending
another provider budget. This is not a claim that alignment will by itself
make the selector meet the release gates.

## Proposed bounded offline work

Approve one public-only contract and input-sufficiency audit over **all 66
exposed calibration groups / 264 candidate pairs**, including every old
positive, negative, unattempted case and overflow case. Use only the four
already downloaded calibration PDFs and their existing question/cue/page
windows. No new source acquisition, embedding, model inference, private
Knowledge, database access, or heldout opening is required. The owner will
not be asked to review more source packets.

Before new annotations, freeze a separate review contract and shuffled packet
that hide old labels, provider choices, error status and desired cardinality.
Use fresh reviewer contexts without this audit, historical logs, labels or
model outcomes. Two independent reviewers first judge the exact wire windows
alone and durably record input sufficiency. Only then may each inspect the
original PDF and judge page/cue utility; the earlier wire-only judgment must
remain unchanged so visual context cannot contaminate it.
Keep three judgments separate, each allowing Yes/No/Unsure:

| Judgment | Proposed decision rule |
| --- | --- |
| Original-page usefulness | The page explains the requested relationship or a concrete learning step explicitly connected to it, under the question's material conditions. A complete answer is unnecessary. Generic prerequisites, shared terms, or repetition of information already in the question do not qualify by themselves. |
| Displayed-cue usefulness | The exact cue accurately directs the learner to that useful material on the cited page. The cue need not contain a complete answer or reproduce the entire page explanation. |
| Input sufficiency | The actual bounded text delivered to the judge contains enough of that learning link to judge usefulness without importing a missing diagram, omitted paragraph, prior chat or outside facts. |

Reviewers record an abstract reason category and source position for each
decision without copying lecture content into tracked artifacts. A separate
reviewer resolves disagreements against the frozen rule, without seeing
model output, prior outcome-selected audits or historical gold. **Unsure
remains unresolved; it never becomes Yes by default.**
Report agreement for each judgment and preserve each review, disagreement,
adjudication and source hash. Retain all 264 pairs, with an old-to-new label
mapping; do not remove inconvenient cases or rewrite historical results.

The audit must distinguish annotation ambiguity from missing model input and
from a selector error on an agreed, observable case. Report whether the
unchanged hit, per-form, exact-cardinality, no-match and all-displayed-card
gates remain attainable under the complete agreed corpus. This is prospective
arithmetic feasibility, not rescoring historical model outputs with new labels.
Freeze the complete denominators and cardinality assignments; retain and
report insufficient-input and unresolved cases instead of removing them.
If labels remain
unresolved, stop before a provider trial. If source information is missing
from bounded input, report that representation defect rather than teaching
the prompt to guess it. Changes to extraction, context size, visual input,
wire/output policy or corpus composition require a further concrete design
decision; this approval would not silently authorize them.

## What this would and would not change

With approval, amend Lane 6/ADR-024 to require one shared educational
usefulness definition across review, prospective judge and scorer. Prepare
only an inert schema/validation contract and offline fixtures for the three
judgments above. The existing consumed prompt, scorer, gold, source packets,
receipts and ledgers stay immutable. New annotations are development evidence
and cannot turn a failed pilot into a pass. Do not choose a new prompt/model
from these annotations or rerun any historical pilot within this scope.

Keep the release requirement of **at least 90% useful displayed cards**, the
positive-hit/per-form, no-match, multi-page, availability, access and source
integrity gates. Keep source-only output, one query embedding, at most one
source-ID request, zero answer/verifier calls, and no weak padding. The
original-PDF reader and existing authorized browsing remain available.

The existing 60-case public heldout stays sealed. A later validation design
must address whether its old review contract is compatible before using it;
do not assume that unread model outputs alone resolve a changed gold-label
definition. Any fresh corpus/network acquisition, model experiment or
private-source transfer needs its own applicable approval and limits.

## Deliverable and stopping point

Produce a content-free report of reviewer agreement, unresolved cases,
wire-observable useful references, old/new label discrepancies and the exact
next defect to repair. Include keyed immutable local review artifacts and
offline schema checks. This audit ends with either a defensible measurement
contract or a stated unresolved limitation; it does not continue through
unbounded prompt variations. Ask stays off and no Lane 6 release checkbox is
closed by annotation work alone.
