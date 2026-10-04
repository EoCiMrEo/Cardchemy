# ADR-023: Original-PDF source navigation for Ask AI

## Status

Accepted; current implementation is v8/visual-v5/admission-v2 on retained
0033 under [ADR-024](ADR-024-gemini-source-id-judge.md).
Ask AI is enabled in the retained local installation (verified 2026-10-04); Lane 6 is **7/7 complete** after the separate
public/private/source-display and release evidence in
[the actual local closure](../../.agent/logs/2026-10-03/2026-10-03-lane6-final-closure-and-activation.md), with the operator-approved
80%-all-displayed-card floor and unchanged separate hit/no-match/access gates.
Fresh installations remain default-off. The source-only original-PDF,
unverified-reference and immutable historical-job contracts remain in force;
ADR-024's bounded ID-only text/PNG judgment and literal-subject admission are
the current limited exceptions to this decision's original zero-reranker/history
transfer wording. No answer generation/verifier is restored.

### Original acceptance and amendment chronology (historical)

Accepted by the operator on 2026-09-27 for product-quality Lane 6;
original-PDF navigation is implemented in the retained 0032 installation,
with Ask disabled pending independent quality and release evidence. See the
[current cutover/recheck](../../.agent/logs/2026-10-02/2026-10-02-v7-retained-cutover-and-release-recheck.md).
The operator approved
[the measured recommendation](../../.agent/logs/2026-09-27/2026-09-27-source-navigation-pdf-recommendation.md)
after the frozen v7 selector and one GTE audit failed their source-sufficiency
gates. Ask remains disabled until this decision's independent quality,
security, accessibility and operational gates pass. This decision authorizes
implementation and offline/disposable verification, **not** paid embedding,
Knowledge reindexing, runtime activation or deleting retained volumes.
The 2026-09-28 selective-navigation amendment approves one new public-only
offline audit after a separate Mixedbread calibration failure; it does not
approve a runtime selector or satisfy the release gate.
That audit also failed calibration. The subsequent operator-approved
groupwise audit is a distinct public-only candidate with a corrected
27-local-call cap; it likewise cannot change runtime or release status.
The later [ADR-024](ADR-024-gemini-source-id-judge.md) partially supersedes
this record's **zero remote reranker/source-text transfer** rule for a
prospective, separately gated `related_knowledge_navigation_v4` policy.
The original-PDF, source-only, access and measured usefulness contracts below
remain in force. No v4 runtime, paid call or private Knowledge transfer is
established by that decision; Ask is still off.

This supersedes [ADR-022](ADR-022-related-knowledge-primary-ask.md) in its
runtime requirement to classify a source as sufficient, to suppress all
related references when the classifier cannot prove a complete relation, and
in its extracted-text-only page viewer. Its source-only, exact-reference,
current-publication, revision, authorization, request-bound and historical-job
fences remain. It does not restore the answer generation or verification
retired from new Ask jobs by ADR-022.

## Context

The operator's goal is for students to read the lecture, not receive a
generated answer. After eleven reviewed published-source examples, the v7
selector still selected only 1/12 useful lecture windows with the correct
page supplied. An independent challenge selected 4/8 useful sources and
promoted 3/8 insufficient ones. A pinned GTE ModernBERT INT8 audit met
resource bounds but accepted 0/32 sufficient heldout windows at its frozen
calibration threshold. This proves the current source-sufficiency gate is not
release-ready. It does not prove that every model or real-query retrieval
fails; the measured gate and current PDFs are already exposed for tuning.

Knowledge stores extracted pages and vectors, while successful jobs delete
their temporary encrypted raw PDF. An exact extracted quote may omit slide
graphics, formulas or layout, and character offsets in extracted text are not
coordinates on the visual PDF page. The operator chose fully automatic,
explicitly **unverified** related references and an in-app original-PDF page
viewer. The desired result is two or three distinct useful page references
when available; one or none is correct when additional pages would be filler.

## Decision

### Learner-visible contract and immutable work policy

New work uses the immutable `related_knowledge_navigation_v3` policy. The
initial v2/v8 implementation remains readable, while migration `0028`
admits the corrected v3/v9 insertion pair without rewriting older jobs.
The release fence remains closed until useful-page and access gates pass. It
returns up to three distinct, currently published PDF page references, each
with an exact bounded extracted-text cue when one exists. Every card says it
is related reading, **not a verified answer or sufficient evidence**. It
never drafts an answer, attaches a claim citation or labels a ranking score
as evidence proof. When no useful page is identified, it shows a distinct
no-useful-match state plus authorized Subject Knowledge browse/search; when a
question's follow-up referent is unresolved, it asks for a clearer question.
No weak page is added solely to reach two or three.
An independent enrolled-student browse/search route exposes current reviewed,
published lecture pages and authorized original-PDF ranges while Ask is off
or returns no match. It is source navigation, not an answer assertion.

