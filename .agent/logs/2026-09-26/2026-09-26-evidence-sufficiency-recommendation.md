# Source-only Ask evidence-sufficiency recommendation

## Authority and current boundary

The operator requested relation-aware retrieval, source sufficiency ranking,
neighbor-page expansion, structure preservation and hard-negative evaluation.
The operator then explicitly reaffirmed **source-only**: no answer generation
or answer-claim verifier. This recommendation concerns how well published
passages let a learner investigate the question. It authorizes no provider
spending, runtime activation, new model download or plan change by itself.

Existing source-only implementation is running with Ask off at verified
`20260926_0023`; its private quality gate has not passed. All seven Lane 6
items remain tracked under the existing plan, with three checked. The owner
required approval before expanding the plan; the following extension is
proposed for that approval.

## Operator architecture reference

The latest supplied diagram reinforces the current boundary:

`Question -> Candidate Sources -> Evidence Sufficiency -> Gold Source`

Evaluate whether a passage contains the requested information type, explicitly
states the required relation and preserves enough context for a learner to
investigate the question. Do not draft an answer while choosing or evaluating
sources. The diagram's later answer/claim branch is reference material, not
authorization to restore the retired answer runtime. Reserve **gold source**
for independently reviewed evaluation evidence; a runtime ranking result is a
qualified source reference, not a guarantee of truth.

Record candidate-retrieval failure and sufficiency-selection failure separately.
An answer-generation/claim-verification stage is absent from this product path.

## Research references and applicability

