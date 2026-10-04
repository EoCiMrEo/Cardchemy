# Approved offline source-usefulness contract audit

Date: 2026-10-01 (America/Chicago). The owner approved the
[bounded recommendation](2026-10-01-source-usefulness-contract-alignment-recommendation.md)
and a Lane 6/ADR-024 amendment. This is a new authorization record; the
historical proposal and consumed public-pilot results remain unchanged.

## Scope and procedure

Audit every one of the 66 exposed calibration questions and 264 candidate
pairs, using only the four existing public calibration PDFs. Freeze a new
shuffled, source-hash-bound packet with no old labels, choices, failure
status or intended cardinality. Divide it into three complete 22-question
batches for manageable independent reviews; this partitions work and does
not select or exclude cases. For each batch, use two fresh reviewer contexts.
Each must finish and seal all wire-only judgments before receiving original
PDF page identities. Then inspect rendered original pages and record separate
page and cue judgments. A third fresh reviewer handles disagreements without
historical gold or model choices. Use Yes/No/Unsure; no forced positive label.

Reviewers use one frozen rubric. Wire sufficiency asks whether the bounded
input alone expresses a question-specific learning link without missing
visuals, omitted text, prior chat or outside facts. PDF usefulness allows an
explicitly connected learning step rather than requiring a complete answer.
Cue usefulness asks whether the exact displayed text directs the learner to
that material. Generic prerequisites, shared topic and repetition of the
question alone do not qualify. Preserve original wire judgments after PDF
inspection and preserve all disputed/insufficient cases in reporting.

## Boundaries

This audit permits no Gemini/model inference, download, private Knowledge,
database/environment edit, heldout opening or Ask activation. Old prompts,
gold, source packets, receipts and ledgers remain unchanged. Any future
quality design must resolve compatibility with the sealed heldout before
using it. Keep the 90% all-displayed usefulness requirement and every other
existing release gate. New labels are development evidence only and must
not be used to declare a historical failed pilot successful.

## Starting evidence

Dirty main at 6c02d6c, 448 changed/untracked status entries. Existing work is
preserved. Plan, ADR-024/index and current-state status are updated to this
approved offline scope. Lane 6 remains 3/7; the audit is not yet complete.

## Frozen review packet

`scripts/audit_source_usefulness_contract_v1.py` verified the pinned exposed
packet and manifest, only opened the four calibration PDFs, and checked
every exact context/cue offset against current PDF extraction. All 66 groups
and 264 pairs are present in three equal shuffled batches. No old gold or
model output is read by this helper. Whole-packet freeze SHA-256:
`0d52a52bdc160f5cc159f5f2571b3c8562a7142d1493d027e00c5168f356ae28`.
Rubric SHA-256:
`ef2a1740549779fef686c594a4a722815e0762ae48e9340ddac1f6000db9a40c`.
The local artifact root is
`C:\Users\eocim\AppData\Local\Temp\cardchemy-source-contract-v1-dk54c0v7`.
Its mapping remains separate from reviewer packets. Reviewer contexts are
fresh and independent; original PDF identities are issued only after a
complete immutable wire-review file and hash are created. Synthetic guard
tests are being checked independently. Review progress is not a quality pass.

## Offline harness verification and interruption recovery

The dedicated annotation and aggregation contracts passed **56 synthetic
tests** from `backend`. They cover complete pair preservation/blinding,
tri-state validation, seal order, partial-state/tamper rejection, independent
review binding, vote-free dispute packets, unresolved-label retention and
complete 66-group/264-pair finalization without historical model scoring.
One added assertion initially matched a rubric field name as if it were a
leaked old-label key; the assertion was corrected to test exact JSON keys.
No real review label changed as a result.

The first reviewer processes stopped before writing reviews during a task
interruption. Fresh contexts then completed and sealed batch 1/a, batch 1/b
and batch 2/a wire reviews (88 judgments each). All three later reported
an account usage limit during PDF review. The saved wire files were retained;
resumed original reviewer contexts continue only their page-review stages,
without resealing or revising wire judgments. At this progress snapshot no
page review is sealed, so no reviewer agreement or model-quality conclusion
is available. The remaining three reviewer assignments and blind adjudication
are still pending. Original-PDF renders alone do not establish completed
inspection. Do not regenerate the freeze or overwrite any sealed artifact.