The worker may send the current question to the configured query embedding
endpoint at most once per durable attempt, with zero answer-model/verifier
calls and zero automatic provider retries. It retains exact-vector plus
PostgreSQL full-text candidate search and can use bounded **local lexical
search** if the query embedding is unavailable. That fallback must report the
provider failure separately from a genuine no-useful-match, and never issue
another remote request. Ranking can use entity/relation/qualifier, slide
structure and nearby pages as signals, but must not silently present a
candidate as verified or stop nearby inspection merely because an initial
same-topic candidate was found. Private history stays local; an unresolved
referent does not cause an external history transfer.

Existing source-only records and retired answer-policy records keep their
immutable snapshots and read rules. A new Alembic revision must admit only
the new source-only policy and its valid stages/outcomes without converting
queued older jobs to it. Store at most three atomic job-owned references with
current content/index/corpus revision, space, exact offsets and expiry. All
SQL candidate paths and every result/PDF read recheck owner or enrollment,
selected documents, publication, readiness, active revisions and embedding
space. Any invalid member hides the complete reference bundle. The PDF is
never a public static asset.

### Immutable original-PDF archive and viewer

For new Knowledge revisions, retain the validated original upload as a
durable, AEAD-encrypted archive bound to the immutable content revision and
source SHA-256. It is separate from the short-lived generation-job source and
uses a separately versioned key, revision-bound authenticated data, bounded
bytes/quota accounting, foreign-key cascades, deletion and recovery rules.
Capture is fenced with canonical pages and must not create a partially
published archive. Serve bounded byte ranges after full current-access and
reference-bundle checks; never decrypt whole configured-maximum PDFs on the
API event loop. Responses use no-store and safe PDF/content headers.

Old published revisions cannot reconstruct original bytes. An instructor
may attach a PDF only when its exact SHA-256 and page count match the active
content revision; this must not create a new Knowledge revision, remote index
request or provider cost. If unavailable, the UI clearly marks the original
PDF missing and may show the already-authorized extracted page instead.

Use a lazy in-app PDF.js canvas/text-layer viewer with authenticated requests
and page navigation to the physical 1-based PDF page. Keep the existing CSP
that forbids iframe/object embedding. Show any exact extracted quote adjacent
to the page; do not claim a visual highlight until reliable PDF coordinates
exist. Maintain keyboard, focus, screen-reader text, reduced-motion and
mobile behavior. Permanent PDF storage changes privacy, backup, key rotation,
operator quotas and export/deletion disclosures.

## Rationale

The previously attempted grammars and generic reranker tried to turn
semantic relatedness into an unverified sufficiency claim. The student
learning objective needs useful source navigation and visible uncertainty.
Opening the original page restores diagrams/layout that text extraction may
lose. The local lexical fallback removes the answer-provider dependency and
gives a bounded way to search when embedding transport fails. This decision
does **not** promise that any fully automatic method will find answer-sufficient
pages for every arbitrary question or every PDF.

## Consequences and release gate

- Freeze a stagewise diagnostic: PDF fidelity and extraction coverage,
  eligible source/index coverage, SQL candidate recall, nearby-page pool,
  final displayed page/quote and original-PDF open. Run oracle-gold-page and
  real-query conditions separately. Current reviewed positives and the prior
  synthetic model packet are exposed regression evidence, not a fresh holdout.
- Independently review original PDFs for a new document/source-separated
  12-case direct/paraphrase/follow-up holdout. Require useful-page hit@3 at
  least 10/12 overall and 3/4 in each group; the exposed eleven-positive
  regression must reach at least 10/11. Measure top-one rank and every shown
  card, not just whether one of three is useful. Wrong-owner/condition,
  no-source, ambiguous follow-up, embedding outage/lexical fallback and
  unavailable-original controls must be explicit.
- The operator set the final displayed-card usefulness target to **at least
  90%** on independent original-PDF review (2026-09-28). Publish the useful
  card count and total shown; uncertain cards fail. Report question-level
  hit@3 and no-match coverage separately so displaying no references cannot
  meet this target. This is measured navigation quality, not a promise of
  perfect answers or support from every arbitrary lecture.
