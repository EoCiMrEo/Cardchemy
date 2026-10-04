# Lane 6 reading-usefulness classifier proposal

Date: 2026-09-28. Status: recommendation only. Branch `main` at
`6c02d6cf063acf83f4da5c08cfc4a3aa2c94be57`, with substantial pre-existing
working-tree changes preserved. No model was downloaded or scored; no private
lecture was read for this proposal, and no provider, database or runtime call
was made. This record does not amend the Lane 6 plan or ADR-023.

## Evidence and decision boundary

[ADR-023](../../../docs/decisions/ADR-023-original-pdf-source-navigation.md)
requires unverified source navigation and leaves Ask disabled pending displayed
page, quote, access and original-PDF gates. The stopped GTE listwise audit had
15/16 raw useful heldout top-one but its calibration-frozen display rule showed
0/16 useful pages. The 2026-09-28 stagewise diagnostic graded 17/33 displayed
cards useful in the exposed published lexical SQL case and useful-page hit@3
of 9/12 in a fresh but unpublished original-PDF proxy. In the published case,
15 of 16 weak cards were same-topic pages missing the requested relation.
Thus a new experiment must decide **whether to display each card and how many**,
not only reorder a pool. The GTE candidate stays stopped and its scored public
packet and reviewed private packets are regression evidence, never new holdout.

## Recommended bounded offline experiment

