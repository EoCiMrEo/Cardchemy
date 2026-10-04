# ADR-019: Two-request Ask AI with pinned local semantic support

## Status

Accepted 2026-09-22 for product-quality Lane 5. This supersedes only the
remote-support call and Ask retry decisions in
[ADR-012](ADR-012-subject-knowledge-and-rag-boundaries.md) and
[ADR-014](ADR-014-native-gemini-rag-profiles.md). Their authorization,
publication, revision, source, quote, citation, privacy and abstention
boundaries remain accepted. It completes the replacement gate anticipated by
[ADR-015](ADR-015-ask-pause-and-gemini-catalog.md).
The operator accepted [ADR-022](ADR-022-related-knowledge-primary-ask.md)
on 2026-09-26 as the only future new-job source-only path. It supersedes this
record's answer generation and local-verifier execution for new Ask work; no
optional verified-answer mode is approved. This record still explains
historical job snapshots and the earlier installation. The source-only release
fence is closed until its separate quality and rollout gates pass.

## Context

The former Ask attempt used one remote query embedding, one remote answer and a
second remote text request for semantic support. Provider and application
retries could increase physical requests further. The operator requires at most
two remote requests in one durable attempt and an independent semantic check;
answer-model self-attestation, quote containment or lexical overlap alone is
not sufficient.

Self-hosted deployments therefore need a reproducible local verifier with known
artifacts, licenses, CPU/RAM and latency. Missing, corrupt, incompatible or
failed local inference must close Ask rather than restore the remote support
call or relax grounding.

## Decision

New jobs snapshot answer policy `two_request_local_support_v1` and support
policy `local_nli_qa_v1`. One durable attempt may make, in order:

1. at most one physical remote query-embedding request;
2. local authorized exact hybrid retrieval;
3. at most one physical remote structured-answer request; and
4. a local semantic-support stage with no provider request.

The answer worker forces application retries to zero for both remote roles;
the Gemini SDK is already configured for one attempt. A failed or missing query
embedding cannot trigger an answer call. Automatic lease recovery is permitted
only while execution is certainly before the provider boundary. A timeout,
disconnect, provider-started dead lease or other uncertain execution is
terminal for that attempt. Old three-call or mismatched policy snapshots cannot
be claimed by the new worker. Migration `20260922_0017` snapshots both policies,
records current-attempt cost provenance, admits `local_support`, limits each
remote stage to one physical request and zero retries, and enforces one query
embedding and one answer stage per manual-attempt number.

The local gate combines two independent CPU-only ONNX models:

| Purpose | Pinned artifact | Revision | License |
| --- | --- | --- | --- |
| Quote entailment and contradiction | `cross-encoder/nli-deberta-v3-xsmall`, quantized AVX2 ONNX | `a150876415327c80daeff35ca6f68f5ed8cf5c24` | Apache-2.0 |
| Question relevance through extractive QA | `onnx-community/tinyroberta-squad2-ONNX`, int8 ONNX | `7c9f69b7e6228375169a4553bcfa6639152e3a69` | CC-BY-4.0 |

Both upstream model cards identify licenses that permit commercial use under
their terms. The [packaged attribution notice](../../backend/legal/LOCAL-SUPPORT-MODELS.md)
credits the models, links their licenses and records that Cardchemy does not
alter the published weights. Operators distributing the separate bundle must
retain applicable upstream notices.

The installer downloads only immutable HTTPS revision URLs, verifies pinned
byte sizes and SHA-256 digests, writes a manifest and refuses to overwrite a
nonmatching bundle. The worker verifies every model and tokenizer digest,
rejects symlinks and unexpected graph inputs/outputs, and loads both models
before claiming a job. It runs offline with `HF_HUB_OFFLINE=1` in a dedicated
pinned distroless Debian 13 image as nonroot UID/GID 10001. ONNX Runtime's glibc wheel is
kept out of the Alpine API, generation and index images. The host bundle is
mounted read-only and is not committed to the repository.