- Reject any fabricated quote, unsupported answer assertion, incorrect PDF
  hash/page, unauthorized/private/stale read, partial reference bundle,
  extra provider request or misleading verified-evidence label. Preserve
  maintained retrieval, race/idempotency, migration, deletion, quota, exact
  source and accessibility gates. A navigation-quality failure keeps Ask off.
- Complete backend offline and guarded PostgreSQL migration/transaction/
  authorization tests, deterministic cross-stack journey, frontend check,
  source viewer keyboard and spoken assistive-technology review, context and
  runtime/security checks. Drain writers/workers, verify backup and key
  recovery, migrate, reattach exact legacy PDFs, verify current images/head
  and rollback safely before self-hosted activation.
- Provider/indexing/live-query tests need a new explicit endpoint, model,
  price, call, token, time and cost envelope. This ADR does not authorize one.
  The release status and corresponding Lane 6 boxes remain open until all
  evidence exists.

### One-shot local ranking feasibility audit

The owner approved one additional **offline experiment**, not a runtime
component or release. The prior GTE INT8 audit's absolute cutoff selected
0/32 useful heldout passages; it did not establish relative ordering within
each question. The current navigation diagnostic finds a useful page within
three for 11/12 unseen-PDF questions but only 18/36 displayed cards useful.
Reuse the already verified public GTE bundle without network or application
data to test within-question ordering and whether a calibrated cardinality
rule stops before weak filler. Freeze 32 public eight-family groups with one
useful and three same-topic insufficient windows each, separate no-useful
groups, source/template-disjoint calibration and heldout, hashes and a single
calibration-only rule before scoring heldout once. Public success requires
14/16 useful top-one and hit@3, at least 90% useful displayed cards and zero
weak primary for no-useful groups. Unknowns fail. Four CPUs, 2 GiB added RAM,
20 s startup, p95 5 s/30 windows and 600 s total are hard experiment bounds.
Failing any bound or quality measure ends this candidate without a private
rescue, a second model or a policy switch. Even a public pass only admits
separate development and fresh document-separated private evaluation; the
existing PDF-open, real-query, access, accessibility and operational release
gates remain mandatory. The model score is never represented as verified
answer sufficiency. See the [Lane 6 plan](../development/PRODUCT-QUALITY-REMEDIATION-PLAN.md)
and [approved proposal](../../.agent/logs/2026-09-27/2026-09-27-navigation-listwise-feasibility-recommendation.md).

The one approved networkless public audit passed its resource bounds but
failed the frozen display rule: raw heldout useful top-one was 15/16, while
the rule displayed 0/16 useful pages. This candidate was stopped without
private rescue or integration. The navigation usefulness release gate is
still open, so Ask remains disabled.

### Selective-navigation amendment and one public audit

The later [Mixedbread one-shot audit](../../.agent/logs/2026-09-28/2026-09-28-reading-usefulness-frozen-audit.md)
also passed resource bounds but stopped at `calibration_rejected_no_heldout`.
Its old ledger is consumed and heldout was not opened. Raw pair-logit top
three held at least one useful cue/page in all 36 positive calibration groups
and 68/72 available useful cues. The train-only pointwise classifier with one
global display threshold found no calibration rule satisfying the no-useful,
card usefulness and hit guards. Its zero displayed cards is a rejection
sentinel. The exposed v3/v9 selector independently showed a useful page on
11/11 questions but only 19/33 displayed original-PDF pages were useful.
These measurements support trying selective display; neither is release
evidence or authority to repeat the consumed audit.

The operator approved [one new public-only candidate](../../.agent/logs/2026-09-28/2026-09-28-selective-source-navigation-recommendation.md).
Keep the learner-visible contract: at most three exact, unverified,
currently authorized original-PDF page references, with no generated answer.
The candidate tests two separate local decisions after existing authorized
hybrid retrieval and bounded neighboring-page inspection: a question-level
null/any-useful decision for the inspected pool, and per-card qualification
of each distinct page with its best exact visible cue (at most 480
characters). Rank and show only individually qualified pages: zero through
three, including two or three when that many qualify. Never add a weak page
to fill the display. Unknown, unresolved follow-up, contradictory or stale
source, and scorer failure cannot be reported as a confident match;
unavailable and genuine no-useful-match remain distinct. Model scores do not
prove answer sufficiency. Any later runtime adoption requires its own
immutable policy snapshot and migration/compatibility review; this audit
does not alter `related_knowledge_navigation_v3` or enable Ask.

