# ADR-022: Source-first Ask AI with related published Knowledge

## Status

Accepted by the operator on 2026-09-26 as the **target architecture** for
product-quality Lane 6, then strengthened the same day: Ask AI must only guide
students to related published Knowledge. New Ask work never generates or
verifies an answer. The earlier source-only implementation runs on the local
stack at verified schema `20260926_0023` with Ask disabled. The current
relation/structure extension is being implemented in the checkout and remains
behind the release fence until the measured gate passes.

This record supersedes ADR-021 **only** where related excerpts are limited to
failed or abstained answer jobs and two displayed excerpts. It supersedes
[ADR-019](ADR-019-two-request-local-support-ask.md) as the only permitted
path for *new* Ask jobs after cutover. ADR-019 records historical execution
and data contracts; it does not authorize a future answer mode. The
ownership, publication, revision, embedding-space, privacy and history
boundaries of [ADR-012](ADR-012-subject-knowledge-and-rag-boundaries.md) remain.
Flashcard generation and its exact-count/card-validation decisions are separate.

**2026-09-27 supersession:** [ADR-023](ADR-023-original-pdf-source-navigation.md)
keeps this ADR's source-only, current-source and no-answer boundaries but
replaces its runtime sufficient-source admission and extracted-page-only
viewer with explicitly unverified related-page navigation and an encrypted
original-PDF viewer. The v3–v7 selectors and GTE audit below are historical
failed candidates, not gates to re-enable. New work must snapshot the v2
navigation policy and pass ADR-023's separate quality/release gates.

## Context

The owner confirmed eleven source-bound positive direct, paraphrase and
follow-up examples in published course Knowledge. Six current-policy positive
source/claim pairs were rejected by the local verifier. One live Ask attempt
separately failed at the answer provider; another retrieved relevant BLEU
material but its short quote omitted necessary context before support was
rejected. A six-query real-embedding diagnostic found target pages at ranks
2, 3, 1, 1, 3 and 1: top-five page recall was 1.0, but MRR was 0.6944 and
the two-excerpt fallback can miss rank-three targets. Page rank does not prove
that a displayed source window contains the needed fact. The owner also
reviewed one explicit contradiction control and one source-supported but
question-irrelevant control; two other proposed contradiction pairs lacked
enough counter-evidence and are not valid negative labels.

The public 0.6B relation experiment produced no qualified calibration rule.
The separately approved Qwen3-4B diagnostic stopped at its 30-second startup
bound before a validated inference result. That is a resource-envelope failure,
**not** a measurement of the model's semantic accuracy or proof that models
cannot help. The independent answer-provider, quote-window, verifier and
retrieval issues still require distinct diagnosis. The owner chose exact
sourced excerpts only when an answer cannot be verified, with no unverified
AI answer prose, and approved making source browsing the proposed default.

## Decision

### 2026-09-26 approved evidence-sufficiency extension

The operator retained source-only Ask and approved relation-aware evidence
selection. The learner receives exact related published Knowledge with page
access, never a drafted or verified answer. The evaluation pipeline is
`Question -> Candidate Sources -> Evidence Sufficiency -> independently
reviewed Gold Source`; runtime candidates do not acquire a gold label merely
because a local ranking rule selected them. The later answer-generation/
claim-verification branch in the operator's architecture reference is excluded
from this product decision.

Keep the present question's requested information type, entity and qualifiers
in a local versioned descriptor. History may resolve an unambiguous entity,
but must not erase the current request for an expansion, definition, mechanism,
measurement, reason, process, property/limitation or application/example.
An ambiguous follow-up makes no remote call.
Use the existing exact-vector and PostgreSQL-FTS candidate channels, then
qualify complete entity-bound source units before similarity/overlap ranking.
An authored relation cue is a navigation candidate, not proven entailment.
Partial context may trigger local same-page and ±1/±2 eligible-neighbor
inspection under the exact principal, selected-document, publication,
revision/corpus/readiness and space predicates. Limits are 30 local chunks,
12 candidate pages and 8,192 estimated tokens, while display keeps three
distinct pages and exact ≤480-character existing chunk spans. Never stitch
an uncitable quote, inherit a neighbor's anchor score, or send additional
provider requests. Distinguish candidate retrieval, sufficiency selection,
provider failure and unresolved-referent outcomes in safe diagnostics.

