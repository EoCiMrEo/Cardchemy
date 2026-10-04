# Public reading-usefulness v3 corpus acquisition

Date: 2026-09-28. The operator separately approved one bounded v3 download
after the first roster lacked schedule links and the second contained a
lecture whose first-page license was CC BY 3.0. This record describes only
public corpus acquisition for the offline Mixedbread experiment; it does not
amend the Lane 6 release gate or activate Ask. Branch `main` at `6c02d6c`;
pre-existing changes, populated database, root `.env`, encrypted original
PDFs and Ask-off setting were preserved.

## Executed limits and independent verification

The frozen v3 preregistration SHA-256 was
`ee050f83d107c59cea09b2140f7cec81047684a9192d26ac7517a0753edfa881`.
One execution of `scripts/acquire_reading_usefulness_corpus.py` used a new
OS-Temp directory `cardchemy-reading-usefulness-public-v3-20260928`. It
completed with fourteen officially linked PDFs: six train, four calibration,
four heldout; separate Lane 6 release PDFs 17 and 37 were excluded. It used
**15 GETs including the schedule**, **51,901,603 received bytes**, within the
approved 24-GET/120-MiB/30-minute envelope. There was no retry.

The script checked PDF signature, at most 10 MiB and 100 pages per PDF,
first-page CC BY 4.0 text, usable extracted text, and recorded URL, file SHA,
page count and byte length. A separate local read recomputed all fourteen
file hashes, the preregistration binding and split counts. The manifest
SHA-256 is
`fb59c3df42d87b0305ce2fe403c779a6f9c4f583b1bedd7bcd77860d05cd61e7`.
Observed documents span 28–45 pages, maximum file size 10,327,823 bytes;
minimum alphanumeric extracted text is 6,786 characters and minimum pages
with at least forty alphanumeric characters is 26. `pypdf` emitted 533
public-PDF object warnings to a private Temp stderr receipt, but the bounded
license/text/manifest checks all passed. Exact candidate windows still need
independent page and extraction review; acquisition does not establish their
usefulness.

The manifest, PDFs and empty fixture plan are under OS Temp; no content or
model output was copied into tracked fixtures or logs. This step made **zero
Gemini or model-inference calls**, read no private Knowledge, wrote no
database records and left Ask disabled. The existing one-shot Mixedbread
artifact passed only load admission, not quality scoring.

## Next gate

Independently author, blind-review and freeze all 192 groups (96 train,
48 calibration, 48 heldout) with four exact page windows each, true useful
counts 0/1/2/3 and source/template-disjoint splits before the first score.
Unknown/weak labels do not become positives. Then run only the approved
networkless 4-CPU/2-GiB/600-second audit and its frozen calibration/heldout
gate. A public pass still requires a separate development decision and a
fresh release holdout; Ask remains disabled throughout.