For each validated claim, the local gate requires NLI entailment of at least
0.80 and greater than neutral or contradiction. A locally extracted answer span
must appear in the claim, or independent QA on the claim must extract a span
that is equivalent to the source span with at least 0.90 NLI entailment in both
directions. This handles a supported definition paraphrase without accepting a
model assertion as its own relevance proof. No retrieved sentence may have a
contradiction score at least 0.50 that dominates its other classes. The existing SQL access,
publication, active revision and embedding-space predicates run before this
stage. Exact quote containment, current source reauthorization, one-to-five
ordered citations, server-derived page/section metadata and fixed abstention
remain mandatory. Any local model error, input truncation risk, invalid score,
missing answer span or semantic rejection fails closed.

`RAG_ASK_ENABLED`, both provider switches, `RAG_LOCAL_SUPPORT_ENABLED`, nonzero
answer/embedding prices, current catalog/policy snapshots, required worker-only
keys/quota labels, a readable model directory and a Subject active space that
exactly matches the configured space must all pass. Defaults remain off. The
profile is refreshed before browser enqueue; a changed profile is rejected.

Every manual Retry is a new authorized attempt. An accessible confirmation
dialog states that another embedding and answer request may incur cost, shows
the additional estimate or labels it unavailable, and says `Previous attempt
cost is unknown` when prior execution cannot be priced. The service allocates a
fresh idempotency identity and quota receipt while preserving cumulative usage,
cost and support-rejection totals.

## Measured selection evidence

The 2026-09-23 local release corpus contains six supported direct/paraphrase
cases and five unsupported/conflicting cases. Three repetitions of all eleven
cases passed with zero supported false rejections and zero unsupported false
acceptances. The same-corpus design comparison was: literal quote only 4/11
correct (five feasible rejections, two unsafe accepts), NLI alone 9/11 (two
irrelevant answers accepted), literal extractive QA alone 8/11 (one feasible
rejection, two conflicts accepted), and combined NLI plus extractive QA 11/11.
Answer-model self-check is not independent. A separate local generative
reasoning verifier remains an unselected option requiring its own pinned
artifact, license, resource and corpus evaluation before use.

On the measured Windows host, the verified bundle was 181,734,633 bytes,
startup was 3,248.539 ms, p95 verification latency was 82.263 ms and the
working-set increase was 330.555 MiB. The release ceilings are 200 MiB bundle,
10 seconds startup, one second p95 and 512 MiB RSS increase.

These measurements prove the checked corpus and host envelope. They do not
prove broad natural-language correctness, another CPU/platform's performance,
current remote-model quality, hosted CI, deployment or provider billing.

## Rationale

The two-request policy makes the cost and replay boundary explicit. Independent
local NLI plus extractive QA retains semantic entailment, relevance and conflict
checks without sending a third copy of private evidence to a provider. Pinned
artifacts, hashes, licenses and a dedicated runtime make the self-hosted
dependency reproducible and fail closed.

## Consequences

- There is no automatic three-call fallback. If artifacts, quality, resources,
  pricing, active space or another release gate fail, Ask stays disabled.
- The API and browser never receive provider credentials or the local models.
  Course text used by the verifier remains inside the answer-worker container.
- The model bundle adds about 173.3 MiB of artifact bytes and measured memory
  use to an enabled answer worker. Operators must provision that capacity and
  review both model licenses for their deployment.
- Normal tests and local-verifier evaluation make no provider request. A live
  comparison still requires an explicit two-call/token/time/cost envelope.
- Existing private history remains readable under current access and source
  eligibility even while new Ask admission is disabled.

## Related areas

[ADR-012](ADR-012-subject-knowledge-and-rag-boundaries.md),
[ADR-014](ADR-014-native-gemini-rag-profiles.md),
[ADR-015](ADR-015-ask-pause-and-gemini-catalog.md),
[ADR-018](ADR-018-gemini-embedding-2-space.md),
[ADR-022](ADR-022-related-knowledge-primary-ask.md),
[Ask operations](../ASK_AI_SHUTDOWN.md), [provider guide](../AI_PROVIDERS.md),
[RAG evaluation](../RAG_EVALUATION.md),
[Knowledge flow](../architecture/SUBJECT-KNOWLEDGE-FLOW.md).

Artifact sources:
[NLI model](https://huggingface.co/cross-encoder/nli-deberta-v3-xsmall) and
[QA model](https://huggingface.co/onnx-community/tinyroberta-squad2-ONNX).
