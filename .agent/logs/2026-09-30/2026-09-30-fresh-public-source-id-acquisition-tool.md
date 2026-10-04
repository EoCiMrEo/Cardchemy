# Fresh public source-ID PDF acquisition tool — offline readiness

Date: 2026-09-30 (America/Chicago). Starting checkout: `main` at `6c02d6c`.
The shared Lane 6 working tree, root `.env`, existing public PDFs, private
Knowledge, consumed provider ledgers and both old heldout label sets were left
unchanged. This work made **zero HTTP requests**, zero provider calls and zero
database changes. Ask remained disabled. The operator approved an offline
prototype, not acquisition, paid evaluation, private transfer or activation.

## Scope and correction to the earlier proposal

[`scripts/acquire_fresh_public_source_id_corpus_v2.py`](../../../scripts/acquire_fresh_public_source_id_corpus_v2.py)
is a new, independent Spring 2022 eight-PDF tool. It does not modify the
Spring 2020 acquisition script or any frozen fixture. The four calibration PDFs
are lectures 04–07; heldout is 08, 09, 11 and 13. Exact expected page counts
are 32, 33, 40, 31 / 46, 33, 27, 36. The canonical preregistration SHA-256
is `4dd13466920e66086cba7c433d6631d1944a71e9205f597387d61b08ae181fdc`.

The [earlier acquisition proposal](2026-09-30-fresh-public-pdf-acquisition-proposal.md)
said the prior pilot had eight CS447 PDFs. A metadata-only check found no
support for that source set: the earlier 96-case multi-PDF pilot used the
14-PDF ECE448 Spring 2020 v4 corpus. The new tool therefore requires that
exact prior manifest, pinned to SHA-256
`9978ad6fd2ca50f20d20ed8231e7434e2d8f91bbdc21b61e5e44ddcb76f0eae4`,
and a separate source-metadata manifest for the two reserved Illinois PDFs.
It never accepts a fabricated eight-CS447 manifest. This corrects the
comparison set, not the eight new Spring 2022 acquisition URLs or quality
gates. Exact PDF hash disjointness is checked at acquisition and independent
rehash; blinded content-overlap review remains required before question
authoring because slides can be reused across years.

## Guarded tool behavior

- Default invocation prints the frozen roster and SHA with `network_requests=0`.
  `--preflight` checks the two comparison manifests and an unused direct OS-Temp
  output path without a network client or approval artifact.
- `--execute` is separately gated by an exact one-use OS-Temp approval artifact,
  absent provider credentials, the pinned source manifests and an exclusive
  output directory. A consumed approval ID cannot be replayed from another
  artifact path. This mode was **not run**.
- Network mode permits only the exact HTTPS schedule and eight PDF paths on
  `courses.grainger.illinois.edu`: no alternate host, credential, port,
  query, fragment, file substitution or retry. It caps physical GETs at 13,
  redirects at two per fetch, schedule body at 512 KiB, each PDF at 10 MiB,
  aggregate bodies at 84,410,368 bytes, connection/read timeout at 15/120
  seconds and whole run at 30 monotonic minutes. Redirect bodies are not read.
- The fetched schedule must link all eight exact PDFs. Each downloaded PDF
  needs a `%PDF-` signature, parseable unencrypted body, its exact preregistered
  page count below 60, first-page CC BY 4.0 text, at least 1,500 alphanumeric
  extracted characters and at least `max(3, pages // 3)` pages with 40 such
  characters. The success manifest records source/schedule SHA-256 and bytes,
  PDF metrics, prior manifest hashes, GET/body/time counts and no labels.
  Rejected runs leave a content-free failure receipt and no success manifest.
- `verify_manifest` independently rehashes and reparses every local PDF and
  the schedule against the manifest and the unchanged prior metadata before a
  separate review packet may be admitted. The success manifest explicitly
  records `content_overlap_review=required_before_question_authoring`.

## Existing public source metadata, no label access

The local Spring 2020 v4 `manifest.json` SHA-256 matched its dated evidence
pin above and contains fourteen `documents` entries. The two reserved source
PDFs were rehashed locally without reading their question/label files; their
hashes and page counts matched the [public holdout source record](../2026-09-28/2026-09-28-public-original-pdf-holdout-freeze.md): lectures 17 and 37,
29 and 31 pages. A source-metadata-only, exclusive OS-Temp comparison file was
created at
`C:\Users\eocim\AppData\Local\Temp\cardchemy-source-id-fresh-sp2022-reserved-comparison-20260930.json`
with SHA-256 `2c91398c3a59ae3cf4eebb1e3119a7b7d0f1845b9ef83c7b6a21b3a38c23118f`.
It contains no question, cue or usefulness label. The Spring 2020 manifest is
`C:\Users\eocim\AppData\Local\Temp\cardchemy-reading-usefulness-public-v4-20260928\manifest.json`.

The approval-less preflight using those two actual manifests passed with
`network_requests=0`, output available at
`C:\Users\eocim\AppData\Local\Temp\cardchemy-source-id-fresh-sp2022-v2`.
This does not authorize or prove a download; all eight new PDF hashes and text
quality remain unknown.

## Verification and remaining gates

`backend/venv/Scripts/python.exe -m pytest -q
tests/test_acquire_fresh_public_source_id_corpus_v2.py` from `backend` passed
**16/16** offline fake-transport tests. They cover the inert default and
preflight, exact roster, URL and redirect rejection, GET/byte/time limits,
missing/duplicate source manifests, success rehash/tamper detection, PDF
signature/page/license/text/encryption rejection, failure receipt/no retry and
one-use approval. `py_compile` passed for the new tool and tests. No real
Spring 2022 response, certificate, license extraction or source-content
independence was validated. Independent blinded overlap review, source/cue
labels, frozen scorer and a separate bounded Gemini pilot remain later gates;
private Knowledge and Ask activation are further separate release gates.
