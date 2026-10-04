# Public reading-usefulness v4 reallocation and admission hardening

Date: 2026-09-28. Branch `main` at `6c02d6c`. This work continues the one
approved public, networkless Mixedbread audit before any quality inference.
The retained database, root `.env`, private Knowledge, original PDF archives,
and disabled Ask policy were not changed. No provider request, new public GET,
model scoring or application data write occurred.

## Why v3 was not admissible

An independent read-only v3 audit found a copied calibration/heldout lecture
slide (29 shared twelve-token shingles in selected cues), a train/heldout
alpha-beta relation paraphrase, incomplete rights attestations, and a count
cue in the first blind review packet IDs. The first reviews are diagnostic,
not blinded quality labels. The validator also accepted self-reported review
booleans without binding the review packet or its two independent judgments.
Scoring that fixture would misstate generalization.

## Local v4 corpus derivation

`scripts/derive_reading_usefulness_corpus_v4.py` pins all 14 acquired v3 PDF
hashes and the v3 preregistration, manifest and empty-plan hashes. It copied
the same 51,891,108 public PDF bytes into a new OS-Temp v4 directory, verified
every copy by SHA-256, and emitted a separate immutable derivation receipt.
No original v3 file was overwritten. The v4 split is train lectures
10, 11, 14, 15, 16, 33; calibration 22, 25, 26, 27; heldout 28, 31, 32, 38.
Reserved release PDFs 17 and 37 remain excluded. V4 preregistration, manifest,
plan and derivation receipt SHA-256 values are respectively
`c3bf3a6a25cee67a0205e1dea82b4627cdaff2b0da5dc9a75d2258af229d6a43`,
`9978ad6fd2ca50f20d20ed8231e7434e2d8f91bbdc21b61e5e44ddcb76f0eae4`,
`3c2ea97e78c7c50aacb5c8aae48da18f3800b71bfb78eb17f715827baf9f4f62`,
and `7040773f2941d999d6703c63d0e8ff5b11189735ba05975a1e27b4f75b158b93`.
The new unlabeled inventory has 519 pages and 598 bounded exact suggestions,
SHA-256 `3fb919cc94949c92c21dc2696795334ed0345835265e0e6ee3b3101bf09ff05d`.
All source text stays in OS Temp.

A read-only shingle comparison on previously selected pages/cues found zero
cross-split eight- or twelve-token pairs in v4; six-token fragments remain.
This is a lexical diagnostic, not proof against semantic paraphrases or a
validated new fixture. Reassigned provisional topics are imbalanced: v4 has
34 train, 15 calibration and 15 heldout topic triples before reauthoring,
against targets 32/16/16. At least 13 relation-family topic triples need new
authoring if these provisional labels survive review. No old labels were
promoted or used to fit the model.

## Admission guard

The validator now requires pinned v4 provenance and an external v2 opaque-ID
blind packet, mapping, two review receipts, adjudication, semantic-leakage
audit and candidate-level rights audit. It reconciles the exact page/cue
judgments with every fixture label and pins their hashes into the freeze.
Unknown and disagreement require an independent adjudication receipt before
freeze; a substantive cross-split selected-source overlap fails locally.
Reviewer IDs and audit booleans cannot prove real independence or source
rights by themselves, so those records still need genuine separate review.
The scoring runner now requires a fixed persistent bind-mounted audit ledger.
Its one-shot parent and child claims no longer depend on the caller's freeze
receipt filename; a copied receipt cannot open a second attempt. A synthetic
negative test exercises that case. The actual ledger mount and final resource
limits must still be verified before inference. A no-model admission probe using
five copied public scripts in a cached backend image passed with Docker
`--network none`, four CPUs, 2 GiB memory and the fixed OS-Temp bind mount;
the persistent ledger remained empty. The first probe from the repository's
E: drive failed because Docker Desktop could not mount that drive, so the
probe used C: OS Temp. No scoring or child claim ran.
The pinned `cardchemy-answer-worker:0.1.0` image also passed a dependency-only
import and the same fixed-ledger admission under `--pull never`, no network,
four CPUs, 2 GiB RAM, a read-only root filesystem, dropped capabilities and
non-root image user. This confirms the intended audit runtime can read the
guard without a model call; it does not verify the eventual full fixture mount
or inference latency.
An independent read-only rights diagnostic checked the 14 PDF hashes,
first-page notices and all 768 provisional text cue offsets. Its OS-Temp
report SHA-256 is
`55b44286ea668f2ac7e7bae0688bea93869560f8a0c89c08fe6935cf46d6b529`.
Text-only cues are conditionally reusable with creator/source/license
attribution and exclusion of separately sourced images/media. This diagnostic
is not a 14-document or 768-candidate rights attestation and cannot be
promoted to one for the new v4 fixture.

The first synthetic test run after switching to v4 failed because its fixture
had only v3 metadata. The synthetic builder was updated to include the v4
derivation receipt; focused tests then passed **52/52**. Additional guard and
runner tests were added afterward, including a second-freeze-filename
negative case and an uncertainty/adjudication receipt case. The combined
focused offline suite passed **65/65**.
The v4 inventory
builder ran on the locally derived corpus. No full release gate or model score
was run in this step.

## Remaining gates

Reauthor and independently review the v4 192-group fixture with opaque IDs;
obtain genuine document and candidate-level text/media rights attestations,
semantic split review and adjudication; freeze exact artifact/runtime hashes;
then run the single approved offline score if all admission checks pass.
The fresh published-source release holdout, any paid indexing/query calls,
enrolled original-PDF browser check, spoken accessibility check and flashcard
sparse-source yield remain separate open gates. Ask stays disabled.
