# Reading-usefulness public corpus acquisition — guarded stop

Date: 2026-09-28. Scope: source-only Lane 6 public, offline Mixedbread audit preparation. The operator approved one bounded local audit; this record covers only the attempted acquisition of its independent public PDF corpus. Branch `main`, HEAD `6c02d6c`; the existing working tree and retained application state were preserved.

## Preregistration and execution

The no-network preflight of `scripts/acquire_reading_usefulness_corpus.py` produced fourteen Illinois ECE448 lecture PDF URLs across train (six), calibration (four), and heldout (four), all source-disjoint. Lectures 17 and 37 remain reserved for the separate fresh Lane 6 release holdout. The script requires every selected PDF to be linked from the official lecture schedule and checks each acquired PDF's first-page CC BY 4.0 declaration, SHA-256, physical page count, size, and extracted-text quality before freezing a manifest. Its hard limits are 18 document URLs, 24 GETs including redirects, 120 MiB total, 10 MiB per PDF, 100 pages per PDF, and 30 minutes.

The sole executed acquisition command was the bounded script with output under OS Temp `cardchemy-reading-usefulness-public-20260928`. It received the schedule page, then stopped at `preregistered_pdf_not_linked_from_index`, before requesting any PDF. Its durable failure receipt reports **one GET** and **10,495 bytes received**. The preregistration SHA-256 is `a8acfb36b7bfb7ab2ff0ec7c04ba01c4da0cbf83543660251864104fedad468d0`. The Temp directory contains only `preregistration.json` and `failure.json`; there are zero PDFs and no `manifest.json` or labels. The terminal receipt and path were preserved; the acquisition was not retried or restarted.

## Result and boundary

The approved experiment cannot proceed to independent question authoring or scoring from this corpus, because the preregistered source list failed its authoritative-link check. No model scoring, Gemini request, private Knowledge read, DB write, runtime switch, or Ask activation occurred. This is an acquisition/design failure, not evidence about the Mixedbread model's reading-usefulness quality. A corrected source list would need a separately reviewed preregistration and a fresh bounded acquisition decision; do not silently reuse the failed one.

`backend\venv\Scripts\python.exe scripts\check_context.py` passed after the log/index update: 37 required files, 78 active guides, and 1,378 local links. No PDF or model artifact was created by this acquisition.