Changed selector semantics require an immutable snapshotted policy identity;
old queued work must not silently run under a changed selector. If this needs
a new job policy, extend the source-only database caps and parent-stage guard
with a new Alembic revision, preserving used migrations and historical rows.
Change the shared chunk/index representation only after measurement shows
lost structure, with a versioned canonical-page reindex and separately
approved remote cost. Source qualification happens before result persistence;
the existing final source authorization and whole-bundle read fences remain.

Activation additionally requires an independent, human-reviewed twelve-case
positive holdout with sufficient displayed/openable hit@3 ≥10/12 and ≥3/4
per direct/paraphrase/follow-up group, plus zero false primary qualifications
on at least sixteen independently reviewed insufficient pairs, at least two
per relation and paired with sufficient controls. The existing first-window,
irrelevance, maintained retrieval and access gates also apply. The prior
4 Yes/8 No review and thirteen No/No alternatives are development examples,
not an independent holdout or corpus-wide absence proof. Ask remains off
until all gates pass. This extension authorizes no paid AI call or remote
reindex. See the [recommendation and research references](../../.agent/logs/2026-09-26/2026-09-26-evidence-sufficiency-recommendation.md).

The operator subsequently approved the same-day
[relation-coverage amendment](../../.agent/logs/2026-09-26/2026-09-26-source-relation-coverage-recommendation.md):
property/limitation and application/example are explicit additional families.
They preserve the requested entity, polarity, condition and domain relation;
topic mentions and another entity's predicates remain insufficient. Source
selection may inspect an exact contiguous owning-heading plus bullet or
continuation unit within the existing 480-character cap when that context is
already present in the canonical chunk. This neither generates text nor
silently changes indexed representation. Snapshot
`hybrid_source_sufficiency_v3`/`source_relation_units_v3` before execution and
reject older selector snapshots before manual-retry quota admission. Keep all
existing bounds and thresholds; the insufficient-pair minimum is sixteen,
two per eight families with sufficient controls. Positive holdout sampling is
4/4/4 across question groups, not exactly two positives per family. The
amendment adds no model, provider request, remote reindex or automatic activation.

The operator subsequently approved the same-day
[source-structure and private-discovery amendment](../../.agent/logs/2026-09-26/2026-09-26-source-structure-coverage-recommendation.md).
For the other six relation families (acronym expansion, definition, mechanism,
measurement, reason and process), local selection may inspect an exact
contiguous owning-slide-title plus bullet/continuation unit **only when the
same canonical indexed chunk contains both**. Its bullet must express the
requested relation predicate; the title or bullet must name the requested
entity, every question qualifier must remain visible in the selected unit,
and another named subject cannot borrow that title. Topic-only titles,
partial predicates, clipped qualifiers and synthesized cross-chunk text do
not qualify. The selected excerpt remains verbatim and at most 480 characters.
Property/limitation and application/example retain their v3 relation guards.
This authored source qualification does not imply an answer or semantic proof.

Snapshot this changed selector as `hybrid_source_sufficiency_v4` with local
`source_relation_units_v4` and reject older selector snapshots before
execution or manual-retry quota admission. The one-embedding/zero-answer/
zero-verifier provider boundary, 20 first-stage candidates,
30-chunk/12-page/8,192-estimated-token local budget, three-source display cap
and all existing reviewed 12-positive/16-insufficient, retrieval, access and
release gates remain intact. Do not change indexed representation or reindex
remotely without measured context loss and its separately approved procedure.

