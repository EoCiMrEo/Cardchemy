# Source-ID calibration diagnosis and next candidate proposal

Date: 2026-09-30 (America/Chicago). Starting checkout: `main` at `6c02d6c`.
The existing in-progress Lane 6 working tree, populated local volume, root
`.env`, and three attached original PDFs are preserved. This is a proposal,
not approval to change the plan, run a provider call, send private Knowledge,
or enable Ask.

## Observed result and independent check

The one approved public Flash-Lite continuation made 37 new accepted calls.
Across the frozen 48-case calibration, 47/48 responses were accepted, useful
page hit@3 was 35/36, and 54/55 displayed cue-plus-original-PDF cards were
independently rated useful. One of twelve completed no-useful groups displayed
a page, so the zero-false-display calibration gate failed. The previous
timeout accounts for the sole positive hit miss. Only 20/36 positive groups
showed the exact available page count under the three-link cap; 54 useful
pages were displayed from 80 useful candidates in the four-page pools (76
could fit under the three-link cap). These are public calibration observations,
not private-course or independent heldout results.

An independent read-only score and ledger audit matched the recorded artifact
hashes and arithmetic. It found exactly 37 new unique claims for groups
12–48, no replay of group 11, and no heldout directory or score. All accepted
outputs passed the source-ID schema. The one false display was a same-topic,
high-word-overlap page whose exact cue and PDF page were both rated not useful
for the question. The existing prompt already warns that topical overlap is
insufficient. The observed problem is therefore a semantic source-selection
error rather than a demonstrated parser or scoring defect; the model's
internal reason is unknown. The 48-case different-PDF heldout remains sealed.

## Recommended bounded next candidate

Preserve source-only Ask: at most one current-question embedding, at most one
source-ID judgment, zero answer/verifier calls, zero automatic retries and
zero to three exact original-PDF links. Prototype a **new versioned ID-only
prompt and candidate presentation** that makes the requested entity,
relation and conditions explicit, asks for an independent decision about
each exact page **and its visible cue**, then returns every qualifying ID up
to three in useful reading order. It must return `[]` if no candidate carries
the needed information and must not fill a link quota, infer absent facts,
generate an answer, rationale, quote or citation. The server still validates
issued IDs and derives every reference from the current authorized source.
This is a hypothesis, not a claim that wording alone fixes the error; the
existing prompt already contains a weaker version of these directions.

Before any live evaluation, freeze the exact prompt, candidate presentation,
parser, version, model and scoring contract; run keyless malformed/foreign-ID,
no-match, multi-page, follow-up, injection and authorization tests. Construct
a **new disjoint public PDF** calibration and different-PDF heldout with
independently assessed page-and-cue usefulness, including strong same-topic
insufficient negatives and one/two/three-useful-card strata. Do not use the
exposed 48-case score as fresh confirmation. Preserve the existing
availability, useful-hit, at-least-90%-of-all-displayed, cardinality and
zero-false-no-useful gates. A public calibration miss stops that candidate;
heldout opens only after a frozen calibration pass. The current unopened
heldout is not evidence for this new candidate. Any public PDF acquisition
and paid Gemini trial require their own documented bounds and approval.

Only a passing independent public evaluation could justify proposing a
versioned runtime policy/model change and a separately approved, disclosed
private original-PDF release evaluation. The dormant v4 runtime remains pinned
to Gemini 3.8, Ask remains disabled, and Lane 6 remains 3/7. Authenticated
lecture browse/search remains available while source judging is gated.

## Verification and limits

Read-only checks: the independent score/ledger audit, separate calibration
error analysis and plan/source-contract review. No provider request, DB write,
heldout opening, runtime policy change or release claim was made for this
proposal. The completed pilot's safe aggregate and cost accounting remain in
the [result record](2026-09-30-flash-lite-failure-inclusive-calibration-result.md).
