# Public original-PDF holdout keyless plumbing rehearsal

Date: 2026-09-28. Scope: provider-free rehearsal of the already frozen public
two-PDF source holdout in a disposable PostgreSQL container. Branch `main` at
`6c02d6c`; the populated database, root `.env`, original PDF archives and
substantial pre-existing working-tree changes were preserved. Ask stayed off.

The new `scripts/run_public_knowledge_holdout.py --mock` parent verified the
frozen holdout and independent source labels, created a one-off database and
network without volumes, migrated it to head, ran head/drift checks, and
launched the guarded child. The child used only deterministic local vectors:
two document batches, twelve synthetic plumbing queries, zero provider
retries, zero answer calls and zero frozen holdout questions embedded. It
captured, indexed and published both PDFs; opened their original bytes through
the enrolled-student routes; rejected outsider, instructor, wrong-Subject and
post-unpublish access. The final report was
`disposable_mock_plumbing_passed`, with `opened_pdf_document_count=2`,
`selector_calls=0`, `release_gate_passed=false`.

The first run lacked Docker API permission under the default sandbox. A normal
approved Docker execution exposed a generic child failure. The parent was
changed to report only fixed non-content guard codes; a further approved run
identified `pdf_original_bytes_changed`. Inspection showed the harness had
attempted an unbounded GET, while the original-PDF API intentionally requires
an at-most-8-MiB byte range. The child now confirms the unbounded GET is
rejected and reconstructs each source through checked bounded `206` ranges,
matching every range and the complete SHA-256. An approved rerun passed.
Raw child output, credentials and PDF text were never printed. Each one-off
container/network was cleaned; a post-run `docker ps -a` name check was empty.

Verification: eight targeted backend admission/executor unit tests passed;
the final real disposable rehearsal passed with the counts above. This proves
capture/index/original-PDF/access plumbing only. It does not run the source
selector, assess reading usefulness, count as a paid-provider test, or permit
Ask activation. The final candidate and fresh release holdout remain unscored.