An independently reviewed gold roster may use a bounded, validated
owner-private authored question input under OS Temp to reach unexposed lecture
pages. The input and exact candidate evidence stay out of tracked fixtures,
telemetry and logs. A filter match is only an unreviewed candidate; the owner
must separately label source fidelity, displayed-excerpt sufficiency and
original-PDF-page usefulness before a case becomes gold. Previously exposed
or development-labeled pages cannot become a page-disjoint holdout. This
amendment authorizes implementation and private packet construction but
does not enable Ask, add a provider call, or close a release gate.

**Operator amendment (2026-09-27): independent evaluation ownership.** The
operator requested that subsequent source evaluation be performed by the
engineering agents, without further owner review packets. This supersedes
the owner-only labeling requirement above. An evaluator separate from runtime
selection must inspect the original PDF, verify exact source/page fidelity,
and judge the requested relation and context in the exact excerpt before
freezing gold. Existing owner decisions remain immutable. Runtime rank,
discovery patterns and a useful surrounding page cannot supply a missing
excerpt label. Reviewer identity, artifact hashes, prior-page exclusions and
evaluation order must be recorded in private artifacts. All quality thresholds,
source-only boundaries and release gates remain unchanged.

The current implementation correction versions the same eight-family policy
as `hybrid_source_sufficiency_v5`/`source_relation_units_v5`. It recognizes
definition and application interrogative forms without treating their request
scaffolding as source qualifiers. Entity, factual qualifiers, ownership,
verbatim spans and all budgets remain required; older snapshots stay fenced.
This version increment is not a quality result or permission to enable Ask.

**Approved canonical-page source amendment (2026-09-27).** Independent
original/canonical review found that 25 of 28 reviewed units lose only their
owning heading from chunk text into section metadata; all complete units
remain on canonical pages. The operator approved exact canonical-page
evidence references and implementation. This supersedes the requirement that
the owning title and body both occur in indexed chunk content. Retrieval
continues to use current eligible chunk anchors; selection may read their
authorized current extracted pages and select one contiguous verbatim
heading/body span, after validating the anchor's body and section against that
page. Metadata concatenation and synthesized text remain prohibited.

Snapshot the new behavior as `hybrid_source_sufficiency_v6` with local
`source_relation_units_v6`; fence older execution/retry snapshots. An additive
Alembic revision adds explicit `chunk` versus `canonical_page` reference kinds
and interprets offsets against that kind's authoritative source. Preserve
historical chunk references, eligible anchor/revision constraints, atomic
claim-fenced commits and whole-bundle redaction. Reauthorize and validate
page linkage, offsets, revision, scope and expiry at commit and every read;
page highlighting uses exact canonical-page offsets for the new kind.

Count inspected page content within the unchanged 30-chunk/12-page/8,192-token
local budget. Keep at most three exact 480-character references, eight source
relations, all qualifier/ownership guards, one current-question embedding,
zero answer/verifier calls and all quality/release thresholds. This changes
local evidence selection and reference persistence, not indexed representation
or embedding space. It authorizes no paid reindex/provider evaluation and does
not enable Ask. See the [measured recommendation](../../.agent/logs/2026-09-27/2026-09-27-canonical-heading-loss-recommendation.md).

### 2026-09-27 approved structural qualification amendment

The operator approved the [bounded v7 recommendation](../../.agent/logs/2026-09-27/2026-09-27-structural-source-qualification-recommendation.md)
and implementation after the canonical-page diagnostic selected only 1/12
independently sufficient source windows with correct page anchors. The missed
sources retain explicit information in headings, lists and explained examples;
this does not measure retrieval or model quality.

Separate question entity, relation, requested object/domain, conditions,
polarity and numbers from request wording. Resolve bounded local follow-ups
only from a single unambiguous prior entity, including ordinary noun phrases.
Build source units from owning headings, relation subheadings, paragraphs,
list items, ordered action sequences and explicitly explained examples. A
relation label and its complete body may state the requested relation without
a fixed verb. End inherited ownership at another topic or overt subject.
Accept only unambiguous acronym/full-name aliases attested in eligible source
text with their original offsets; matching normalization never changes the
displayed verbatim slice. Generic topic mentions, unrelated examples, missing
conditions/numbers, unordered items presented as a process and implicit
mathematical inference do not qualify. Rank only qualified units.

