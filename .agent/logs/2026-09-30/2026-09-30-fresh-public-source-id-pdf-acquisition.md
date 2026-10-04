# Fresh public source-ID PDF acquisition

Date: 2026-09-30 (America/Chicago). The owner approved one exact acquisition
of the eight ECE448 Spring 2022 public PDFs after the zero-network preflight.
Starting checkout was `main` at `6c02d6c`; pre-existing Lane 6 work, the
populated database volume, root `.env`, three attached private original PDFs,
old public heldout labels and disabled Ask gate were preserved.

The one-use approval was consumed once. The bounded acquisition fetched the
official schedule and eight fixed PDFs in **9 physical HTTPS GETs**, with no
retry or redirect, receiving **28,458,095 bytes** against the 13-GET and
84,410,368-byte caps. Every PDF passed the script's exact-page, signature,
unencrypted parse, first-page CC BY 4.0, size and extracted-text guards.
The new unlabeled manifest SHA-256 is
`6572395ae7234abdb790226940d0a104db153103d30f14ebb9d0a4e3118df72e`.
The artifact remains in exclusive OS Temp at
`C:\Users\eocim\AppData\Local\Temp\cardchemy-source-id-fresh-sp2022-v2`.

An independent local `verify_manifest` invocation then rehashed and reparsed
all eight PDFs and the schedule against the pinned prior public source
metadata; it returned `verified_unlabeled`, eight documents and the same
manifest hash. PDF parsing emitted public-source object warnings to a separate
Temp stderr receipt, but the bounded parse and verification succeeded.
No old question/label file was opened for the comparison. The prior 14-PDF
Spring 2020 manifest and two reserved public PDF hashes were used only as
source metadata; exact PDF hashes did not collide.

This acquisition proves only file admission. Semantic slide reuse across years,
independent original-page/cue usefulness labels, question packet freezing,
new public model quality, private Knowledge transfer and Ask release remain
unverified. A separate blinded content-overlap review is required before any
new question authoring. The acquisition made no Gemini call or database write
and did not activate Ask.
