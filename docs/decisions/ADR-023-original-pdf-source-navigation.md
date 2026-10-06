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

Originally accepted on 2026-09-27. The source-only, original-PDF and
immutable history rationale below remains accepted; ADR-024 supersedes only
the remote-judge/history-transfer prohibition with its bounded exceptions.
Original approval/trial chronology is retained in [dated logs](../../.agent/logs/README.md)
and the [pre-cleanup decision](https://github.com/EoCiMrEo/Cardchemy/blob/61b34ebda127b712bf22e36f84fb393f1343f707/docs/decisions/ADR-023-original-pdf-source-navigation.md).

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
- The operator initially selected 90% on 2026-09-28; the accepted ADR-024
  amendment sets the current target to **at least 80%** across every displayed
  card in complete independent original-PDF review. Publish the useful
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
  The retained local release passed on 2026-10-04; each future installation
  and source change still requires its applicable evidence before enablement.

The separately approved local ranking/selective/groupwise candidates did
not pass their frozen calibration gates and are retired. Their failures,
consumed ledgers and historical 90%/cardinality requirements remain in the
dated logs and pre-cleanup decision linked above. [ADR-024](ADR-024-gemini-source-id-judge.md)
records the bounded source-judgment successor and current accepted 80% floor;
the historical pilots were never retroactively regraded.

## Related areas

[ADR-012](ADR-012-subject-knowledge-and-rag-boundaries.md),
[ADR-021](ADR-021-related-knowledge-excerpts.md),
[ADR-022](ADR-022-related-knowledge-primary-ask.md),
[ADR-024](ADR-024-gemini-source-id-judge.md),
[product-quality plan](../archive/PRODUCT-QUALITY-REMEDIATION-PLAN.md),
[Knowledge flow](../architecture/SUBJECT-KNOWLEDGE-FLOW.md),
[privacy](../security/PRIVACY.md),
[database operations](../database/DATABASE_OPERATIONS.md),
[RAG evaluation](../ai/RAG_EVALUATION.md).