Snapshot `hybrid_source_sufficiency_v7` and `source_relation_units_v7`; extend
the canonical-reference insertion guard with an additive migration rather
than rewriting `0024`. Preserve historical references and every access,
revision, atomicity, expiry, exact-offset and complete-bundle read invariant.
Keep one current-question embedding, zero answer/verifier calls, three exact
480-character windows and the unchanged 30-chunk/12-page/8,192-token budget.
This adds no model, dependency, reindex or embedding-space change.

Independent public positive/negative structural cases precede implementation.
Freeze the candidate before one private measurement. Exposed v6 pages become
regression evidence; independently reviewed unexposed pages are required for
the release holdout. Retain all existing thresholds and Ask's closed release
fence. Report insufficient holdout material or residual inference limits
instead of silently relaxing gates or adding private question-specific rules.
Any learned source-sufficiency component requires a separate proposal. Future
source review is delegated to independent agents, as instructed by the operator.

### 2026-09-27 approved learned-ranking feasibility audit

Frozen v7 fails independent source sufficiency and must not be activated.
The operator approved [one local learned-ranking audit](../../.agent/logs/2026-09-27/2026-09-27-learned-source-ranking-feasibility-recommendation.md)
of pinned GTE ModernBERT INT8 on complete questions and exact displayed
windows. This encoder produces only a candidate score; it cannot be treated
as an answer, entailment certificate or calibrated sufficiency probability.
The 96 independently authored public cases split into 32 calibration and
64 heldout. Freeze one calibration-only acceptance threshold, then require
at least 28/32 sufficient heldout hits, at least 3/4 per relation and zero of
32 insufficient hits before the single private offline qualification audit.
Retain every existing private, source/current-access and release gate.

The approved acquisition envelope is ten GETs/300 MiB/30 minutes, at most
one retry/resume per file, for the pinned public model/tokenizer bundle.
Inference is offline: four CPU threads, at most 2 GiB added resident memory,
20-second startup, five-second p95 per 30-window pool, 600 seconds total.
Reject silently truncated question/window evidence. Stop on budget, quality
or compatibility failure; do not tune heldout, train, swap models or restore
the retired answer/verifier. The approval covers audit preparation/acquisition/
execution only. Runtime integration, paid calls, rollout and Ask activation
remain separate decisions. See the
[audit evidence](../../.agent/logs/2026-09-27/2026-09-27-learned-source-ranking-audit.md).

The approved one-shot audit met technical resource bounds but **failed public
source sufficiency**: zero of 32 heldout sufficient windows survived the
calibration-only threshold. It is not a selected Ask component. No private
qualification, runtime integration, paid retrieval or Ask activation followed.
The frozen score and review evidence remain in the audit record; source-only
presentation and the existing quality/release gates are unchanged.

### Default result and remote boundary

- After its own release gate, a new Ask job snapshots `related_knowledge_v1`
  as its immutable policy and uses the existing durable, principal-private
  Subject queue, claim fencing, quotas, cancellation and retention. It may
  send the **current question only** in at most one physical
  `QUESTION_ANSWERING` query-embedding request to its configured embedding
  provider. It makes zero answer-model requests, zero local answer-verifier
  calls and zero automatic provider retries. No lecture excerpt, prior chat
  history or generated answer is sent to an answer model by this policy.
- The worker performs authorized exact-vector plus PostgreSQL lexical retrieval
  in the active compatible embedding space. The evidence-sufficiency extension
  below replaces the initial top-five source-selection budget with at most
  twenty first-stage candidates, followed by bounded local qualification and
  same-page/nearby-page inspection. Both
  SQL candidate paths retain Subject ownership/enrollment, selected-document,
  review/publication, readiness, current content/index revision and space
  predicates. The selection rule may use only bounded local question/context
  signals, including locally inspected authorized conversation context if a
  separately evaluated follow-up rule needs it. A bounded, versioned
  history-aware lexical candidate rule may be evaluated locally when the
  current-question vector alone cannot resolve a referent. Prior chat is
  **not** added to the outbound embedding payload under this policy. An
  ambiguous referent that cannot be resolved safely produces `no_match` or
  asks the user to clarify; it is not guessed from history. The selector
  cannot make another embedding/reranking/provider call or treat word overlap
  as answer entailment. Any future prior-chat egress needs a separate explicit
  product decision and disclosure. Any changed indexed representation gets
  a separately versioned canonical-page reindex and measured cutover.
