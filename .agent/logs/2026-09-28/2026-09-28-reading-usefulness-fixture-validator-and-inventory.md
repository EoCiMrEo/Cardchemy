# Public reading-usefulness fixture admission and source inventory

Date: 2026-09-28. Scope: approved provider-free preparation for the public
Mixedbread 192-group audit. Branch `main`, starting HEAD `6c02d6cf`; existing
working-tree changes and retained application state were preserved. No private
Knowledge, database, provider, network request, model scoring, runtime-policy
change, or Ask activation was part of this work.

## Inputs and implementation

The approved [proposal](2026-09-28-reading-usefulness-classifier-proposal.md)
requires 96/48/48 training/calibration/heldout groups, four exact PDF windows
per group, equal zero/one/two/three useful-card strata, eight relation families,
direct/paraphrase/follow-up coverage, independent blind review and adjudication,
and a freeze before scoring. The acquisition
[plan](../../../scripts/acquire_reading_usefulness_corpus.py) supplies the
required group field names. Its newly approved v3 corpus manifest is pinned at
SHA-256 `fb59c3df42d87b0305ce2fe403c779a6f9c4f583b1bedd7bcd77860d05cd61e7`;
the preregistration is pinned at
`ee050f83d107c59cea09b2140f7cec81047684a9192d26ac7517a0753edfa881`.
The 14 acquired documents are split 6/4/4 and the first-page CC BY 4.0
declarations and bytes are rechecked before inventory or fixture validation.

[The validator](../../../scripts/validate_reading_usefulness_fixture.py) accepts
only a canonical JSON fixture bound to the v3 corpus, plan and pypdf extractor
version. It requires all 192 independently reviewed groups before admitting
any freeze. Its exact arrays preserve four candidate cues, one-based page
numbers, start/end character offsets, full extracted-page text SHA-256,
separate original-page and displayed-cue usefulness labels, two distinct
reviewers and a matching adjudication record. It checks the split/label count
targets, every relation-family/question-form cell, disjoint document and
question-template identities across splits, exact page/window text, license
provenance and reviewer attestations. It does not infer a usefulness label.

The exclusive `freeze` receipt binds corpus preregistration, source manifest,
fixture plan, labeled fixture, validator, scoring harness, runtime manifest and
the previously pinned Mixedbread bundle manifest. `verify` requires the
receipt's SHA-256 supplied from an external recorded pin and rechecks the
underlying files. Neither mode executes the model. The receipt cannot itself
prove when reviewers adjudicated or when a model was first run; the operator
must record its digest outside the mutable audit folder before any score.

[The inventory builder](../../../scripts/build_reading_usefulness_source_inventory.py)
rechecked the v3 source bytes and wrote only to OS Temp. Its deterministic,
unlabeled authoring aid contains extracted page text, page SHA-256, original
page numbers and exact at-most-480-character suggested windows with offsets.
The exclusive output is
`C:\Users\eocim\AppData\Local\Temp\cardchemy-reading-usefulness-source-inventory-v3-20260928.json`:
14 documents, 519 pages, 598 suggestions, zero omitted suggestions, 636,491
bytes, SHA-256 `25c4d00f9426bef3e01180b4cbc7f8b0335818cd2333be84495d86af4675a264`.
It contains no authored questions, reviewer labels, score or tracked source
text. Third-party embedded material still needs human exclusion before any
excerpt enters a tracked public fixture.

## Verification and limits

`backend/venv/Scripts/python.exe -m pytest -q
tests/test_reading_usefulness_fixture.py` from `backend` passed **20/20**
synthetic offline tests. They cover exact source offsets and hashes, 192-group
strata, split/template and reviewer failures, rights-review refusal, external
freeze pinning, exclusive writes and the unlabeled inventory. Python compile
and targeted whitespace checks passed. The real v3 inventory run was
provider-free and returned `unlabeled_inventory_created_no_scoring`; PDF
reader repair notices were emitted for some existing source PDFs but extraction
completed and the manifest metrics matched. Later runs suppress that repeated
library warning output while still failing on invalid bytes, pages or notices.

This work does not establish that any page/cue is actually useful, that
semantic paraphrases do not leak across splits, that human reviewers are
independent, or that the proposed classifier meets any calibration/heldout or
release gate. No 192-group reviewed fixture exists in this record. Ask remains
disabled.
