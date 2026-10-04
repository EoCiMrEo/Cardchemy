# Public visual calibration preparation

Date: 2026-10-01 (America/Chicago). Implements the
[approved scope](2026-10-01-visual-source-public-calibration-approved.md).
Dirty `main`, HEAD `6c02d6c`, unrelated work preserved. Lane 6 remains 3/7,
Ask disabled. Two subagents stopped at their account usage limit; completed
documentation and a partial scorer were retained. The primary agent finished
code and verification. No provider request during preparation.

## Implementation

- `scripts/run_visual_public_calibration_v2.py`: keyless admission, externally
  pinned executable/request receipt; only the fenced worker reads the dedicated
  judge key and sends the approved POST. No application Settings, DB, private
  source, download or heldout access.
- `scripts/score_visual_public_calibration_v2.py`: all 67 requests, 54 historical
  positives, original strata and 108 Yes/151 No/5 Unsure qualification; exact-set,
  availability, per-form and all-displayed-card denominators. Unknowns earn no
  credit; clarification is not conclusive no-match. Optimistic ceilings stop
  when unchanged gates are mathematically unreachable.
- `scripts/launch_visual_public_calibration_v2.py`: scrubbed keyless preflight,
  hidden detached supervisor, worker suspended/assigned before resume, four CPU,
  two GiB aggregate committed memory, 90-minute deadline and kill tree on close.
  External approval SHA passes unchanged. Fixed exclusive launch/run/attempt
  ledgers prevent copied receipts/output paths from permitting replay.
- REST omits only the preparer's top-level model selector metadata: the same
  model is fixed in the URL. Prepared and actual REST hashes bind unchanged
  question/cues/text/images/schema/HIGH thinking/output bound/`store=false`.
  Receipts keep strict IDs/closed labels/statuses, safe error codes, numeric
  usage and latency; no raw response, thought text, answer or internal exception.

## Findings before credential or network access

One admission stopped because numeric JSON object keys decode as strings.
Canonical-byte comparison now checks the same frozen bound without regrading.

Original request `G` IDs and independently shuffled review `Q` IDs differ.
The caller derives their bijection from the externally pinned parent mapping,
retains candidate IDs and rejects inconsistent/missing bindings. A reversed-
order synthetic regression proves scores attach to the correct question slate.
No ordinal assumption remains. These repairs used zero provider requests.

Earlier keyless receipts are superseded by the final executable freeze and
cannot pass current code-hash admission; no claim was consumed. All historical
inputs/reviews/failed pilots/ledgers remain intact.

## Actual checks and limits

New contracts: **49/49** pass. Full related source/visual suite: **300/300** pass
in 19.95 seconds. Includes native Windows assignment for a synthetic keyless
child and injected 67-call transport verifying spacing/accounting/complete
receipts/no retry. Real-public keyless admission revalidates all 67 prepared
requests and cached original PDF/PNG identities; zero network calls.

These checks do not prove model/provider success, private retrieval/display
quality, browser/release readiness or enablement. Final receipt/roster hashes
and actual execution are recorded separately. Root environment, populated
data/volumes, exact private PDFs, ignored backups and source-only policy remain.
