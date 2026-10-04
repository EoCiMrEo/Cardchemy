# Public reading-usefulness v4 blind-review progress

Date: 2026-09-28. Branch `main` at `6c02d6c`. This continues the single
approved networkless public Mixedbread audit preparation. No model inference,
Gemini request, new public GET, private Knowledge read, retained database
write, or Ask enablement occurred. The populated volume, root `.env` and
original private PDFs remain unchanged.

## Source and review packets

The final train author-only draft in OS Temp has SHA-256
`122f6a262a27b68bafcb2cc6cfebfd36b5df7358353980aecbe59475dd6a32a1`;
the calibration/heldout author-only draft has SHA-256
`0c1c5f659a4e2e8cc667e4d2930ba509e12618845eb098de2d80ff6b8915aef6`.
Separate v2 blind packets with random opaque IDs have SHA-256
`97e759f4ec37dac757477392d4c5834cdefe8eeea4b19e48dc123cc8a092c641`
for train and
`b816506dadf85ceb97bac5b48c2e8d0f57358e97c5ccd515f02ab69c35895437`
for calibration/heldout. The author mapping files are separate from all
reviewers; neither the provisional labels nor the mapping were provided to
them. The two final author drafts have 192 groups, 768 exact windows and the
registered split/useful-count balances. All source offsets and page hashes
match the locally pinned PDFs. The validator's twelve-token selected-window
and selected-page cross-split checks passed; exact cross-split question and
template duplicates were absent. A lightweight lexical question screen found
thirteen pairs sharing at least 0.2 non-stopword Jaccard overlap, and sampled
high-overlap pairs involved different concepts. This is not yet the independent
semantic-leakage attestation.

## Independent review status

Two separate reviewers completed all 384 calibration/heldout blind
judgments. Review A SHA-256 is
`0b01c448d70df3c0dd3c016e69293f5f024ea9d4f90d863b75f007f33994b552`;
review B is
`a42d41f2a67ac2061000112929e2bd05852dd8b4bd0ad0ffecb6898d8aa1cf0e`.
The comparator validated identity and reported 357 agreements, 14
disagreements, 22 uncertain judgments and 27 distinct candidates requiring
adjudication. An independent adjudicator inspected the relevant original PDF
pages and exact cues and resolved all 27; receipt SHA-256 is
`20e51aad6cc736ea2c57f52f977e74eae891e68673896cc776b1656661716059`.
Positive labels mean the page/cue helps a student investigate the question;
some provide partial context and do not establish a complete answer. This
matches source-only navigation, not answer certification.

Two separate reviewers also completed all 384 train blind judgments. Review
A SHA-256 is
`e293039bc9032ce03870e85ee7766530de28b72333ff0e8674f9b3a946b87fc2`;
review B is
`db060e4610d729876716f7681fafa1a04aae79bdad722f5e7cb2e710c9c6979c`.
The comparator reported 342 agreements, 27 disagreements, 36 uncertain
judgments and 42 distinct candidates requiring separate adjudication. That
adjudication remains in progress. No author-proposed label was promoted to a
reviewed fixture or used to score a model.

## Rights precheck and limitations

A source-only OS-Temp precheck revalidated all 768 exact text offsets and
identified 207 cues on pages that also contain raster images. No selected
text cue contains an explicit third-party rights marker. The canonical
first-page notice expression matched all 14 PDFs. An initial diagnostic
mistakenly used a regex that omitted `CC-BY`; its 0/14 result was corrected
in a new immutable precheck receipt. Corrected receipt SHA-256 is
`ac53f7c36da5a4540460c1c8040a7ff8b7412fbc72ddb08443dfec73a723b88f`.
This is **not** a candidate-level rights attestation: the final fixture may
copy exact slide text with attribution, but no figures, images, rendered PDF
pages or other separately credited media enter a tracked fixture. Independent
candidate and document rights review remains required before freezing.

## Offline regression

The first full backend offline run had 2,172 passes, 147 skips, two live-test
deselections and one failure in the PDF-child log-redaction test. That test
passed in isolation and as a whole module. It had relied on inherited pypdf
logger level, which other tests can change. The test now pins its own warning
level and enabled state before asserting sanitization. The full backend suite
then passed **2,173 tests**, with 147 skips and two deselections, in 162.42
seconds. This is offline proof; skipped service/live tests do not establish
PostgreSQL, browser or paid-provider success. The retained Compose services
were inspected read-only and were all running/healthy. Ask admission remains
disabled by policy; this service-health check alone is not a quality gate.

## Next gates

Finish independent train adjudication. Assemble labels only from two blind
reviews and required adjudication, obtain genuine per-candidate rights and
semantic split attestations, validate and freeze exact fixture and runtime
hashes, then use the one approved one-shot networkless audit if all admission
checks pass. Public model quality, separate private original-PDF release
holdout, any paid embedding/index call, enrolled browser page-open check,
spoken assistive-technology check and representative sparse whole-source
flashcard yield remain unproven. Lane 6 remains 3/7; Ask stays disabled.

## Later review closure and admission stop (2026-09-28)