- [Sufficient Context: A New Lens on Retrieval Augmented Generation Systems](https://arxiv.org/abs/2411.06037)
  (Joren et al., ICLR 2025) distinguishes insufficient retrieved context from a
  model failing to use sufficient context. It also distinguishes useful context
  from context that fully answers a question. This supports separate relevance
  and sufficiency labels; it does not validate our authored qualification rules
  or require adopting its answer-generation method.
- [Passage Re-ranking with BERT](https://arxiv.org/abs/1901.04085)
  (Nogueira and Cho) supplies a query-based passage reranking precedent. Its
  relevance objective alone does not establish evidence sufficiency, and citing
  it does not authorize adding BERT or another learned model to this runtime.
- [Google Research's explanation of sufficient context](https://research.google/blog/deeper-insights-into-retrieval-augmented-generation-the-role-of-sufficient-context/)
  provides the authors' accessible account of that distinction. It is background
  for the design, not local course-quality evidence.

The intent descriptor, neighbor bounds, exact-source contracts and proposed
gates below are project-specific engineering recommendations derived from
source inspection and owner review, not results claimed by these papers.

## Verified defects and evidence

- `related_evidence.local_followup_query` can resolve a short question to an
  acronym alone. The original request for expansion is lost for qualification.
- `select_source_first_excerpts` ranks overlapping terms in the top five
  chunks, not the entity-specific relation requested by the question.
- The gold helper chose shortest keyword co-occurrences. Owner review approved
  four of twelve proposed pairs; all thirteen larger alternatives across eight
  rejected cases were No for excerpt and page usefulness. The owner confirmed
  correct file/page identity but unhelpful content. These are exact rejected
  question/source pairs, not corpus-wide unsupported questions or observed
  runtime retrieval misses. The four Yes labels establish usefulness, not
  automatically sufficient evidence for a complete answer.
- Current references are offsets in one existing chunk. At most three distinct
  pages and 480 characters per excerpt are permitted. Whole-page, cross-chunk
  or cross-page stitched quotes cannot be assigned a convenient chunk ID.
- Chunking already detects pages/headings/paragraphs, but removes heading-only
  units and flattens oversized text. A representation change affects indexing
  and shared generation preparation; it needs explicit versioning/reindex.

Independent read-only subagents reviewed selector, neighbor SQL, reference
contracts, chunking and evaluation labels. No private text was printed or
provider called during those audits.

## Proposed ordered implementation

### 1. Preserve question relation

Create a local versioned query descriptor with the original question, resolved
entity, relation (acronym expansion, definition, mechanism, measurement,
reason, process or unknown), qualifiers and ambiguity. History may resolve an
entity but cannot remove the current relation or qualifier. Multiple plausible
referents require clarification, without a remote call. Only the original
current question is embedded once; the descriptor/history remain local.

### 2. Qualify and rerank source units

Keep the existing exact semantic plus PostgreSQL lexical candidate foundation.
PostgreSQL FTS is not BM25; adding a BM25 extension is not part of this minimum
change. Give the source-only policy an explicit bounded candidate stage before
the current top-five/display slicing discards material.

Inspect complete source sentences or unambiguous heading/bullet units. Bind the
requested entity to the requested relation and preserve required qualifiers:

| Relation | Explicit candidate cue | Insufficient candidate |
| --- | --- | --- |
| Acronym expansion | Complete expansion explicitly bound to that acronym | Mere mention, partial expansion or another acronym's expansion |
| Definition | Entity-bound explanatory predicate or scoped definition unit | Topic list, discussion heading or application alone |
| Mechanism | Entity-bound action explaining operation | Benefit, output or application alone |
| Measurement | Entity bound to what is measured/compared | Metric name without its measurement, another metric's predicate |
| Reason | Relevant property linked to a causal statement | Nearby unrelated causal phrase or inferred cause |
| Process | Complete scoped steps/transformation | Numbered list without matching entity or isolated step |

Reject predicate borrowing across entities/sections and incomplete required
qualifiers. Negation, conditions, comparisons, formulas and mixed requests need
dedicated controls. Unknown or malformed relations remain uncertain.

Use internal **explicit relation candidate / partial context / no matching
relation / ambiguous** statuses. If the implementation uses SUPPORTED/PARTIAL/
UNSUPPORTED names, define SUPPORTED strictly as passing this versioned source
qualification, never semantic truth or a verified generated answer. Authored
rules are an initial source-navigation candidate; regexes cannot certify
general entailment. Do not restore the retired NLI/QA answer pipeline under a
new name. A future learned source reranker requires its own measured proposal.

Rank qualification and complete displayed context before semantic/lexical
scores. A high similarity score cannot compensate for a missing relation.
Expose a versioned Evidence Sufficiency Score only with documented component
meaning and public calibration; no arbitrary weights or truth-probability
claim. Measure relation qualification, entity binding and complete context
separately from relevance.

### 3. Bounded local neighbor expansion

When initial candidates have only partial context, inspect same-page sibling
chunks, then page -1/+1; allow -2/+2 only if still unresolved and within limits.
Proposed caps: thirty candidate chunks, twelve distinct candidate pages and
the existing 8,192-token local context ceiling. Final display stays at three
distinct pages, each one exact contiguous existing chunk slice of at most
480 characters. These are maximums, not a mandate to show weak candidates.

Neighbor SQL must revalidate server-issued anchor IDs through the eligibility
view and repeat principal, Subject ownership/enrollment, selected documents,
review/publication, current content/index/corpus revision, readiness and active
embedding-space predicates. Neighbor and anchor share the same document and
revision/space. Record neighbor origin/distance; never inherit an anchor's
vector score as if its neighbor were embedded/retrieved at that score.

No recursive expansion, extra query embedding, remote reranker, answer call or
automatic retry is permitted. Reauthorize references at atomic commit and all
reads. An unpublish/reindex/access change invalidates the entire bundle.

### 4. Preserve structure only if measurement identifies lost context

First evaluate the earlier changes against existing canonical text/chunks.
If a needed relation is omitted or split, create a separately versioned
structure-preserving representation with headings, bullet/formula/example
boundaries and canonical page offsets. Stage canonical-page reindex and
measure before cutover; do not rewrite vectors or alter the generation-shared
chunker silently. Any remote reindex needs separate explicit bounded cost
approval. Do not invent absent mathematical text or infer facts from image
layout. No claim-level generated-answer verification belongs in this phase.

## Product and persisted contracts

- Primary references require a qualified complete source unit. Partial context
  triggers bounded local expansion, not another model request.
- When the bounded search cannot qualify a useful sufficient unit, say the
  search found no sufficiently clear excerpt for this question. Do not claim
  the whole published corpus lacks an answer. Keep this outcome distinct from
  provider failure and unresolved-reference clarification.
- Preserve exact sourced display, page links and existing learning-oriented
  disclosure; no generated answer or unsupported claim is attached to a quote.
- Snapshot new immutable retrieval/selection identities. Do not execute old
  queued policy snapshots using changed selection semantics. If a new Ask
  policy identifier is required, extend source-only DB guards in a new
  migration, including the 0023 parent-stage trigger, rather than rewriting
  used migrations or leaving a request-cap loophole.

## Measurement before activation

Retain original reviews and versions. The exposed reviewed pairs become
development examples once used to design the new selector; exact rejected
question/window pairs are hard negatives, not negative whole questions.
Private evidence remains outside tracked fixtures, logs and CI. Human labels
distinguish exact source fidelity, relevance, sufficient displayed context,
page usefulness and uncertainty.

Freeze public relation/adversarial rules before an independently reviewed
private holdout. Preserve the maintained recall/MRR and v1 displayed-window
thresholds; do not replace twelve independent holdout positives with the four
reviewed useful development examples. Author new questions from actual source
content before runtime measurement, covering direct/paraphrase/follow-up
relations and retaining distinct-page/document constraints. Unknown/unreviewed
results cannot pass.

Proposed additional gate, to freeze before any candidate measurement: at least
twelve independently reviewed insufficient question/source pairs, with at
least two covering each of the six declared relations, must have **zero false
primary qualifications**. Pair these with independently reviewed sufficient
source units so refusing every candidate cannot pass. On the new twelve-case
positive holdout require sufficient, useful, exact, currently authorized and
openable displayed hit@3 on at least ten cases and at least three of four in
each direct/paraphrase/follow-up group. Every displayed primary reference must
have a conclusive Yes for its requested relation and complete context; unknown
or partial context cannot be called sufficient. Keep the existing first-window,
relevance, maintained retrieval and access thresholds in addition to this
gate. These sample gates are release evidence, not population-wide correctness
guarantees. The reviewed development negatives are separate regression cases.

Required negatives include same entity/wrong relation, right relation/wrong
entity, heading-only mention, partial acronym, missing qualifier, negation,
unrelated steps, split units and inaccessible/stale/other-document neighbors.
Measure initial recall/rank, sufficient displayed hit@3, incomplete/irrelevant
selection, no-source/clarification, neighbor cost/latency, exact offsets and
actual current page opening separately. Keep one embedding and zero answer/
verifier/automatic retries. Fresh detailed live approval is required before
any private query-embedding measurement.

This proposal does not mark a Lane 6 checkbox complete or enable Ask.

## Proposal review and verification

A bounded independent source/contract audit found the proposal suitable for
plan/ADR approval, with no material defect. The additional false-qualification
gate above is now concrete rather than an unspecified future threshold. The
owner approval request covers the plan/ADR extension and ordered implementation
behind the closed release fence; provider spending and remote reindex remain
separately guarded. The operator approved the specific plan/ADR extension
and ordered implementation while retaining the closed Ask fence. No approval
was given for a paid request or reindex. Plan and ADR-022 were updated here.

`python scripts/check_context.py` passed: 37 required files, 77 active guides,
1,258 local links. This is documentation/navigation validation, not retrieval
quality or a live-provider result. Existing source-only runtime is unchanged.
