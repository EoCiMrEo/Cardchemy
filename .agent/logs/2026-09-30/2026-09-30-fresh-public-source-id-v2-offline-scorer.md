# Fresh public source-ID v2 offline scorer

Date: 2026-09-30 (America/Chicago). Starting checkout: `main` at
`6c02d6cf063acf83f4da5c08cfc4a3aa2c94be57`. The existing uncommitted Lane 6
work, populated volume, root `.env`, and previous public evaluation artifacts
were left intact. This task used no provider credential, network call, private
Knowledge, old frozen packet, or previously sealed heldout content.

## Scope and approved decision

The operator approved the offline `public_exhaustive_page_and_cue_v2` candidate
and asked to continue toward completing Lane 6. This record covers only its
new public PDF score contract, not a paid run, independently completed labels,
private release evaluation, runtime policy change, or Ask activation. The
separate packet builder freezes calibration and different-PDF heldout packet
and label files with one source-manifest hash, a separate blinded corpus-overlap
review hash, two reviewer identities, adjudication identity, and file hashes.

## Implementation

- `scripts/score_fresh_public_source_id_v2.py` reads the fresh packet and
  independent page-plus-cue labels, checks the freeze and code/model/result
  bindings, recreates the exact v2 ID-only wire per group, and matches each
  accepted ID receipt and usage receipt or one error receipt to that wire hash.
  It never sends a request or reads a key. The optional heldout packet, labels,
  and result files are opened only after all 48 calibration cases pass.
- `backend/tests/test_score_fresh_public_source_id_v2.py` uses synthetic
  48+48 groups and four disjoint synthetic document identities. It tests a
  full pass, valid empty no-useful selections, two and three timeouts,
  malformed foreign IDs, a weak displayed page, all-displayed usefulness,
  changed receipt hashes, zero-retry binding, and heldout cardinality.

Every split requires at least 46 valid responses. Physical failures count
against all 48 denominators; a failed no-useful group is not a successful
abstention. Every completed no-useful group must return a valid empty ID list.
The calibration hit threshold remains `max(30, ceil(5P/6))`, with each
positive question form at `ceil(5P_form/6)`. Heldout retains its 33 useful-hit,
31 useful-first, 60 useful-card, per-form and `ceil(5/6)` cardinality gates.
Both splits require zero false displays among no-useful groups and at least
90% useful page-plus-cue cards among **all** displayed cards. Malformed IDs
fail the gate instead of becoming no-match.

The exact useful ID set now defines a cardinality-correct positive group.
This keeps the numerical `5/6` thresholds but prevents a same-count weak ID
from receiving cardinality credit. In a synthetic heldout counterexample,
seven two-useful groups each replaced one useful ID with a weak ID. All 36
groups retained a useful hit and useful first page, 65 useful cards were
displayed, and useful-card precision stayed above 90%; exact cardinality fell
to 29/36 and the heldout gate failed. This clarifies the v2 requirement to
select every qualifying page up to three rather than fill a count.

## Checks and limits

- `backend/venv/Scripts/python.exe -m pytest tests/test_score_fresh_public_source_id_v2.py -q`
  from `backend`: **10 passed**. This is keyless synthetic contract evidence.
- The scorer plus existing inactive-v2 prototype tests passed together:
  `venv/Scripts/python.exe -m pytest tests/test_score_fresh_public_source_id_v2.py tests/test_exhaustive_source_id_public_prototype.py -q`
  from `backend`: **16 passed**.
- After the acquisition and packet-builder contracts settled, the four-file
  keyless subset passed together: `venv/Scripts/python.exe -m pytest
  tests/test_acquire_fresh_public_source_id_corpus_v2.py
  tests/test_prepare_fresh_public_source_id_v2.py
  tests/test_score_fresh_public_source_id_v2.py
  tests/test_exhaustive_source_id_public_prototype.py -q` from `backend`:
  **48 passed**. An interim combined run during the packet-builder's overlap
  review interface edit had 14 fixture/signature failures; that edit was
  completed and the rerun passed.
- A direct synthetic cross-interface read used the packet builder's fixture
  outputs, wrote canonical packet/label/freeze bytes to disposable OS Temp,
  and loaded **48 calibration groups with 48 locally recreated v2 wire hashes**.
  The scorer verified the packet hash in labels. This check did not read the
  synthetic heldout split, use downloaded PDFs, or call a provider.
- An initial targeted invocation from the repository root could not import
  `app` because backend tests require the documented `backend` working
  directory. A later non-ASCII fixture exposed Windows default text-decoding
  in the test helper; the helper now reads canonical UTF-8 JSON bytes. Both
  issues were repaired and the final targeted run passed.
- No fresh PDFs or independent reviews were acquired in this scorer task. No
  actual model receipt was scored, and no calibration or heldout quality claim
  follows. Receipt hashes and one-attempt IDs enforce internal consistency;
  they do not independently prove when a later paid attempt occurred or that
  a future operator approval was valid. A separate pre-call frozen execution
  contract and physical-attempt ledger remain required for a live trial.
- No temporary resource or database was created by the implementation.
  Pytest's disposable synthetic files remain under its normal OS-Temp area.

Ask remains disabled until independent calibration, heldout, private source,
accessibility, release, and deployment gates are actually satisfied.
