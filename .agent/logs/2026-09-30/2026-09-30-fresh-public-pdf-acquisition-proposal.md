# Fresh public PDF acquisition proposal for the source-ID candidate

Date: 2026-09-30 (America/Chicago). Starting checkout: `main` at `6c02d6c`.
The pre-existing Lane 6 working tree is preserved. This is an offline proposal
only: no PDF was downloaded, no old heldout label was opened, no provider or
database call was made, and Ask remains disabled. It does not authorize an
acquisition or a scored pilot.

## Candidate roster and preregistration

The root task independently read the official [Spring 2022 ECE448 lecture
schedule](https://courses.grainger.illinois.edu/ece448/sp2022/lectures.html)
and the PDF title pages. The eight proposed URLs are linked from that schedule
and their title pages state CC BY 4.0. Those observations are source screening,
not a local-byte or license-extraction check; the acquisition must repeat them
against the actual downloaded bytes. Lecture 10 lacks the title-page CC BY 4.0
declaration and is excluded.

| Proposed split | Exact PDF URL | Expected pages |
| --- | --- | ---: |
| Calibration | https://courses.grainger.illinois.edu/ece448/sp2022/slides/lec04.pdf | 32 |
| Calibration | https://courses.grainger.illinois.edu/ece448/sp2022/slides/lec05.pdf | 33 |
| Calibration | https://courses.grainger.illinois.edu/ece448/sp2022/slides/lec06.pdf | 40 |
| Calibration | https://courses.grainger.illinois.edu/ece448/sp2022/slides/lec07.pdf | 31 |
| Heldout | https://courses.grainger.illinois.edu/ece448/sp2022/slides/lec08.pdf | 46 |
| Heldout | https://courses.grainger.illinois.edu/ece448/sp2022/slides/lec09.pdf | 33 |
| Heldout | https://courses.grainger.illinois.edu/ece448/sp2022/slides/lec11.pdf | 27 |
| Heldout | https://courses.grainger.illinois.edu/ece448/sp2022/slides/lec13.pdf | 36 |

The proposed split is four whole PDFs per side, 278 expected pages total. Fix
this roster, split, corpus ID, page counts, acquisition limits and canonical
preregistration SHA-256 before a network run. Keep question templates,
candidate construction and independent page-plus-visible-cue reviews split
disjoint. Do not inspect heldout labels or score them before a frozen
calibration pass. A fresh public source set must not reuse the exposed 48-case
calibration or its unopened heldout as confirmation.

## Proposed one-use acquisition envelope

- One exact schedule URL plus eight exact PDF URLs; no discovery crawl, file
  substitution, retry, resume or second attempt under the same approval.
- At most **13 physical HTTPS GETs**, including the schedule and all redirects:
  nine expected successful fetches plus at most four redirects in aggregate.
  Permit at most two redirect hops for any one logical fetch. A missing or
  additional redirect beyond either cap stops the run.
- Require certificate validation and exact host
  `courses.grainger.illinois.edu` for every request and redirect. Reject HTTP,
  alternate hosts, credentials, explicit ports, query strings and fragments;
  redirect targets must still be the approved schedule or PDF path. Do not
  stream redirect bodies.
- Cap the schedule response body at **512 KiB**, each PDF at **10 MiB**, and
  aggregate received bodies at **80.5 MiB (84,410,368 bytes)**. Check streamed
  bytes even when `Content-Length` is absent or misleading. Use a 15-second
  connection timeout, 120-second read timeout and **30-minute whole-run**
  monotonic deadline. A failed transfer consumes its GET; do not replay it.
- Require every exact PDF link on the fetched official schedule, HTTP 200,
  `%PDF-` signature, a parseable unencrypted PDF and the exact expected page
  count above (also below a 60-page hard ceiling). Extract title-page text
  locally and require CC BY 4.0 there; a site-level statement, a CC BY 3.0
  page or an unchecked third-party-media notice cannot substitute. Require at
  least 1,500 alphanumeric extracted characters per PDF and at least
  `max(3, pages // 3)` pages with 40 such characters, as in the prior corpus
  guard. Attribution for embedded third-party media remains separate.
- Record SHA-256 and byte count of every accepted PDF and the fetched schedule,
  a canonical preregistration hash, page count, license-check result, exact
  URL, GET count, received bytes and elapsed time in a new manifest. Verify the
  files against that manifest independently before any review packet. Write
  only to a new OS-Temp directory with exclusive creation; a failure leaves a
  receipt and no usable manifest. Never overwrite or silently resume an old
  directory.

Correction recorded 2026-09-30: the earlier 96-group multi-PDF public pilot
used the verified fourteen-PDF ECE448 Spring 2020 v4 corpus. A claimed
eight-PDF CS447 comparison manifest could not be substantiated in repository
logs or the local artifact inventory and is not an acquisition prerequisite.
URL distinction alone does not prove content independence. Before the new
corpus can be used, compare its PDF hashes against the verified ECE448 Spring
2020 v4 corpus manifest and the two reserved Illinois PDFs using source
metadata only; stop on an exact duplicate or missing verified comparison
metadata. Because slides may be reused across years, also perform a blinded
content-overlap review before writing questions. This check must not read any
old heldout labels or turn title-page screening into a quality claim. Actual
new PDF bytes and hashes are still unknown.

## Reuse decision and next gate

[`acquire_reading_usefulness_corpus.py`](../../../scripts/acquire_reading_usefulness_corpus.py)
is bound to ECE448 Spring 2020, fourteen documents, 6/4/4 train/calibration/
heldout counts, its v3 corpus ID and fixture targets. Calling it unchanged
would fetch the wrong corpus. Its manual redirect, streamed-byte, PDF/license,
exclusive-output and manifest patterns can inform a **new separately versioned
eight-document acquisition tool**, with fake-transport/keyless tests for the
exact roster, URL/redirect caps, byte/time stops, hash and page/license
rejection, source-disjoint comparison and failure receipt. The source script's
consumers and old frozen fixtures must remain unchanged.

Only after a separate bounded acquisition approval should the tool download
these PDFs. Acquisition alone yields unlabeled source material. Independent
page-and-cue review, frozen candidate/prompt/parser/model/scoring contract and
a separately authorized bounded Gemini evaluation are later gates. A public
calibration miss leaves heldout sealed. Private Knowledge transfer, runtime
model/policy selection and Ask activation remain separate release decisions
under ADR-024 and the Lane 6 plan.

## Checks and limits

Read-only inspection covered repository guidance, ADR-024, the Lane 6 plan,
the prior acquisition script and dated corpus evidence. No network preflight,
file acquisition, semantic deduplication or PDF-byte validation ran in this
task. The proposed numerical bounds and split remain unapproved until they
are frozen and the owner grants a separate acquisition envelope.