- The result is **Related published Knowledge**, not an assistant answer.
  Return at most three deterministic, distinct-page, source-contiguous exact
  excerpts, each at most 480 characters, with server-derived document title,
  page and optional section. The source text is escaped as text in the browser.
  Copy must state that these passages are related course material and have
  **not** been verified as an answer. No excerpt becomes a
  `RagMessage.sources` claim citation, support pass or asserted answer.
  Three is a maximum to validate on reviewed examples, not an automatic
  guarantee of relevance or a reason to show low-quality candidates.
- If no eligible, useful source window qualifies, complete with a distinct
  `no_match` result and no excerpts; do not imply that no answer exists in all
  course material. Query-embedding, transport, retrieval or internal failure
  yields a safe `failed` result, not `no_match` or a fabricated successful
  bundle. Provider execution/cost ambiguity remains visible to the authorized
  user through content-free diagnostics.

### Persisted outcome, source access and history

- Use a new Alembic revision and typed API contract with a job-level terminal
  `result_kind` (or equivalent) that distinguishes `related_knowledge` and
  `no_match` from historical `answer`/`abstained` and job `failed`. A
  completed source-only job has no assistant answer message. Relax the existing
  completed-job `answer_message_id` requirement **only for the new policy's
  valid terminal kinds**; retain it for historical answer/abstention jobs.
  Do not widen `RagMessage.outcome` with a pretend answer message. Extend
  related-reference count/order constraints from two to at most three without
  weakening current source-scope/offset checks. Snapshot the embedding role,
  model and complete space identity for the new policy without filling the
  existing required answer-provider/model columns with misleading dummy
  values; migrate their identity and stage constraints conditionally while
  preserving historical records. A `no_match` job has no refs.
- Persist only job-owned source IDs, exact character offsets, current
  content/index/corpus revision and embedding-space context, ordering, attempt
  and expiry, never a second copy of passage text. Under the current fenced
  claim and Knowledge write lock, recheck publication, scope and revision, then
  commit terminal `related_knowledge` and all its references atomically. A
  source change or lost lease cannot commit a partial or stale result. The
  reference expiry is no later than the question message's 90-day expiry.
- Every API/history read reauthorizes the requesting principal's own thread
  and current Subject access, selected documents, publication, active
  content/index/corpus revision, embedding space, offsets and expiry against
  canonical Knowledge. Hide the **entire** bundle on any failed check,
  unpublish, replacement, deletion or access loss; never expose a partial
  historical excerpt. Existing answer history remains governed by its old
  policy and source-read rules until the operator-authorized clean development
  volume reset; new Ask does not expose an answer action. Logs, metrics and account
  export do not duplicate quote text; retention and Subject/account cascades
  still remove dependent references.
- A retry or new paid attempt requires the existing accessible additional-cost
  disclosure and a fresh idempotency/quota identity. Previous uncertain spend
  is labelled unknown, not zero. Do not silently reinterpret an old queued
  `two_request_local_support_v1` job as source-only, or replay an uncertain
  embedding. Old-policy work is drained or explicitly fenced during cutover;
  it cannot be admitted, retried or run by the source-only worker.

### Availability and presentation

- Split Ask admission/profile/cost checks by immutable mode. Source-only
  availability needs the Ask gate, current compatible embedding space,
  embedding credentials and price/quota/worker readiness; it must not require
  an answer-model key, answer-model price or local NLI/QA bundle. Keep
  `RAG_ASK_ENABLED` default off until the source-only release gate passes.
  The provider key remains in the worker, never the API/browser. Ask has no
  answer-model readiness or local-verifier prerequisite.
