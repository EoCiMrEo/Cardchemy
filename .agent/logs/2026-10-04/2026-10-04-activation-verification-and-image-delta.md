# Activation verification and exact backend image delta

## Scope and preservation

Continuation of the authorized Lane 6 completion, crossing from October 3 to
October 4 in America/Chicago. Dirty main HEAD remains
`6c02d6cf063acf83f4da5c08cfc4a3aa2c94be57`. Existing work, root settings,
populated volumes, original PDFs, backups, old jobs and all provider failures
are preserved. These checks do not make a new provider request.

The independently reviewed activation patch opens only the accepted runtime
fence to `related_knowledge_navigation_v8`. Fresh-install Ask and source-judge
flags remain default-off. Historical policies remain readable and fenced.

## Test failures and execution context

The first focused run recorded three failures, 334 passes and three errors.
Three errors were pytest's inaccessible shared temporary root; three failures
were a synthetic shutdown Subject missing its active embedding space. The
[independent diagnosis](2026-10-04-activation-target-fixture-and-temp-diagnosis.md)
records the smallest fixture correction and nine passing target cases. No
runtime behavior or config assertion was relaxed.

The repaired default-sandbox attempt then stalled before creating pytest's
temporary base. Its exact identified child was stopped after 286.054 seconds;
the parent recorded exit 4294967295, no summary and unchanged 462 scoped inputs.
That receipt and claim remain, and are not counted as a pass. The independent
diagnosis reproduced the execution-context issue. A fresh run through normal
command approval redirects TEMP/TMP and pytest's absent base to an owned ignored
directory, retaining the same credential-free test environment.

The normally approved repaired focused run passed **340 tests in 64.17 seconds**
(wrapper 68.072 seconds). All 462 scoped backend Python files and pytest.ini
remain identical before/after, map SHA
`0101318f632e67b5d4f2ae4def5396dcc70ddfe1e9e7a47d164bed3646c8f4d2`.
No provider keys, live opt-ins or retained database were injected. This snapshot
does not claim every transitive repository file.

The first fresh full run recorded **one failure, 5,361 passes, 271 skips and two
live deselections in 366.80 seconds**, with unchanged inputs. The remaining test
requires a review output outside the repository, while the isolated harness had
placed tmp_path inside ignored repository scratch. Its privacy rejection was
correct. The full-suite failure and claim are preserved. The harness now creates
a fresh owned external OS temporary parent, rejects a repository-contained
parent, and still isolates TEMP/TMP plus an absent pytest base. The test and
production output guard are unchanged. The terminal normally approved rerun
belongs in the final closure record.

## Exact image and security checks

The prior backend image is retained under
`cardchemy-backend:lane6-preactivation-20261003`:
`sha256:7002fd38e80dbe3ac89e4ab64e305944848d4cdd594de2bf41d229237a30af41`.
The built current backend is
`sha256:b88f3603877c6cb8cc9cbef0c2a7e9428163ce938fdffdbc86972a4cb7a1fe80`.
Its keyless networkless image smoke passed API/worker imports, password hashing,
JWT/AES-GCM, bounded PDF/PNG and OCR-absent checks.

The new security run exited zero: history/worktree secret scans clean, and
backend, optional OCR and frontend images had zero HIGH/CRITICAL findings.
Current artifact metadata records the exact image IDs, SBOMs/checksums and
failed_gates=[] under artifacts/security. The prior directory was preserved as
artifacts/security-preactivation-20261003. The source snapshot predates only
the later shutdown fixture correction; the runtime image bytes are unchanged.
This is local image/security evidence, not hosted CI or production deployment.

## Cleanup and remaining operational proof

Both owned selected-source replay servers were stopped; port 8899 was verified
closed. The owned replay tab was closed. The authenticated local app tab remains
for post-cutover verification. Ignored receipts and test scratch are retained as
evidence; no populated volume or original source was removed.

At this record's creation the two installation flags are still false. Current
full-suite success, flag-only change, matching-service recreation, heads/drift,
actual health/profile/browser evidence, context validation and Lane/goal/heartbeat
closure remain separate root-owned steps. See the
[final closure](../2026-10-03/2026-10-03-lane6-final-closure-and-activation.md)
for their actual terminal results; this progress record is not activation proof.