The separate train adjudicator subsequently resolved all 42 required train
candidate judgments. Its OS-Temp receipt has SHA-256
`dc106cef6ceb627b2567481cb367e43c2730e7c5314c2cefa5e4962b73a040f7`.
These judgments supersede the earlier "in progress" status above; no model
score has been computed. Deriving labels from both blind reviews and required
adjudications gives actual useful-page/cue counts by group of 0/1/2/3/4:
train `15/27/24/23/7`, calibration `12/12/9/15/0`, heldout
`12/9/15/12/0`. The registered fixture requires train `24/24/24/24/0` and
calibration and heldout `12/12/12/12/0` each. Seven train groups also exceed
the validator's maximum of three useful candidates. The exact-label assembler
correctly refuses to prepare this fixture; author-proposed labels must not be
substituted for the independent judgments.

A content-free design repair list was written to OS Temp with SHA-256
`bdf5368dc26d4f8d1a9fde4bab41686c276634c3ce597f2e921d2731c857b50d`.
Its target counts are **proposals, not labels**. Any altered question/window
must receive a new independent blind review and adjudication before a fixture
can be admitted. No scoring, heldout tuning or quality claim may use the old
author draft. A separate rights preassessment has SHA-256
`02c1b508ca527c1988e934cbbbc7e460b93886808e618e8d9085b4644a57cfbd`:
14 first-page CC BY 4.0 notices and all 768 pypdf 6.19.0 spans checked, but
nine candidate pages in lecture 32 have cited third-party figures and three
of their cues may include diagram labels. Conservatively exclude those nine
pending independent resolution; this is **not** a final rights attestation.
An independent cross-split semantic review is also pending and has identified
a likely repeated absent-accuracy question pattern across calibration and
heldout, despite distinct exact templates. A passing exact-string check does
not cure semantic leakage.

The completed semantic preassessment has OS-Temp SHA-256
`1b52d3f3d73e6c193a996547a1b048dc1b0db7a3c0f22667a8ea98d5e5f94a85`.
It checked all 192 group identities, source separation and sixteen borderline
question pairs. Six questions in the calibration XOR and heldout image
accuracy triples request essentially the same missing validation metric;
they fail semantic split admission even though exact strings and selected
page/cue shingles do not overlap. No positive semantic receipt was issued.

An independent content-free count analysis proved at least 34 label-changing
candidate replacements are needed under the fixed strata: the reviewed train
set has 172 useful cues versus 144 required, and calibration and heldout each
have 75 versus 72. One candidate replacement can reduce the useful total by
at most one. The nine rights-excluded lecture-32 candidates are currently
non-useful and therefore add nine mandatory replacements, bringing the
minimum to 43. A distributed 34-replacement design can preserve each form's
positive-group count, but every proposed replacement needs new independent
review, and the six semantically overlapping questions need a source-disjoint
revision. These are pre-score fixture repairs, not model tuning.

The frontend scope check separately passed typecheck, lint, six unit tests,
59 component tests and coverage, build, and Chromium with 80 passing and one
opt-in live password-reset case skipped. Backend offline passed 2,173 with
147 skips and two live deselections as stated above. These checks do not
establish the public model-quality gate, retained-browser release gate, paid
provider behavior or manual spoken assistive-technology gate. At the retained
stack both API and Ask worker validated `rag_ask_enabled=false`; the services
were healthy at inspection. The audit one-shot marker has not been written.

## Candidate-only repair after the admission stop

Two independent authors prepared new OS-Temp **author-only** drafts while
preserving all original drafts, blind reviews and adjudications. The train
draft SHA-256 is
`c49e9d52238b4b2672401a24b625e5153c08faf270440c56c767a98a7a020ea7`:
it changes one exact candidate window in each of 28 groups and leaves their
questions/templates untouched. The calibration/heldout draft SHA-256 is
`9da036d5999aefb6c2e7fa9dc68a8984460aeefc1e31dbd1547d2f67658a373f`:
it changes six count candidates, nine candidates adjacent to third-party
figures, and rewrites a three-form absent-metric question topic to address
semantic leakage. Authors explicitly left changed labels unknown. Some train
replacements may still be useful reading context and must be judged as such;
the conditional target balance is no evidence of actual balance.

Separate new blinded packets omit author labels. Their SHA-256 values are
`804dd0d7eb4660fee80e6d24c160dcb3b86f1c78085ee7142120800b691bff8d`
(train) and
`7b84f08b1af580ab3e9fde61bbe6c83c12f7353eaa00a0698dff5bd4dbbbfa6a`
(calibration/heldout). The opaque mapping hashes are retained only in OS
Temp, separate from reviewers. A second read-only pass using the backend
`pypdf 6.19.0` confirmed all 768 windows are exact source offsets of at most
480 characters over 159 selected pages. Cross-split source, exact
question/template and twelve-token selected-page/cue guards passed. This
mechanical check does not clear semantic split overlap, candidate rights or
source usefulness. Two new independent blinded reviews are underway; no new
model score, provider call, database write, indexing or Ask activation has
occurred.
