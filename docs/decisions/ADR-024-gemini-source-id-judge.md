# ADR-024: Bounded Gemini source-ID judging for original-PDF navigation

## Status

Accepted; current implementation is `related_knowledge_navigation_v8`,
`visual_source_id_v5` and immutable `literal_subject_admission_v2` on Alembic
head `20261002_0033`. This partially supersedes ADR-023's original prohibition
on remote reranking/source transfer and adds the narrowly bounded literal
preceding-subject exception. Source-only, exact-reference, current-access and
immutable-history requirements remain unchanged. No answer generation or
answer verification is restored.

The retained local installation passed Lane 6's seven release gates and was
enabled on 2026-10-04; fresh installations remain default-off. Complete public
usefulness is 94/99; independent private twelve-case usefulness is 21/24
(87.5%), with 12/12 hits and 4/4 per form. The accepted floor is 80% of every
displayed card; hit/no-match/availability and zero fabricated/stale/unauthorized/
wrong-page gates remain separate. See the
[actual closure](../../.agent/logs/2026-10-03/2026-10-03-lane6-final-closure-and-activation.md)
for source/display/activation evidence, physical failures and unknown charges.
Dated activation is historical evidence, not a current health claim or new
provider authority. Inherited source was subsequently published through
[PR 41](https://github.com/EoCiMrEo/Cardchemy/pull/41); no production deployment
or new version release follows from that source merge.

## Context

Exposed authorized hybrid retrieval contained a useful original PDF page in
the top three for 11/11 questions, but only 19/33 displayed cards were useful.
Three separately bounded local selector audits failed combined no-match,
displayed-card usefulness and positive-hit calibration. Those failures do not
prove every selector or fresh holdout fails; they identify the observed
selection gap. More query vectors lacked an independently measured candidate
recall need. The owner wants students to read original lectures through 0–3
unverified related-reading references, never a generated answer.

A source judge changes privacy, physical-call and cost boundaries because it
receives authorized lecture text/visuals as well as the question. Private-source
transfer must be explicit, independently measured and disclosed.

## Decision

### Authorized input and output

Keep at most one unchanged current-question embedding per durable attempt.
Candidate assembly uses the existing exact-vector/FTS paths and bounded local
same-page/neighbor inspection. Ownership/enrollment, selected document,
reviewed publication, readiness, current revision/corpus and active compatible
embedding space remain inside SQL. Measure candidate recall separately from
final selection; multiple vectors require evidence and a further approved policy.

At most one bounded Gemini request may receive the current question, ephemeral
issued candidate IDs, exact authorized page/cue context and bounded PNGs of
the corresponding original pages. Authenticate complete original archives
before isolated rendering. Images retain physical page/scale/hash association
and fixed byte/pixel/deadline bounds. Do not send full PDF bytes, profiles,
other Subjects/unselected/unpublished revisions, credentials or answer drafts.
The provider returns only closed issued-ID/category/cue judgments; strict local
validation rejects foreign IDs, malformed global structure or ambiguous output.
A non-useful page with a contradictory positive cue is discarded, never promoted.
The current question's ordinary learning use of `ignore` is permitted by a
narrow lexical clarity rule, not a semantic instruction detector.

Only an unresolved follow-up may additionally transfer a unique literal subject
from the strictly preceding user question, at most 160 characters/twelve words.
Bind exact local identities, hashes, times and literal offsets immutably at
admission. Recheck that binding, current access/source/archive and claim after
quota waits immediately before dispatch and again before persistence. No full
preceding question, full history or assistant response is transferred. Clear
questions remain raw; ambiguous or stale context requires clarification.

The server derives titles, contiguous cues of at most 480 characters, offsets,
revisions and PDF page links locally. It atomically persists at most three
ordered job-owned references under writer/access/revision fencing. Reauthorize
the entire bundle at commit and every metadata/range/source read; any invalid
member hides the whole bundle. The model cannot write a citation, answer or
verified-evidence label. Never pad selection with a weak page.

### Outcomes, bounds and immutable history

Each durable attempt permits at most one query-embedding request and one
source-ID judgment, zero answer/verifier calls and zero automatic retries.
Bounded local lexical retrieval may follow transient embedding unavailability,
retaining failed-stage/unknown-cost diagnostics and visible fallback mode.
An unavailable judge is a safe provider failure, never a true no-match.
Valid empty selection completes `no_match`; useful selection completes
`related_knowledge`; neither creates an assistant answer message. Certain
finished source judgment may resolve source-free clarification, while failed
or uncertain calls cannot claim clarification.

The source judge has its own worker-only key, quota, prices and immutable
provider/model/token/time snapshot, independent of retired answer settings.
Current template uses Gemini 3.5 Flash-Lite HIGH, at most 32,768 input and
4,096 thinking-inclusive output tokens, 120-second request deadline and zero
retries. Price/account limits must be reviewed before live execution. Shared
worker admission, attempt cost and uncertainty account for both possible calls.
Manual Retry requires a separate accessible possible-extra-cost acknowledgement
and `Previous attempt cost is unknown` when applicable. Safe telemetry excludes
questions, source text, raw responses, private identifiers and secrets.

Historical answer/navigation policies and schema rows retain their original
identities and remain readable under current privacy/access/redaction guards;
they cannot execute or retry under v8. Consolidating module filenames does not
change immutable policy IDs, hashes, wire payloads or used migrations.

### Evaluation and installation enablement

Freeze source pools, independent input/page/cue labels, question forms,
calibration/holdout split, current model/wire/window rules and acceptance
criteria before scoring. Public-first calibration and source-separated public
holdout precede separately approved private transfer/holdout. Keep all cases
and every displayed card in the denominator; No/Unsure earns zero credit.
Physical failures remain separate from replacement outcomes and never count
as valid no-match. Failed historical 90%/cardinality trials are not regraded.
Current gates and complete measurements live in [RAG evaluation](../ai/RAG_EVALUATION.md).

Require exact-source/PDF-open, current access/revision/space, migration/race,
offline/service/journey/frontend, keyboard/spoken accessibility and operational
backup/rollback evidence before activation. Fresh installations remain off;
explicit Ask/judge flags, valid active embedding space/current prices and
matching services are required. Migration or a healthy image alone never opens
Ask. Every future provider/private-transfer evaluation needs a fresh exact
endpoint/model/price/call/token/time/cost envelope; old consumed approval and
a configured key grant no new authority.

## Rationale and consequences

One source judge targets the measured final-selection/no-match gap while
preserving the pedagogical source-only experience. Closed issued IDs and
local exact-reference derivation keep canonical Knowledge authoritative.
Independent public/private review separates source quality from provider
availability and access integrity. Passing the recorded sets cannot guarantee
arbitrary lecture usefulness or current external-service availability.

Source-content egress must be disclosed before asking. Operators review
provider terms/region/logging/retention and their own deployment privacy policy.
Safe failure, immutable history, extra-cost consent and source reauthorization
remain mandatory even after local activation. The independent Published
lectures browser remains available while Ask is paused or selects no useful page.

Earlier candidate approvals, failed/partial trials, consumed ledgers and exact
historical parameters remain in [dated logs](../../.agent/logs/README.md), the
[retired tracker](../archive/PRODUCT-QUALITY-REMEDIATION-PLAN.md) and the
[pre-cleanup ADR text](https://github.com/EoCiMrEo/Cardchemy/blob/61b34ebda127b712bf22e36f84fb393f1343f707/docs/decisions/ADR-024-gemini-source-id-judge.md).
Consolidation removes repeated chronology from this current decision; it does
not erase old failures, approve another call or modify historical data.

## Related areas

[ADR-023](ADR-023-original-pdf-source-navigation.md),
[ADR-022](ADR-022-related-knowledge-primary-ask.md),
[privacy](../security/PRIVACY.md), [provider operations](../ai/AI_PROVIDERS.md),
[RAG evaluation](../ai/RAG_EVALUATION.md),
[current state](../development/CURRENT-STATE.md),
[Ask maintenance](../ai/ASK_AI_SHUTDOWN.md).