Use [Mixedbread's `mxbai-rerank-xsmall-v1` model card](https://huggingface.co/mixedbread-ai/mxbai-rerank-xsmall-v1)
as the public pair-scoring backbone, at immutable repository revision
`d1ba0a474aeed7c9fa96c3f57b128277580c5fae`. The repository publishes an
[87.2 MB quantized ONNX graph with SHA-256 `15ef19a6de90be7d52b627f2c784107bd806e64826450f41fb75fa4f0179ab30`](https://huggingface.co/mixedbread-ai/mxbai-rerank-xsmall-v1/blob/d1ba0a474aeed7c9fa96c3f57b128277580c5fae/onnx/model_quantized.onnx).
Its upstream license is [Apache 2.0](https://huggingface.co/mixedbread-ai/mxbai-rerank-xsmall-v1/blob/d1ba0a474aeed7c9fa96c3f57b128277580c5fae/LICENSE).
The published task is text ranking; no vendor benchmark proves Cardchemy
reading usefulness or a safe display count. This is a **new model and new
task-labeled decision rule**, not a rerun or retuning of GTE.

The proposed classifier takes the current question (and only locally resolved
prior-question context when needed) plus each exact, at most 480-character
learner-visible cue. It uses a frozen ONNX pair logit and a fixed small set of
question/cue lexical, title, condition and within-pool score features. Fit one
regularized logistic usefulness classifier on public training labels only.
For each question, rank by its output, show zero to three distinct original-PDF
pages whose classifier score clears one calibration-only threshold, and never
fill a slot for count's sake. This shared binary decision is the cardinality
classifier: the number accepted is the displayed count. Freeze feature names,
regularization, tie-break, page deduplication and threshold-selection algorithm
before seeing any model score; calibration may set only that one threshold.
For the threshold, scan midpoints between unique calibration scores and choose
the option with greatest useful-card recall subject to zero shown cards in
calibration no-useful groups, at least 90% precision across displayed
calibration cards, and at least 30/36 positive calibration groups with a
useful shown page. Tie-break toward the higher threshold. If no nonempty
rule satisfies these constraints, stop before opening heldout.
Do not call the score a probability of answer sufficiency or a verified answer.
No answer generation, extraction, NLI/QA verification, LLM, fine-tuning of
model weights, private-label fitting or remote reranking is included.

Before scoring, independent authors and blinded reviewers should freeze 192
public question groups with four natural candidate windows each, drawn from
actual independently sourced PDFs with documented public-domain or open reuse
rights:
96 train, 48 calibration and 48 heldout, with 24/12/12 groups per true
useful-card count (zero, one, two or three) in those respective splits.
Stratify each split across eight relation families and
direct/paraphrase/follow-up questions. Include wrong-owner, wrong-condition,
near-topic, partial-relation, negation, diagram-dependent and unresolved
follow-up cases. A useful card requires an independently useful original page
**and** a useful exact displayed cue for the requested reading relation;
record page-only usefulness separately. Use disjoint source documents and
question templates across splits, reject paraphrase or page-text leakage,
and freeze PDF/text provenance, page/offset, label, fixture, harness and
runtime hashes before the first score. Independent reviewers adjudicate
disagreement before the freeze; later unknowns and malformed inputs fail.
Neither the prior GTE packet nor the exposed 37-page unpublished PDF may enter
the new heldout. Invented controls may supplement the packet but cannot count
toward the primary public gate. Check each document's reuse rights before
copying text into a tracked public fixture.

For the public PDF corpus, pre-register at most eighteen document URLs plus
their authoritative reuse notices, with at least four distinct PDFs per
split. Cap retrieval at 24 GETs, 120 MiB received, 10 MiB per PDF, 100 pages
per PDF and 30 minutes; reject a document that needs an exception. Record URL,
license, bytes and SHA-256 before labels are written. Do not fetch private
course material or let a source appear in more than one split. These corpus
limits are separate from the model-bundle acquisition limit below.

Pre-register one heldout opening. A public **pass requires all** of: at least
33/36 positive groups with a useful shown page within three and at least
10/12 in each direct/paraphrase/follow-up group; at least 31/36 useful first
cards; at least 90% of every displayed card useful; at least 60/72 available
useful cards shown across the 1/2/3-card groups; at least 10/12 exact displayed
counts in each positive-count stratum; and zero displayed cards in all twelve
no-useful groups. No-output on a positive, unknown review, truncation, timeout
or score error counts as failure. Report pool recall separately, plus page-only
versus cue usefulness, false-primary mechanism and every displayed-card grade.
These are experiment admission gates, not ADR-023 release gates. On any miss,
stop this candidate: no heldout retuning, second model, private rescue, runtime
integration or Ask activation. A pass only permits a separately approved
development assessment and fresh source-disjoint release evaluation.

For any approved acquisition, allowlist only the pinned ONNX graph, tokenizer,
config, model card and license files; follow the [official immutable-revision
download method](https://huggingface.co/docs/huggingface_hub/en/guides/download).
Cap acquisition at 12 HTTP GETs including metadata/redirects, 160 MiB received,
one bounded transport retry per file and 30 minutes. Verify each file size and
SHA-256 plus a bundle manifest before and after scoring; do not load remote
code or fetch arbitrary dependencies. If the pinned file set or offline runtime
is incompatible, stop. Score in a networkless, credential-free disposable
container without retained data mounts; cap four CPUs, 2 GiB total added RAM,
20 seconds startup, 5 seconds p95 per 30 windows, 600 seconds for the entire
experiment and 256 pair tokens with no silent truncation. These are proposed
limits, not measured performance for this model. No app image, `.env`, database,
provider or production dependency changes are part of the experiment.

## Fresh release holdout and privacy

There is currently no fresh **published**, source-disjoint 12-case holdout:
the three retained published sources and the earlier unpublished 37-page PDF
have been exposed to diagnosis. A newly and independently sourced public PDF
can supply fresh release cases **with separate owner approval**, provided its
license permits this use, it is unseen by development/model selection, its
original pages and 4/4/4 direct/paraphrase/follow-up labels receive independent
review before scoring, and it is genuinely ingested/reviewed/published as
current authorized Knowledge in the active space. The release measurement
must then exercise real candidate SQL/hybrid retrieval, bounded current-query
embedding under a separately approved price/call/token/time/cost envelope,
every displayed cue and original-PDF page open, and negative access/revision/
publication controls. An unpublished local lexical proxy cannot satisfy those
requirements. Approval for the PDF or for this public offline audit is not
approval for paid indexing, provider calls or Ask activation.

The experimental public corpus and model remain isolated from private
Knowledge. If a model were ever shipped, retain the upstream Apache 2.0
license/notice and document its exact artifact digest; assess operator notice,
local retention and resource impact before runtime integration. Local
inference itself need not send private question or lecture text to a model
host, while the existing optional query embedding still sends the current
question to the configured provider under ADR-023. Do not put private source
text, questions, model input/output or user data in tracked fixtures, CI,
logs or external model services.

Verification for this **proposal**: read current ADR, plan, model-audit and
stagewise diagnostic evidence; checked the upstream model card, graph metadata,
license and official revision-download documentation. No execution checks were
run because acquisition/inference and runtime work were outside this scope.