Reuse the already hash-verified public Mixedbread scorer, fourteen CC BY 4.0
PDFs and 192 independently reviewed groups: 96 train, 48 calibration and
48 still-blind heldout. Treat exposed train/calibration aggregates as
development data. Before scoring, freeze the exact fixture, pooled score/
lexical/relation features,
fixed train-only binary null and separate per-card classifiers, deterministic
search allowing at most one null and one card threshold, harness, Docker
image and scripts, with a freeze digest outside the attempt folder. Use a
new fixed one-shot ledger; do not clear or reuse the old ledger. Calibration
must have zero displays in twelve no-useful groups, at least 90% useful
combined cue-plus-page cards among every displayed card, and useful hit@3
in at least 30/36 positive groups. Open heldout only after that pass, once.
The existing public heldout gate remains: useful hit@3 at least 33/36 and
10/12 per question form; useful first card at least 31/36; at least 90% of
all displayed cue-plus-page cards useful; at least 60/72 available useful
cards shown; correct display count in at least 10/12 of each one/two/three-
useful stratum; and zero displays in twelve no-useful groups. Report raw
pool, null/card confusion, original-page versus exact-cue usefulness,
displayed numerator and denominator, no-match and first-card errors, and
resource use. Unknown or failed controls count as failure.

Run exactly one audit in a disposable networkless, credential-free Docker
container with the cached immutable image/model and no retained database or
private mounts. Hard limits are four CPUs, 2 GiB RAM, 20 seconds startup,
p95 five seconds per 30 windows, 256 pair tokens without silent truncation,
and 600 seconds total including preflight and cleanup. Make no download,
provider request, database write or private-Knowledge read. A calibration
failure leaves heldout unscored; a heldout or resource failure ends the
candidate without retry, private rescue or threshold tuning. A public pass
allows only separately reviewed development work. Release still requires
the fresh published, document-separated original-PDF holdout with at least
90% useful **original PDF pages among all displayed cards**, the unchanged
10/12 overall and 3/4-per-form page hit@3 gates, exposed regression 10/11,
and no-match, access, PDF-open, spoken assistive-technology and operational
checks above. Paid query/index evidence requires a new explicit envelope.
Ask remains disabled and Lane 6 checkboxes remain open.

The separately approved selective audit later stopped at
`calibration_rejected_no_heldout` after its fixed train-only question-null
and per-card classifiers found no threshold pair meeting the public
no-useful, displayed-card and positive-hit calibration guards. The raw
pair-logit top three still contained a useful cue/page in 36/36 positive
calibration groups. The run passed resource bounds and made no provider or
database requests; the heldout was not scored and the one-shot ledger is
consumed. [Its frozen record](../../.agent/logs/2026-09-28/2026-09-28-selective-navigation-frozen-audit.md)
is a failed candidate, not a new runtime policy or permission to retune.
The earlier published hybrid result found a useful page for 11/11 exposed
questions but only 19/33 displayed pages were useful, so current evidence
directs the next diagnosis to selection and no-match. Extra vectors from
variants of the current question remain a conditional future proposal only
if an independent real-query funnel first proves candidate misses; it would
need a separate policy and cost approval.

### Groupwise source-cardinality amendment and one public audit

The owner approved [one additional groupwise audit](../../.agent/logs/2026-09-28/2026-09-28-groupwise-source-cardinality-recommendation.md)
after both prior Mixedbread one-shot audits stopped at calibration with their
heldout sets unscored and ledgers consumed. This tests a **different local
decision rule**, not a retry or recalibration of those failed candidates.
The published-course 11-question diagnostic and public raw top-three result
point to candidate display/cardinality as the measured next bottleneck; they
do not establish useful candidate recall on the new independent PDFs.

The public-only candidate scores four distinct-page cues per question with
the same cached, hash-verified Mixedbread pair model. Each public group has
four pages from one PDF; this does not establish fidelity to the runtime pool
of up to 30 chunks/12 pages, potentially across PDFs. On 96 train groups
the candidate fits predeclared regularized card utility and four-way
`0/1/2/3` count heads using a fixed shallow nonlinear feature transform.
The public count label requires **both** a useful exact visible cue and a
useful original PDF page. The count decision sets a maximum, including zero;
each page must also pass an individual utility/risk gate. A high relative
rank cannot fill an unsupported card slot. Only the
current question, locally resolved referent, exact cue/page structure,
bounded lexical/condition features and pair scores may be inference inputs;
split/document/reviewer identities and labels are excluded. Freeze features,
training, regularization, ties, the single conservative set-risk parameter
grid, fixture, scripts, model bundle and image before any score. The 48
calibration groups were exposed as development aggregates during two failed
audits; use them only for that one parameter, not as independent evidence.
Report a calibration-only aggregate precision/hit/no-match frontier if no
rule passes; zero displayed cards in a
rejected result is not a demonstrated safe policy.

