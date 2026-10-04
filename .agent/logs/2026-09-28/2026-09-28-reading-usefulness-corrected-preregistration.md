# Reading-usefulness corpus: corrected preregistration

Date: 2026-09-28. The first bounded acquisition stopped after one official
schedule GET (10,495 received bytes) because its frozen roster contained PDF
numbers that the schedule did not link. It downloaded zero PDFs and produced no
labels or model scores. The failed receipt and output remain under OS Temp.
This correction changes only the local preregistration, not the approved model,
fixture targets, runtime policy, retained data or release gate.

## Source check and correction

Read the [official Illinois ECE448 lecture schedule](https://courses.grainger.illinois.edu/ece448/sp2020/lectures.html)
and verified every chosen PDF as an actual schedule link. The schedule has no
`lec13.pdf` or `lec23.pdf` link. The minimal source-disjoint correction is
train `13 → 11` and calibration `23 → 27`; both replacement PDFs show CC BY 4.0
on the first page. The corrected split is train `11,14,15,16,18,19`,
calibration `20,21,22,27`, heldout `25,26,36,38`. Separate release holdout
PDFs `17,37` remain excluded. The candidate URLs retain the official
`https://courses.grainger.illinois.edu/ece448/sp2020/slides/lecNN.pdf` pattern.
The official schedule links every corrected number; the full PDF bytes and
first-page notices for `20`, `21` and `36` still require the bounded download.

The local acquisition script's canonical preregistration SHA-256 is
`bef54089a3ef0ccd332c8dc8a07852c352e012bcb301b04ca9c72b742d8c48fb`.
It was verified by a no-network call to `preregistration()` and
`canonical_bytes()`. The earlier receipt's preregistration hash must not be
reused. No corrected-corpus GET, provider call, model inference, database write
or runtime change occurred in this step.

## Decision and remaining gate

The corrected acquisition needs its own explicit one-shot decision. The
proposed limits remain at most 18 document URLs, 24 GETs including redirects,
120 MiB received, 10 MiB and 100 pages per PDF, and 30 minutes total. The
acquirer fails on missing official links, non-PDF files, missing first-page
CC BY 4.0, low extracted-text quality or a bound breach. Use a new OS-Temp
output directory; do not resume or overwrite the failed receipt. Only after
all fourteen PDFs pass can independent authors/reviewers build and freeze the
192-group public fixture before any Mixedbread scoring. Ask stays disabled.