- Refresh the mode-specific profile before enqueue. The browser and privacy
  disclosure for source-only say that the **question** goes to the configured
  embedding endpoint and that authorized published Knowledge is read locally;
  they do not say lecture text or bounded history is sent for a generated
  answer in this mode. Knowledge indexing has its own existing embedding
  disclosure. Present `related_knowledge`, `no_match`, provider failure,
  historical answer and abstention as distinct accessible states only until
  the authorized development data reset; new jobs have no answer state;
  preserve keyboard, focus, live-region and mobile behavior.

## Rationale

Exact current source passages give learners a useful path into their published
course material without promoting an unverified model claim into an answer.
One embedding request bounds new remote work while preserving the measured
Subject-scoped retrieval foundation. A separate job result kind and source
reference contract keep browsing evidence visibly and structurally distinct
from the historical answer contract. The product aim is to direct students
to a lecture page and let them read it. The Qwen startup timeout did not
establish semantic quality, and no answer model is needed for this product aim.

## Consequences and release gate

- Before enabling the new default, freeze the excerpt selector and evaluate
  the **displayed windows** on all eleven owner-reviewed positives and an
  independent direct/paraphrase/follow-up holdout. Pre-register the hit and
  usefulness criteria, top-three coverage, irrelevant-excerpt rate, rank,
  overlap, latency and physical request/cost accounting; compare the maintained
  RAG corpus. Top-five page recall alone is insufficient. Include the reviewed
  contradiction and true-but-irrelevant controls; do not count the two
  evidence-insufficient contradiction pairs as negative passes. Add
  unsupported/ambiguous questions, a locally resolved follow-up and an
  unresolvable referent, provider failures, prompt injection,
  malformed input, unpublished/cross-Subject/stale sources and mid-read drift.
  Require zero unauthorized or stale disclosure, fabricated quote, unverified
  answer assertion and unsafe rendering. A failed gate keeps source-only off.
- Verify the schema and typed UI/API discriminants, one-call/zero-retry
  boundary, fencing, atomic refs, idempotency, cancellation, cost disclosure,
  export/deletion, retention and old-job replay under targeted/offline and
  disposable PostgreSQL tests. Run the deterministic cross-stack journey,
  frontend check, context validation and manual keyboard/spoken accessibility
  review. Live embedding tests need a fresh explicit endpoint/model/price/
  call/token/time/cost approval; this ADR authorizes no provider spending.
- A self-hosted rollout needs drained writers/workers, a verified backup,
  migration/head and matching-image checks, Subject active-space preflight,
  quality verification and a rollback plan. On failure, disable new Ask
  admission and repair source-only behavior;
  preserve existing data and history. Do not downgrade a populated database
  or delete volumes to recover. The retained local stack runs matching source-only images with Ask off;
  that deployment does not prove the measured quality gate or enabled release.
- Flashcard yield and sparse-source feasibility remain independent Lane 6
  evidence. This design does not change generated-card validation, exact-count
  atomicity or the smaller-target choice.

## Related areas

[ADR-012](ADR-012-subject-knowledge-and-rag-boundaries.md),
[ADR-019](ADR-019-two-request-local-support-ask.md),
[ADR-021](ADR-021-related-knowledge-excerpts.md),
[ADR-023](ADR-023-original-pdf-source-navigation.md),
[product-quality plan](../development/PRODUCT-QUALITY-REMEDIATION-PLAN.md),
[Knowledge flow](../architecture/SUBJECT-KNOWLEDGE-FLOW.md),
[RAG evaluation](../RAG_EVALUATION.md),
[privacy guide](../PRIVACY.md),
[source-first evidence](../../.agent/logs/2026-09-26/2026-09-26-source-first-architecture-recommendation.md),
[answer service](../../backend/app/services/rag_answers.py),
[Ask panel](../../frontend/src/components/rag/AskAiPanel.tsx).
