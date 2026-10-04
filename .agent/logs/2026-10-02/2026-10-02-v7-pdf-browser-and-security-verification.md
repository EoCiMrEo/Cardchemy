# Current v7 PDF browser and isolated security verification

## Scope and preservation

Continue the authorized Lane 6 release checks after the restore-verified
forward cutover to `20261002_0032`. Dirty `main`, original PDFs, populated
volume, operator root `.env` and verified backups are preserved. Ask and
the source judge remain disabled. This record establishes browser/runtime
and scanner results, not independent source usefulness or release completion.

## Browser observations

Using the approved host-managed in-app browser and the already authenticated
student session, open each original PDF through Published lectures on the
retained v7 application. Week 2, Week 3 and Week 4 all rendered their original
page-one canvas with the expected physical page totals (33, 42 and 32).
The previously reported PDF-display fallback warning was absent. Week 2
keyboard Next opened physical page two while keeping the initial citation
page distinguishable. Escape dismissed the dialog and restored focus to its
opening lecture button. Week 3 Escape/focus restoration also passed.

The mobile viewport showed a bounded, scrollable dialog with visible PDF
controls and readable-text/extracted-text disclosures. Browser QA verdict:
**4/5 for this tested PDF flow**; authenticated opening, rendering and keyboard
navigation passed, while spoken assistive-technology verification and Ask
selection outcomes were not exercised. No browser question was submitted to
Gemini. Private PDF text/screenshots were not retained in tracked evidence.

A later Week 4 keyboard Next check opened physical page two of 32. Escape
closed its dialog and restored focus to the Week 4 lecture button.

## Security finding classification and repair

The first isolated scanner run found three generic-key matches: an exact
frozen public roster SHA and two invented consumed-authorization identities
inside negative tests. Source inspection and the redacted report confirmed
these were noncredentials. Add separate exact-path/exact-match or exact-line
allowlists in `.gitleaks.toml`; no broad test/log exemption, severity reduction
or ignored real credential is introduced. Preserve the prior metadata,
redacted findings and checksums under ignored verification storage.

The documented full `scripts/test_security.py --image-tag 0.1.0` rerun passed:
Git history/prospective exported tree Gitleaks, workspace Trivy secret scan,
and all three backend/backend-OCR/frontend HIGH/CRITICAL vulnerability gates.
CycloneDX SBOMs, immutable image identities and report SHA checksums are in
ignored `artifacts/security`. Source/image scans ran without network; the
public advisory database was obtained before mounting exported source/images.
Operator environment, database, original PDFs and provider keys were excluded.
The isolated export was cleaned by the harness; real Git history was unchanged.

The separately documented credential-free/networkless backend-OCR image smoke
passed native dependencies, workers/API, authentication purpose, source
encryption, text-PDF extraction, bounded original-page PNG rendering and
image-only PDF OCR with English language data. Backend/frontend image smoke
had already passed for these matching images.

Public provider quality, current private displayed-source measurements,
spoken assistive-technology verification and Ask activation remain separate.
Lane 6 remains **3/7** at this observation.
