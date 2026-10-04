# Public visual checkpoint continuation: transport timeout stop

Date: 2026-10-01 (America/Chicago).

## Execution and preservation

The [approved 63-request continuation](2026-10-01-visual-calibration-v3-approved.md)
ran once under its distinct v3 authorization and four-CPU/two-GiB named
process tree. Approval SHA:
`001fa1a743811ad601f1af91620fc110f51d3af0331639ac17e56618cc65dc56`.
The actual execution-account keyless preflight passed after a read-only ACL
grant on the new **public-only approval directory**. No private ACL, root
configuration, volume, original private PDF or database was changed.

The successor caller/scorer/supervisor passed **75 synthetic tests** before
launch. Admission rechecked the four old receipts against frozen inputs,
closed verdicts, physical claims, old run-claim and approval/result hashes.
The JSON round-trip converts integer metric keys to strings; canonical-byte
comparison repaired that local admission bug without changing any metric.
The complete disk-serialization regression and tampered/extra-attempt
negative cases now cover this boundary.

## Observed result

- Four new physical requests: **one valid, three `provider_timeout`**.
- Three errors completed at **30,008 / 30,007 / 30,002 ms**; the valid
  request completed at **13,232 ms**. They provide no evidence about page
  classification quality on those failed groups.
- No automatic retry. Four prior valid requests were not resent.
- Combined evaluation is **8/67 attempted**, **5 valid**, **59 unattempted**;
  the new three errors make the approved maximum-two-error / 65-valid gate
  mathematically unreachable. The caller stopped as required.
- Partial displayed usefulness remains **4/5 = 80%**; this is not a complete
  model-quality pass. Hit/form/no-match and independent holdout remain open.
- New reported guard cost **USD 0.003695**; inherited USD 0.020718 is
  separate. Combined known guard cost **USD 0.024413**, plus **three unknown
  request costs**. Free-tier listing and guards are not provider invoices.

Terminal result SHA:
`fa56e56f5c53f8bcb48b3b7c993613638fa7209feb50b76ae213d59dc409643c`.
The supervisor receipt reports exit zero; exact supervisor and worker PIDs
were verified absent after completion. The one-use launch/execute/run and
physical claims remain consumed. Do not restart or overwrite them.

## Next action and limits

This stop identifies the **30-second transport/deadline availability gate**,
not a proven failure of model usefulness. Inspect latency and repair the
matching runtime/deadline contract before another precisely approved
provider run. Preserve all failed cases and uncertainty; do not grant them
empty/no-match credit or recast the partial 80% as completion.

Offline worker archive preparation also passed **41 targeted tests**:
bounded complete AES-GCM/SHA authentication before rendering, including
interior corruption, missing/reordered blocks, key mismatch and oversize.
This helper grants no authorization and is not connected to active Ask.

No heldout opening, private source transfer, generated answer, Ask enablement
or database write occurred. Lane 6 remains **3/7**. The owner-approved
80% usefulness floor and all distinct gates are retained.
