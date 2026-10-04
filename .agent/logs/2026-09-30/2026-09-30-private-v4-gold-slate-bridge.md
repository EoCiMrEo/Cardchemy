# Private v4 gold-to-slate bridge contract

Date: 2026-09-30. Starting checkout: `main` at `6c02d6c`, with a broad
pre-existing uncommitted Lane 6 working tree. This slice preserves that work,
the retained database/volume, root `.env`, published Knowledge and original
PDFs. The fresh 12-case private stage-1 packet was **not opened**. No private
PDF text or secrets were read, no provider request was made, and no database
operation or migration ran.

## Scope and change

The existing stage-1 freezer hashes twelve independently chosen gold pages and
their current document/content/index revision, canonical page and attached
original-PDF SHA. The dormant v4 scorer separately validates candidate
`page_key`/`cue_sha256` identities and frozen labels, but its asserted stage-1
hash alone did not establish that the two packet schemas describe the same
gold pages and current source revision.

Added `scripts/bridge_private_source_gold_v4.py`, a pure validator over
caller-supplied, exact-byte-hashed stage-1, v4 roster and label artifacts, plus
an authorized current-page snapshot and captured pre-judge candidate slates.
It requires all twelve T cases and form balance; checks each gold page key,
canonical page SHA, document/content/index revision, corpus/embedding space,
attached original-PDF SHA/page count and current/published/index-ready flags;
maps issued runtime `S01`–`S04` order to scorer `C1`–`C4`; hashes each exact
bounded cue slice from canonical page text; and requires the scorer's complete
independent page/cue label identities. It returns only hashes and counts with
`release_gate_passed=false`. Direct invocation is a zero-read preflight.

The snapshot is a **trusted caller input**, not proof of current authorization
by itself. A later private release run must obtain it with current principal,
Subject, publication, revision, active-space and original-PDF checks in a
read-only transaction, preserve the review-before-selection order, validate
the signed freeze and actual display with the existing scorer, and independently
verify original-PDF inspection. This slice does not collect those records,
freeze or score the real private holdout, change the scorer's gate, approve
private transfer, or enable Ask.

## Verification

- Synthetic-only focused backend run:
  `venv/Scripts/python.exe -m pytest -q tests/test_private_source_gold_v4_bridge.py tests/test_private_source_gold_v4.py tests/test_source_judgment_display_v4_score.py`
  from `backend`: **42 passed**.
- New bridge regressions reject wrong stage-1 bytes/roster SHA, changed gold
  identity, content/index/PDF revision drift, unpublished/unauthorized or
  changed corpus, changed canonical gold text, altered cue offsets/issued IDs,
  and missing or altered exact-cue labels. The valid two-candidate case binds
  both issued cues. No real private data was used in these tests.

No backend offline suite, disposable PostgreSQL, browser, hosted CI, live
provider or manual accessibility check was run for this isolated contract.
Lane 6 release evidence and Ask admission remain open.