The calibration gate remains zero displays in twelve no-useful groups, at
least 90% of displayed cards with **both** useful exact cue and useful
original page, and useful hit@3 in at least 30/36 positive groups. Only a
pass permits **one** score of the still-unused 48-group public heldout, the
independent public test for this frozen candidate. Its unchanged requirements
are useful hit@3 at least 33/36 and 10/12 per form, useful first at least
31/36, at
least 90% of all displayed cards with both useful cue and useful original
page, at least 60/72 available useful cards shown, correct count in at least
10/12 per one/two/three-useful stratum,
and zero displays in twelve no-useful groups. Unknown/failed controls fail.

Use a new exclusive one-shot attempt/child ledger; preserve both consumed
ledgers. At most 768 public question/cue pairs are scored in batches of at
most 30, for at most **27 local model calls**: 20 train/calibration and seven
heldout if admitted. The initial approval question incorrectly stated 26;
the owner separately authorized 30–50 local calls and this audit uses the
tighter corrected cap of 27. One disposable networkless Docker run uses the
cached image/model, no credentials/private Knowledge/retained database,
four CPUs, a 2 GiB memory/swap cap, startup at most 20 seconds, p95 at most
five seconds per 30 windows, at most 256 pair tokens without truncation and
600 seconds including preflight and cleanup. Keyless tests and no-score
freeze verification precede inference. Failure stops without retry, heldout
tuning, private rescue, integration or Ask activation; any further variant
needs new root-cause review and approval.

The learner-visible contract and independent release gate above do not
change. In particular Ask remains source-only and disabled, with at most
one current-question embedding and zero generated-answer/verifier calls;
the current 12-case private original-page gate across three attached,
published PDFs still needs at least 90%
useful **all displayed** cards, useful-page hit@3 at least 10/12 overall
and 3/4 per question form, exposed regression at least 10/11, plus access,
no-match, PDF-open, spoken accessibility and operational checks. A public
audit pass is feasibility evidence only. Query/document embeddings or
indexing for the release test require a fresh explicit paid envelope.
Multiple current-question embeddings remain only a conditional future
proposal if independent real-query measurement proves candidate recall is
insufficient, with separate policy, cost and quality approval.

The one approved groupwise run then stopped at
`calibration_rejected_no_heldout`: 20 local calls scored 576 train and
calibration pairs, with zero provider requests or database writes. The
validated fixture included heldout labels, but they were not scored or used
for training/calibration. No set-risk value met zero no-useful displays,
90% cue-plus-page usefulness among all displayed cards and positive useful
hit@3 at least 30/36 together. The aggregate calibration frontier illustrates
the conflict: risk `0.0` gave 30/37 useful hypothetical cards, a display in
five no-useful groups and 21/36 positive hits; risk `4.0` gave 7/7 useful
cards, zero no-useful displays and only 7/36 positive hits. Neither is a
selected policy. Raw pair-logit top three still contained a useful cue/page
in all 36 positive calibration groups. The resource limits passed, but the
candidate quality gate failed, the exclusive ledger is consumed, and the
heldout/release gate remains unmeasured. Do not rerun, retune or integrate
this candidate under the used approval. Ask remains disabled.

### Subsequent remote source-ID decision

After the three local one-shot display selectors failed calibration, the
operator accepted [ADR-024](ADR-024-gemini-source-id-judge.md) as the next
architecture direction. It allows at most one bounded `source_judgment`
request after the current-question embedding under a **new immutable**
policy. The request may rank only currently authorized canonical candidate
page text and return issued ephemeral IDs. It cannot generate answers,
citations or excerpts. The server still reconstructs exact original-PDF
references and rechecks the entire bundle. A public-only pilot, fresh
explicit paid-call envelope, later separately disclosed private-source
evaluation and the unchanged independent original-PDF usefulness and
security gates precede any Ask activation. The older v3 policy and consumed
local audit ledgers are unchanged.

## Related areas

[ADR-012](ADR-012-subject-knowledge-and-rag-boundaries.md),
[ADR-021](ADR-021-related-knowledge-excerpts.md),
[ADR-022](ADR-022-related-knowledge-primary-ask.md),
[ADR-024](ADR-024-gemini-source-id-judge.md),
[product-quality plan](../development/PRODUCT-QUALITY-REMEDIATION-PLAN.md),
[Knowledge flow](../architecture/SUBJECT-KNOWLEDGE-FLOW.md),
[privacy](../PRIVACY.md),
[database operations](../DATABASE_OPERATIONS.md),
[RAG evaluation](../RAG_EVALUATION.md).
