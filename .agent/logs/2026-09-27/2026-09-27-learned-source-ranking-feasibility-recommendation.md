# Learned source ranking feasibility recommendation

Date: 2026-09-27. Status: **operator approved the bounded audit**.
The operator explicitly approved the audit through the displayed question,
including plan/ADR updates, independent corpus/harness preparation, this
public bundle's bounded acquisition and one offline experiment. Subsequent
runtime integration, training, paid calls and activation remain unauthorized.
Approval evidence and actual results will be recorded in the
[audit implementation log](2026-09-27-learned-source-ranking-audit.md).

## Evidence and diagnosis

The [frozen v7 measurement](2026-09-27-structural-source-v7-implementation.md)
fails despite 310 development contracts passing: the independent challenge
selected 4/8 sufficient windows and falsely promoted 3/8 insufficient controls;
the exposed lecture set selected 1/12 positives even with correct page anchors.
The actual source text is present and exact offsets are intact. This isolates
a qualification bottleneck without proving that vector retrieval is complete.

The explicit grammar does not reliably associate a predicate with its owner
and condition. It also rejects some complete relations expressed differently
from its recognized forms. Occurrence of an entity, relation word and qualifier
in one window is not sufficient when they belong to different propositions.
Adding topic-specific patterns would continue fitting exposed cases. Apply
the approved v7 stopping rule and preserve the failed candidate as regression
evidence. Ask remains off; Lane 6 remains 3/7.

## Recommended next step: one offline learned-ranking audit

Evaluate a small question/passage cross-encoder as a **candidate**, before
changing production architecture. Keep exact page-window construction,
authorization, current revision/space checks, atomic references, expiry,
source-only presentation and existing query-embedding limits. The candidate
sees the complete bounded question and each actual displayed window together;
grammar may construct windows and explain diagnostics but must not discard a
sufficient source merely because it lacks a recognized relation phrase.

The concrete baseline is `Alibaba-NLP/gte-reranker-modernbert-base`, revision
`f7481e6055501a30fb19d090657df9ec1f79ab2c`, with published CPU INT8 ONNX
`onnx/model_int8.onnx`. The official repository lists an approximately 151 MB
artifact with SHA256
`ecc6a0ae67cee3d898167802383112d9185ca9250e07bd5d1fa65019b050179d`.
The English encoder has 149 million parameters. This is a text-ranking model,
not evidence that its scores certify sufficiency. The repository's retrieval
benchmarks do not establish this project's question/condition/ownership gates.
See the [official model card](https://huggingface.co/Alibaba-NLP/gte-reranker-modernbert-base/blob/f7481e6055501a30fb19d090657df9ec1f79ab2c/README.md),
[published INT8 artifact metadata](https://huggingface.co/Alibaba-NLP/gte-reranker-modernbert-base/blob/f7481e6055501a30fb19d090657df9ec1f79ab2c/onnx/model_int8.onnx)
and [Sentence Transformers retrieve/rerank documentation](https://sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html).

The audit must assess **sufficiency**, not only improved rank. Retain every
question condition/number/polarity; reject overlength inputs rather than
silently truncating them. Use exact contiguous candidate windows at most
480 characters and no surrounding hidden evidence when scoring sufficiency.
An internal score is neither a truth probability nor an answer. No generated
claim, extractive answer, retired answer-verifier call or learner-facing answer
is introduced. No hosted inference, training or extra remote request is proposed.

### Pre-registered measurement

1. Author 96 independent public cases before any model scoring: 32 calibration
   and 64 heldout, balanced positive/insufficient cases across all eight
   relations. Include same-topic wrong-owner, wrong-condition, negation,
   incomplete explanation, transition-only slides and unresolved follow-ups.
   Authors/reviewers stay separate from the audit implementer; freeze source,
   questions, labels, offsets, split and runtime fingerprints.
2. Choose at most one scalar acceptance threshold on calibration data, above
   every calibration insufficient score. Freeze that rule before heldout;
   do not label sigmoid values calibrated probabilities. Any lower diagnostic
   band may mean partial/unsupported but cannot promote a primary reference.
3. Require at least 28/32 sufficient heldout windows accepted, at least 3/4 per
   relation, and **zero of 32 insufficient** accepted. Unknown, malformed,
   timeout and unscored cases are failures, not passes. Also report score
   overlap, ranks, false-primary categories, source fidelity and latency.
4. Only after the public gate passes, run one frozen source-window audit on
   the existing exposed lecture regression and the separately reviewed
   unexposed prospective original-source packet. Keep both roles explicit:
   regression is not holdout; original-PDF qualification without published
   canonical binding is not a live SQL/retrieval or page-open release test.
   Existing private thresholds remain at least 10/12 and 3/4 per question
   group, zero of sixteen insufficient controls, and all seed/access gates.
   Review actual selected windows independently; no owner packet is required.
5. A failed audit ends this candidate. Do not silently fine-tune, add another
   model, tune thresholds on heldout/private outcomes or convert ranking
   relevance into a sufficiency claim. Training a sufficiency classifier or
   changing the product's primary-reference contract would need another
   evidence-backed decision. Success would justify a separately reviewable
   runtime proposal, not automatically enable Ask or close Lane 6.

### Proposed resource and download limits

Reuse the installed offline ONNX/tokenizer runtimes where compatible. Validate
compatibility before any dependency change; no unpinned executable model code
or `trust_remote_code` is permitted. Model/tokenizer/config bundle capped at
300 MiB, SHA/size manifest pinned before use; at most 512 pair-input tokens,
four CPU threads, 2 GiB added resident memory, startup 20 seconds, p95 at most
five seconds for a bounded 30-window pool, and 600 seconds total scoring.
Stop on any budget/compatibility failure. These are proposed ceilings, not
measured feasibility. No runtime resource budget is changed by this record.

If approved, public artifact acquisition is bounded to the pinned Hugging Face
repository: at most ten file GETs, 300 MiB total completed bytes, 30 minutes
total; at most one transport retry/resume per file within that envelope,
retaining verified bytes and requiring matching Range/length/hash. Do not
restart a complete verified file. Record consumed attempts honestly. All
inference runs offline with network disabled after bundle verification.
No Gemini request, Knowledge upload/indexing, retained DB write, `.env`
change, container rollout or Ask activation is included. Any dependency or
artifact outside these bounds needs a separately concrete approval.

## Corpus availability and ordering

All 107 pages of the current published scope were previously exposed. Four
additional originals have 159 pages, so a new independently reviewed corpus
is feasible, but unpublished original sources cannot satisfy current-source
SQL/release gates. A minimal 37-page prospective document produces 33 chunks
under the explicit 1200/120 preparation profile; this is local feasibility,
not embedding expenditure or indexing authorization. Finish and preserve
that packet independently, but defer paid ingestion and real-query embedding
tests until a source qualifier first passes its offline gate.

## Approval needed

The operator required approval before plan/architecture extensions, and the
approved v7 stopping rule expressly requires a separate proposal for a learned
source component. Approval sought: record **this bounded audit** in Lane 6/
ADR-022, prepare the independent corpus/harness, acquire this public bundle
within the stated limits, and run the offline experiment. Runtime architecture
integration, training, paid provider calls and activation remain later steps.
