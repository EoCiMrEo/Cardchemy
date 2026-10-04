# Public Batch source-ID harness: keyless readiness

Date: 2026-09-29 (America/Chicago). Scope: the proposed public-only Lane 6
quality experiment after two HTTP 503 outcomes on the first unresolved
calibration group. Starting branch `main`, HEAD `6c02d6c`. The existing broad
working tree, root `.env`, populated volume, attached original PDFs, consumed
pilot ledgers and disabled Ask gate were preserved. This record does **not**
approve a Batch request or amend Lane 6/ADR-024.

## Work and boundaries

- Added `scripts/run_public_source_id_multipdf_36_batch.py` and provider-free
  contract tests. The new runner binds the unchanged public packet, labels,
  original three accepted ID/usage receipts, both later 503 claims and the
  scorer before considering 45 unresolved calibration items. Heldout has 48
  items from the separately frozen public PDFs and stays sealed unless the
  complete 48-group calibration passes.
- A keyed inline Batch creation has an exclusive durable claim before its
  non-idempotent POST. Known-job polls are GET only, claim before egress, and
  enforce a global 100-GET limit, 30-minute per-job spacing and a 48-hour
  pilot limit. An uncertain create cannot be replayed. Responses require all
  issued metadata keys, unique and valid selected IDs, finish/usage bounds and
  no per-item errors. A complete terminal item seal can be materialized after
  an interrupted local write without another provider request. The second
  paid POST requires the completed calibration receipt, rechecked score,
  enough time and at least one remaining GET.
- The application runtime is unchanged: the candidate remains public-only,
  source-ID-only and never makes an Ask answer/verifier call. No private
  Knowledge, history, user identity, labels or PDF bytes are in its payload.
  The runner's live modes retain `PENDING_SEPARATE_OPERATOR_APPROVAL` and
  therefore fail closed. The proposed envelope and asynchronous provider
  retention are in the [separate proposal](2026-09-29-public-batch-source-id-evaluation-proposal.md).

## Verification

- The exact prior public ledgers passed a credential-free, network-free
  preflight: 45 unresolved calibration groups, conditional 48 heldout,
  **zero new calls**; checkpoint SHA-256
  `5c39c622444e1df5a547e36cb00cf8e91cea81d83ad4ee0fa1a2f09681fffb73`.
- The four relevant provider-free Batch/previous-pilot suites passed
  **65/65**. New tests exercise both documented REST output shapes, keyed
  shuffled results, malformed/duplicate/error items, an admitted synthetic
  creation, persistent poll spacing, complete-receipt heldout admission,
  tampered receipts, 48-hour deadline and 100-GET limit. An initial test run
  from the repository root failed to import `app`; rerunning from `backend`
  used the documented package context and passed.
- A separate agent ran guarded disposable PostgreSQL and deterministic
  journeys: migration head/drift and downgrade/re-upgrade passed,
  **131 PostgreSQL tests passed** (3 skipped, 2,464 deselected), and both
  RAG-off/RAG-on journeys passed. See the
  [independent record](2026-09-29-lane6-disposable-postgres-and-journey-gates.md).
  The full backend and frontend offline gates were separately rechecked in
  the [offline release record](2026-09-29-lane6-independent-offline-release-recheck.md).
- `python scripts/check_context.py` passed 37 required files, 79 active
  guides and 1,521 local links before this new index entry. Targeted
  `git diff --check` passed.

## Limit

No Batch POST/GET, Gemini call, private-source transfer, database write,
runtime policy change or Ask activation occurred. Google Batch can fail or
expire; even a complete public result would not prove private original-PDF
usefulness, interactive reliability, current dormant 3.8 runtime quality,
spoken accessibility, or the four open Lane 6 quality/release checkboxes.
The next plan/ADR amendment and any paid Batch attempt require the operator's
fresh explicit approval for the exact endpoint, model, data, token, request,
time, cost and retention envelope.
