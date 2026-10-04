# Subject Knowledge evaluation corpus

## Current local Lane 6 closure — 2026-10-04

The local source-only v8/visual-v5/admission-v2 installation on head `0033`
is enabled after its measured quality, PDF/display and release gates. Fresh
installations remain default-off. See the
[closure and activation evidence](../.agent/logs/2026-10-03/2026-10-03-lane6-final-closure-and-activation.md). Earlier installation
checkpoints below remain historical snapshots; the linked closure supersedes
their off/pending status, while default-off and upgrade safeguards still apply.

## Current source-navigation release metrics

The owner accepted the [2026-10-01 metric alignment](../.agent/logs/2026-10-01/2026-10-01-source-navigation-metric-alignment-approved.md):
usefulness must reach **80% across every displayed card in a complete
evaluation**. Keep independent original-PDF hit@3 at least 10/12 and 3/4
per question form; the prospective public ordinary no-match gate is at least
10/12 clear empty outcomes, while fabricated, unauthorized, stale or wrong-page
references remain forbidden. No-match, exact-source, authorization and release
gates remain separate. Useful-set completeness and cardinality are diagnostics,
not requirements to fill three slots. The full public calibration retains
67 groups, 45/54 hits, 15/18 per form, at least 65/67 valid responses and
at most two errors. Uncertain selections receive zero credit. The earlier
12/12 no-match threshold and 90% usefulness records below remain historical;
their stopped trials are never retroactively regraded as passes.
Ask stays disabled until the actual matching policy passes.

The [2026-10-02 heldout alignment](../.agent/logs/2026-10-02/2026-10-02-heldout-review-uncertainty-metric-alignment.md)
applies the same zero-credit No/Unsure rule to the prospective heldout v2
scorer. Strict issued-ID validation remains independent and unchanged.
Keep all sixty cases: at least 58 valid outcomes, at most two failures,
40/48 useful hits, 14/16 per form, 10/12 conclusive empty no-match outcomes
and 80% usefulness across every displayed card. The original v1 trial's
absolute reviewer-Unsure gate and stopped results remain historical;
no uncertain label receives a useful credit or retrospective pass.

Source head and retained database are `20261002_0032`. Dormant visual v7
`visual_source_id_v3` authenticates original PDFs and can pass bounded exact
page text/cues and full-page PNGs to one ID-only judge after at most one
current-question query embedding. Its current output ceiling is 4,096 tokens
including thinking, with a 120-second source-judge deadline. An unresolved
follow-up may project only a unique immutable literal subject from its strictly
preceding user question; no full history or assistant text is sent.
Public calibration passed with 92/103 useful displayed
cards; the separate different-PDF input review and caller preparation made
zero provider calls. The later [public v6 trial](../.agent/logs/2026-10-02/2026-10-02-public-heldout-v6-terminal-result.md)
stopped on availability: 38 evaluated questions, 35 valid replies and partial
49/50 useful displayed cards, with 22 untouched questions. Full different-PDF
holdout, matching private source-display/page-open usefulness and spoken
accessibility remain required before Ask admission. Technical access, PDF
browsing, migration and release rechecks are recorded in the
[retained cutover](../.agent/logs/2026-10-02/2026-10-02-v7-retained-cutover-and-release-recheck.md).

The separate [private v6 metric](../scripts/score_private_source_display_v6.py)
accepts externally SHA-bound roster, independent page/cue labels and later
display observations bound specifically to the earlier v6/visual-v2 policy.
Those immutable preparation artifacts do not validate v7/visual-v3 admission
or its matching private wire inputs. It retains complete
private 12-case and exposed-seed denominators, 80% across every shown card,
10/12 and 3/4-per-form holdout hits, N12/U01 controls and zero source/policy
violations. Unknown labels count as nonuseful; provider failures do not earn
no-match credit. It is a pure metric: source authorization, independently
frozen reviews, actual provider/display observations, browser and spoken
accessibility need separate evidence. It always leaves runtime release false.
The earlier v4 scorer and its 90% records below remain historical and unchanged.

The v6 review still needs an Ed25519 receipt over exact roster/label hashes
and freeze time, checked against a separately trusted reviewer-key SHA.
Externally supplied SHA bindings alone do not replace this review seal.

## Current source-navigation vector diagnostic

The separate [private v6 query preparer](../scripts/prepare_private_query_vectors_v6.py)
binds twelve current questions to the independently frozen gold and reauthorized
source snapshot. Its preparation-only CLI reads no settings or key and makes
zero provider/DB calls. Native mocked transport confirms twelve singleton
`batchEmbedContents` requests, each containing only the current question in
`QUESTION_ANSWERING` mode; history and lecture text never enter this request.
An inert execution component requires a fresh pinned authorization, compatible
active space, a central exclusive approval claim and an external resource fence.
It checkpoints valid vectors privately and stops on failure without replay.
The prospective cap is twelve calls, 512 estimated input tokens, 30 seconds per
call, six minutes total and USD 0.001 at a conservative USD 0.20/million guard.
Preparation does not authorize that trial or establish hybrid/display quality.
The [dated record](../.agent/logs/2026-10-02/2026-10-02-private-v6-query-vector-preparation.md)
distinguishes its zero-call preflight from actual provider evaluation.

The [provider-only query-vector builder](../backend/scripts/build_private_query_vectors.py)
accepts only the frozen eleven-case published-source roster and an explicitly
supplied principal, Subject, corpus revision and compatible embedding-space
identity. Its default invocation makes no provider or database call. The
`--preflight-inputs` mode checks roster bytes, the active validated Settings
embedding profile and cost envelope without a provider or database call.
`--execute` additionally requires one fresh matching UUID4 command flag and
process variable. An exclusive private receipt consumes that approval before
any request. A failed or uncertain attempt has no automatic retry.

The builder sends only each current question to native Gemini Embedding 001 in
`QUESTION_ANSWERING` mode, serially, with at most eleven physical requests,
512 aggregate estimated input tokens, 30 seconds per physical request, six
minutes total and a USD 0.001 local-cost ceiling at the conservative
USD 0.20 per million input-token admission price. It creates a complete
private vector packet with exclusive permissions for the separate
[read-only source-navigation diagnostic](../backend/scripts/diagnose_source_navigation.py).
The packet is an input to retrieval measurement, not a quality grade or
release result. The builder does not read or write the application database,
change Knowledge, send history, or generate an answer. Do not run its paid
mode without a fresh reviewed provider envelope.

On Docker Desktop with a Windows Temp bind, Linux permission bits on the bind
may appear permissive despite host ACLs. The builder requires a container-local
`/private` directory and roster file with modes `0700` and `0600`; copy the
frozen roster into that directory before preflight, and copy the resulting
packet to owner-private Temp only after the one-off container stops. Keep the
container on a network without application database access and pass only the
embedding credential and validated profile inputs.

The current authored, deterministic evaluation corpus is
[`subject_knowledge_v2.json`](../backend/tests/fixtures/rag_eval/subject_knowledge_v2.json).
It extends the original Phase 12
[`subject_knowledge_v1.json`](../backend/tests/fixtures/rag_eval/subject_knowledge_v1.json)
before retrieval, prompt, ANN or reranker tuning. Both fixtures contain only
synthetic teaching material: no user lecture/chat content, credentials or paid
provider authorization.

Lane 0 adds the focused
[`product_quality_lane0_v1.json`](../backend/tests/fixtures/rag_eval/product_quality_lane0_v1.json)
corpus for repeated direct/paraphrase questions, the reported semantic support
false-rejection shape and a contradiction control while Ask remains paused.
Lane 5 adds the content-free
[`product_quality_lane5_local_support_v1.json`](../backend/tests/fixtures/rag_eval/product_quality_lane5_local_support_v1.json)
selection corpus with six supported direct/paraphrase claims and five
irrelevant, unsupported or conflicting controls.

## Phase 19 cases

The v2 corpus includes direct facts, semantic paraphrases, exact technical
terms, similar concepts across lectures, multi-page topics, overlapping chunks
and a bounded follow-up. Negative cases cover ambiguous or unsupported
questions, an empty eligible corpus, conflicting handouts, lecture/chat prompt
injection, cross-Subject and guessed source IDs, and ready-but-unpublished
Knowledge. Validation cases use a real but unrelated citation and an
unsupported claim attached to a valid source ID, because identifier membership
alone does not establish relevance or semantic support.

Lifecycle cases cover access revocation before and during work, corpus and
embedding-space mismatch, unpublish/delete/reindex while queued or running,
and history-source redaction after unpublish/delete. The PostgreSQL suites
exercise those states against current owner/enrollment, publication, active
revision, corpus and embedding-space predicates; source reads reauthorize the
same scope instead of trusting a stored citation.

## Historical answer-policy thresholds

These checked-in gates describe the earlier retrieval/answer-policy corpus.
They are retained as a nonregression baseline and do not enable new Ask answer
generation:

| Measurement | Required result |
| --- | ---: |
| Retrieval recall at top 5 | 1.00 |
| Mean reciprocal rank | at least 0.80 |
| Feasible-answer claim support | 1.00 |
| Unsupported-query abstention | 1.00 |
| Invalid-citation rejection | 1.00 |
| Cross-Subject/private-source exposure | 0 |
| Duplicate-overlap rate among returned chunks | at most 0.20 |
| Disposable exact-query p95 | at most 2,000 ms |
| Local indexing throughput | at least 1 chunk/second |
| Bounded history context | at most 8 messages |
| Historical two-request answer-policy calls per durable Ask attempt | at most 2: one query embedding and one answer; zero automatic retries |
| Local support release corpus accuracy | 100%, with zero supported false rejections and zero unsupported false accepts |
| Local support runtime | bundle at most 200 MiB, startup at most 10 s, p95 at most 1 s, RSS increase at most 512 MiB |

The evaluator reports recall@K, reciprocal rank, support, abstention, citation
validity, forbidden-source exposure, overlap diversity, retrieval latency,
index throughput, history consumption and provider-stage bounds. Token and cost
ceilings are separately enforced by the snapshotted answer and embedding
profiles; local estimates and provider receipts are not a complete billing
ledger.

## Source-only displayed-window gate (not yet passed)

### Prospective original-PDF navigation contract: ADR-023/024

The operator approved [original-PDF source navigation](decisions/ADR-023-original-pdf-source-navigation.md)
after the frozen v7/GTE sufficiency experiments failed. The paragraphs in
this subsection describe the **earlier v4/0029 release design and its
historical tests**; the current v7/0032 target and revised prospective metrics
are stated above. Historical v3/v9 navigation selected pages locally; source
head `0029` admitted prospective
`related_knowledge_navigation_v4` with `hybrid_source_navigation_v9` and
the [ADR-024 source-ID judge](decisions/ADR-024-gemini-source-id-judge.md).
It allows at most one current-question embedding and one bounded source-ID
judgment over currently authorized published page cues, zero answer/verifier
calls and zero automatic retries. The server derives up to three exact,
unverified reading references and original-PDF page links locally. Transient
embedding unavailability may use bounded lexical candidates; judge failure
remains distinct from true no-match. The current release fence keeps Ask off,
and the retained installation was verified at `0029` after its restore-backed
cutover. That dormant v4 worker was not admitted for Ask. This does not
label a source sufficient.
Earlier sufficiency evidence and scorers below are historical; passing them
cannot substitute for the new page-navigation gate.

Freeze runtime and a source/document-separated 12-case direct/paraphrase/
follow-up holdout before measurement. Require useful-page hit@3 >=10/12 and
>=3/4 per group, plus >=10/11 on exposed seed regression. Report top-one and
every displayed card; at least 90% of **all displayed cards** must open an
independently judged useful original PDF page for that question. Uncertain
grades fail, and showing no cards cannot satisfy hit@3. Separate PDF
fidelity/extraction coverage, eligible
index coverage, actual SQL candidate recall, nearby-page pool, displayed
quote/page and authenticated original open. Oracle-page tests are not real-
query retrieval proof. Include no-source/wrong-condition/ambiguous-history,
embedding outage/fallback, unavailable-original and all current-access controls.
Fresh paid embedding/index evidence needs its own approved envelope. Ask stays
off until quality, access, migrations and release gates pass.

The separately approved 2026-09-28 eleven-question query-embedding packet
measured current published-source hybrid retrieval without an Ask job or
database write. Independent original-PDF review found a useful displayed page
for 11/11 exposed cases and a useful first page for 9/11, while only 19/33
displayed cards were strictly useful. The designated gold page was in the
SQL candidate pool for 11/11 and in the displayed top three for 10/11.
This is development regression evidence with just one follow-up, not the
document-separated holdout, authenticated PDF-open test, or release pass.
The single approved provider envelope was consumed; no further paid query
or indexing is authorized by these results. See the
[dated diagnostic](../.agent/logs/2026-09-28/2026-09-28-live-query-embedding-hybrid-diagnostic.md).

Three separately approved, one-shot public Mixedbread display candidates
stopped at calibration before heldout. The later selective candidate separated
question-level no-match from per-card qualification, but no fixed pair of
thresholds met zero no-useful displays, 90% combined cue/page usefulness and
30/36 positive hits simultaneously. Its raw top-three scorer found a useful
candidate in all 36 positive calibration groups; that observation cannot
establish safe displayed-card selection or private-course quality. The third
groupwise candidate trained a four-way 0–3 count cap and per-card utility
gate on public train data; 20 local calls scored 576 train/calibration pairs
within resource limits, but no set-risk rule met zero no-useful displays,
90% useful cue-plus-page displayed cards and 30/36 positive hits together.
At risk `0.0`, the hypothetical display was 30/37 useful with five
no-useful groups showing a card and 21/36 positive hits; risk `4.0`
was 7/7 useful with zero no-useful displays but only 7/36 positive hits.
These calibration-frontier points are **not selected policies**. The third
fixture validator read all splits, including heldout labels, but heldout was
not scored or used for training/calibration. Its four-page, single-PDF groups
also do not establish runtime multi-PDF candidate-pool quality. All three
ledgers are consumed and the runtime policy stays disabled. See the
[second frozen audit](../.agent/logs/2026-09-28/2026-09-28-selective-navigation-frozen-audit.md).
Additional query vectors remain conditional on independent real-query
evidence of candidate misses and require a separate policy/cost approval.

The operator later accepted [ADR-024](decisions/ADR-024-gemini-source-id-judge.md)
as a **prospective** remote source-ID judgment path, not a deployed selector.
Test actual authorized candidate recall first on
deployment-shaped public multi-PDF pools. Freeze the question-plus-canonical-
page/cue prompt, ephemeral-ID-only schema, count/validation rule and model
before a public calibration/heldout pilot that includes same-topic weak
pages and no-useful questions. The proposed first pilot has at most four
public page candidates per question; it cannot alone prove the runtime
up-to-twelve-page case. Keep the frozen two-PDF Illinois public supplemental
holdout and the separate 12-case, three-PDF published-Knowledge private
release holdout sealed until the public candidate passes and its rule is fixed.
Report useful opened original pages **and** exact visible cues for every
displayed card, no-match errors, negative/access controls, physical requests,
latency and uncertain cost. The independent >=90%-all-displayed-pages,
>=10/12 overall and >=3/4-per-form hit@3, exposed >=10/11 and security/
PDF-open/accessibility gates above are unchanged. The two-PDF public labels,
split and acceptance rule were frozen, but the first approved calibration
stopped after one physical provider request whose response failed admission.
Its exact status and cost are unknown, no quality score was produced, heldout
remains sealed and that approval cannot be reused. See the
[calibration stop](../.agent/logs/2026-09-29/2026-09-29-public-source-id-live-calibration-stop.md).
Any new public attempt needs a fresh exact paid envelope including uncertain
prior cost. Private-source egress requires a later separate provider/content/
privacy decision, disclosure and paid envelope after a passing public gate.

The later separately approved public Gemini 3.5 Flash-Lite continuation
completed the frozen failure-inclusive calibration with 37 new accepted
calls for groups 12–48 and no replay of group 11. Across all 48 groups,
47/48 responses were valid, useful-page hit@3 was 35/36 positives, and
54/55 displayed exact-cue-plus-original-PDF cards were useful. One of twelve
completed no-useful groups displayed a page, so the **zero-false-display
calibration gate failed**. The different-PDF heldout was not opened and the
one-use authorization is consumed. This is a measured public calibration
failure, not a private-source or runtime result. The approved offline
`public_exhaustive_page_and_cue_v2` hypothesis judges each page and cue
independently and selects all qualifying issued IDs up to three, or none;
it makes no answer. It needs a newly frozen, disjoint public PDF calibration
and different-PDF heldout with the unchanged availability, useful-hit,
cardinality, all-displayed-usefulness and no-useful gates. The exposed score
cannot be its confirmation. See the [result](../.agent/logs/2026-09-30/2026-09-30-flash-lite-failure-inclusive-calibration-result.md)
and [next-candidate decision](../.agent/logs/2026-09-30/2026-09-30-source-id-calibration-cause-and-next-candidate.md).

The dormant [v4 original-PDF display scorer](../scripts/score_source_judgment_display_v4.py)
is separate from the public pilot scorer and historical v3 scorer. Its default
command only reports preflight status. Release scoring now requires the
[gold-to-slate bridge](../scripts/bridge_private_source_gold_v4.py), rejects
duplicate JSON keys in frozen inputs and reports top-one usefulness with
numerators and denominators. A future private measurement must bind
the independently frozen question/gold packet, the actual four-page candidate
slate, an independently signed review of **every candidate's original page and
exact visible cue before source-ID selection**, and the later runtime display
by exact hashes. The exposed eleven-case and fresh twelve-case holdout use
separate signed components; neither alone is a release pass. The combined
metric counts all displayed cards, treating `Unsure` as non-useful, with the
10/11, 10/12, 3/4-per-form, ≥90% usefulness among **all independent-holdout
cards** and among all combined cards, no-match and zero-invalid-source
conditions. A passing display metric would still leave browser, accessibility,
privacy, publication and operational release checks open. No actual private
v4 selection or holdout score has been established by this scorer's synthetic
tests.
The [denominator correction](../.agent/logs/2026-09-29/2026-09-29-v4-independent-holdout-denominator-fix.md)
prevents high exposed scores from masking weak cards in the independent
holdout; it does not alter the source-only runtime or activate Ask.

The keyless [private gold freezer](../scripts/freeze_private_source_gold_v4.py)
accepts only an exact-hash Temp input, verifies twelve page-distinct cases
balanced 4/4/4 across direct, paraphrase and follow-up forms, and binds each
visually reviewed gold page to current authorized published revisions and the
attached original-PDF SHA using read-only transactions. Its default preflight
does not read the database. The 2026-09-29 self-reviewed stage-1 packet uses
new questions and pages with zero overlap against the historical exposed/T/X
page inventory, and its three archived PDF hashes match the owner's local
original files. This is an agent visual review **before candidate selection**,
not an external human review or an actual v4 display score. The exact private
packet hash and limitations are recorded in the
[freeze evidence](../.agent/logs/2026-09-29/2026-09-29-fresh-private-original-pdf-gold-freeze.md).
No candidate slates or cue labels for these twelve cases have been frozen;
provider selection and all release gates remain pending.

### Historical sufficiency preregistration

The accepted [ADR-022](decisions/ADR-022-related-knowledge-primary-ask.md)
uses `related_knowledge_v1`: at most one current-question embedding, no answer
model or verifier, and up to three exact excerpts with an authorized extracted-
page open action. The current candidate preregistration is
[`source_first_display_gate_v1.json`](../backend/tests/fixtures/rag_eval/source_first_display_gate_v1.json)
and its aggregate-only scorer is
[`score_source_first_display.py`](../scripts/score_source_first_display.py).
This fixture is **unobserved**, and owner-reviewed source pairs are not labels
for the windows a selector actually displays.

The scorer also supports an opt-in, frozen `X##` private holdout registration.
It binds twelve separately owner-reviewed source candidates, their exact
question/page/history probe roster, prior exposed-source artifact bytes, runtime,
scorer and unchanged threshold digests before accepting measurements. It
requires four direct, four paraphrase and four follow-up questions on twelve
distinct pages in at least two documents; it does not derive human labels from
discovery patterns. Earlier reviewed/development page reuse is rejected.
Pattern-derived seed-page exclusion cannot be independently proven from the
packet alone and is reported as such; actual seed/holdout page disjointness is
still checked from measured rows. Registration is not a quality pass, and an
incomplete or reviewer-rejected source set cannot be frozen as gold. Following
the operator's 2026-09-27 instruction, subsequent labels may be supplied by
an independent engineering evaluator inspecting the original PDF and exact
source window before runtime measurement. Preserve prior owner labels and
record evaluator identity and artifact fingerprints; do not infer sufficiency
from discovery or selector output. The current registration interface uses
the historical owner-label field names; those names do not establish reviewer
identity. Independent registrations use separate v2 schemas and retain owner
flags false. They bind the original reviewed PDF artifact bytes, reviewer ID,
exact question/page/relation/quote identity, freeze time and post-registration
measurement/review order. Missing exact canonical chunk coverage remains
unavailable, even when reviewed page gold registers successfully; registration
cannot pass the exact displayed-span gate.

The candidate gate requires useful/openable hit@3 on at least 10 of 11
owner-reviewed seed questions, including H01, and at least 10 of 12 independent
page-disjoint holdout questions with at least 3 of 4 in each direct,
paraphrase and follow-up group. At least 9 first windows must be relevant in
each seed and holdout group; no more than 10% of displayed windows may be
irrelevant. It also requires zero fabricated/stale/unauthorized excerpts,
failed page opens, unverified answer assertions and U01 known-irrelevant
windows. The maintained retrieval recall@5=1 and MRR≥0.8 thresholds remain
nonregression criteria. Counts in the fixture are proposed thresholds, not
measured results or a released policy.

The owner subsequently approved a versioned source-sufficiency extension to
[ADR-022](decisions/ADR-022-related-knowledge-primary-ask.md). It raises the
local *candidate* ceiling to 20 (initially v2; relation coverage was v3; the
title-and-bullet extension was v4; canonical-page selection was v6;
the approved structural extension is v7), preserving
the exact-vector/PostgreSQL-FTS channels, while relation qualification and
bounded same-page/±1/±2 inspection choose at most three displayed exact
sources. It does not change the maintained top-five recall/MRR baseline or
authorize an answer model. A new independent private holdout must prove
sufficient/openable displayed hit@3 ≥10/12 and ≥3/4 per question group, plus
zero false primary qualifications on at least sixteen independently reviewed
insufficient question/source pairs, two per eight declared relations, with sufficient
controls. The earlier 4 Yes/8 No and thirteen No/No pairs are exposed
development labels, not that holdout. Public authored-rule tests and an
embedding-only guarded probe do not establish private quality. See the
[source-level recommendation](../.agent/logs/2026-09-26/2026-09-26-evidence-sufficiency-recommendation.md).

The historical v4 selector could qualify an owning slide title with its
bullet/continuation for the six relation families beyond property/limitation
and application/example. The title and bullet had to occur in the same
canonical indexed chunk; the displayed contiguous verbatim unit had to contain
the requested entity, explicit relation predicate and all qualifiers without
borrowing another subject's predicate. The 480-character excerpt and existing
inspection, provider, access and quality limits are unchanged. These are
authored source-selection rules, not independently reviewed gold labels or
proof of semantic entailment. The v4 backend image has passed an isolated
runtime smoke; Ask remains disabled pending independent source/display gates.
See the [source-structure decision](../.agent/logs/2026-09-26/2026-09-26-source-structure-coverage-recommendation.md)
and [current validation](../.agent/logs/2026-09-27/2026-09-27-source-structure-v4-validation.md).

The approved v6 canonical-page amendment supersedes that same-chunk rule;
eligible chunks anchor reauthorized page reads with exact kind-specific
offsets. Its frozen supplied-anchor diagnostic selected 1/12 sufficient
sources and none of sixteen insufficient controls, despite independent PDF
review reaffirming every original label. This measures qualification after a
correct anchor, not retrieval or visible-page quality. The approved v7 repair
uses explicit question roles and source structure, with no model or provider
change. Its public structural pairs must be authored independently before
implementation; the candidate is frozen before one private measurement.
Previously exposed v6 pages are regression evidence, so the release holdout
needs unexposed pages. Source-window labels must assess actual selected spans;
scores and exact offsets alone do not establish sufficiency. All current
gates and the disabled Ask state remain. See the
[v7 implementation evidence](../.agent/logs/2026-09-27/2026-09-27-structural-source-v7-implementation.md).

The single frozen v7 measurement subsequently failed: the independent public
challenge selected 4/8 sufficient windows and falsely promoted 3/8 insufficient
controls across owner/condition boundaries. The exposed lecture regression
remained 1/12 positives and zero of sixteen controls with correct page anchors.
These results reject activation and trigger the approved stop rule for further
private pattern tuning. Both measured sets now remain regression evidence;
they cannot become a fresh holdout for a later candidate. No paid retrieval
comparison was run after the qualification failure.

The operator then approved one separate [offline learned-ranking audit](../scripts/audit_source_ranker.py)
with [bounded public artifact acquisition](../scripts/download_source_ranker_bundle.py).
It freezes 96 independent public question/window cases and selects a single
threshold using only 32 calibration cases before measuring 64 heldout cases.
Public success requires at least 28/32 sufficient hits, at least 3/4 per
relation and zero of 32 insufficient hits, plus the approved resource limits.
Only a public pass permits the single private source-window audit. Existing
published-source retrieval, seed, independent private and release gates remain;
a ranking score is not by itself a calibrated sufficiency guarantee. The
experiment changes no runtime policy and authorizes no paid provider request.
See the [approved specification](../.agent/logs/2026-09-27/2026-09-27-learned-source-ranking-feasibility-recommendation.md)
and [actual audit evidence](../.agent/logs/2026-09-27/2026-09-27-learned-source-ranking-audit.md).

The single pinned GTE INT8 public audit finished with 4/16 calibration
sufficient, 0/16 calibration insufficient, 0/32 heldout sufficient and 0/32
heldout insufficient selected by the calibration-only threshold. Startup,
30-window p95 and added RAM were within the approved bounds, but quality
failed decisively. The private lecture and real-query gates were intentionally
not run. The result rejects this candidate for Ask; it does not establish
that model size or runtime speed caused v7's source relation errors.

The provider-free [private sufficiency packet builder](../scripts/build_private_source_sufficiency_packet.py)
discovers exact source windows with authored patterns, excludes previously
reviewed pages, and writes an unreviewed manifest and escaped HTML only in
owner-private OS Temp storage. Its default command is a no-database preflight;
explicit creation uses current owner/publication/revision/space filters and a
read-only transaction. Human source-fidelity, excerpt-sufficiency and PDF-page
labels are required before conversion to a frozen probe roster. A partial
packet cannot pass the twelve-positive/sixteen-pair gate. The earlier expanded
discovery found ten positive candidates (3 direct, 4 paraphrase, 3 follow-up)
and five insufficient-pair candidates on ten distinct pages in three documents;
received three positive excerpt/page Yes, six No and one omitted decision,
with five insufficient-pair No decisions; source-fidelity decisions remain
unreviewed. These counts describe template discovery, not source
scarcity, actual Ask output or corpus-wide absence.

An optional `--authored-spec` input lets the owner nominate bounded private
questions for previously unexposed pages. It is an absolute OS Temp JSON file
with literal-only patterns, at most 64 KiB and 64 cases; schema, relations,
lengths and duplicate IDs are checked before the read-only database snapshot.
Its digest is bound to the unreviewed packet. No authored question, excerpt or
source text belongs in tracked fixtures or logs. A matched page is still only
a discovery candidate: an independent evaluator must label source fidelity,
exact excerpt sufficiency and original PDF page usefulness before a gold roster
can be frozen. The operator delegated subsequent evaluation to engineering
agents on 2026-09-27; previous owner labels remain immutable. Previously exposed pages and development labels cannot be used
as independent holdout evidence. No complete reviewed
12-positive/16-insufficient set has been established. The current narrow
interrogative-parser correction has v5 retrieval/selector snapshots within the
same eight families; v4 measurements remain historical v4 evidence.

The approved v6 amendment permits exact canonical-page windows anchored to a
current eligible chunk. It preserves the owning heading when chunking retained
that heading only as metadata. Count full inspected page text against the
8,192-token budget, along with admitted chunks. Measurements record source kind
and exact source-slice validation; canonical-page offsets must align directly
with the opened page. Chunk containment alone is no longer the page-window
criterion. The twelve independently reviewed page gold cases and sixteen
insufficient controls are frozen before v6 runtime measurement; source coverage
and original-PDF labels alone cannot pass the displayed-window gate.

The provider-free [source-pair evaluator](../scripts/evaluate_private_source_sufficiency.py)
audits frozen owner-reviewed insufficient windows and their paired sufficient
windows. The default command opens no database. Explicit execution requires
`--execute`, `--controls`, `--candidate-manifest` and `--profile`; all three JSON
files must remain in private OS Temp storage, at most 512 KiB each. The profile
contains only an explicit local `postgresql+asyncpg` database URL, which must
never be printed or committed. It does not read root `.env` or invoke providers.

Before constructing a reader, the evaluator checks the candidate manifest
digest and exact records, the controls digest, runtime and evaluator source
fingerprints, and owner labels. At least sixteen distinct insufficient windows
are required, with two per declared relation and reviewed sufficient controls;
`Unsure`, missing labels and unsupported relation parsing cannot pass. Each
window is at most 480 characters; the audit accepts at most 64 pairs and is
bounded to 120 seconds. Current instructor ownership, Subject, selected
documents, publication/readiness, content/index/corpus revisions and embedding
space are reauthorized in read-only PostgreSQL snapshots before and after
evaluation. Chunk/page hashes and exact offset alignment must still match.

Only the reviewed window is examined. Any qualifying subspan in an insufficient
window is a false-primary failure; a cropped sufficient window is unknown
unless the exact reviewed window is selected. Review of a larger window does
not label its subspans. The CLI reports aggregate per-relation counts and safe
failures without private questions, excerpts or source identities. A passing
pair audit never establishes whole-page/corpus absence, retrieval usefulness,
actual page opening or the separate release gate. See its
[synthetic contracts](../backend/tests/test_private_source_sufficiency.py).

Public negative controls now include same-unit predicates belonging to a
different entity, wrong numeric ranges and entity-free metric questions with
missing discriminators. Passing them does not prove semantic sufficiency.
The operator approved explicit property/limitation and application/example
families after the six-family selector could not cover the reviewed seed
questions. Their v3 owning-heading/bullet units and the v4 extension to the
other six families are under validation. Qualification remains an evaluation
candidate and cannot be activated from the public suite alone. For operator
diagnostics, retained rank pairs cover
only the first five candidates; content-free selection logs expose aggregate
inspection/selection counts, not all twenty source identities.

## Retrieval and support result

`hybrid_exact_v1` uses exact Subject-filtered cosine search and PostgreSQL
`simple` FTS, each capped at 20 candidates. It fuses with reciprocal-rank
fusion `k=60`, returns at most 5 chunks, requires vector similarity at least
0.5, deduplicates same-page term overlap at 0.8, and caps retained context at
8,192 estimated tokens. RRF is a rank score, not a probability or confidence.

The current disposable PostgreSQL run evaluated seven feasible direct,
paraphrase, technical, multi-page, overlap, injection and cross-lecture queries
against actual pgvector cosine plus FTS. All reviewed gates passed: recall was
1.00, MRR met the 0.80 floor, forbidden-source exposure was zero, overlap stayed
within 0.20, exact-query p95 stayed below 2 seconds and indexing exceeded one
chunk/second. An unrelated query returned empty evidence. The complete Phase 20
service run passed 82 PostgreSQL tests, with 3 intentionally gated skips, and also
completed head/drift, downgrade-to-base and re-upgrade-to-head checks.

The answer contract permits only one-to-five ordered claims, each linked to one
retrieved chunk and an exact contiguous quote. After the single remote answer,
the local `local_nli_qa_v1` gate requires quote-to-claim entailment, an
extractive answer span relevant to the question and no dominating contradictory
sentence in the retrieved evidence. Unknown, duplicate, fabricated, stale,
irrelevant or unsupported citations fail closed. Empty retrieval, ambiguity,
conflicting evidence, model abstention or support rejection produces the fixed
server-issued abstention without citations. A local inference failure is never
replaced with the retired remote support call.

No HNSW or IVFFlat index ships, so filtered ANN recall and iterative-scan tuning
are explicitly not applicable; the exact query is the baseline, not a silently
missing comparison. The evidence did not justify changing top-K, RRF,
similarity, shared page-aware chunking or the 8,192-token context cap. It also
did not justify a reranker. Any future ANN, reranker or RAG-specific chunk
version needs separately reviewed corpus-scale recall/latency evidence and must
preserve the flashcard regression baseline.

## Lane 4 isolated PostgreSQL ablations

The 2026-09-23 disposable PostgreSQL test reindexed four copies of the same
canonical pages with deterministic local vectors. Nine authored queries
compared the shipped exact policy with one-term lexical search and immutable
section context, then compared 32-token chunks with 16-token chunks with and
without four-token overlap. Only canonical chunk text remained citable.

| Isolated policy or chunking | Recall@5 | MRR | Exact-query p95 |
| --- | ---: | ---: | ---: |
| Shipped `hybrid_exact_v1`, 32 tokens, no overlap | 0.889 | 0.889 | 5.475 ms |
| One bounded lexical term | 1.000 | 1.000 | 5.849 ms |
| Immutable section search context | 1.000 | 1.000 | 4.198 ms |
| Both lexical and section changes | 1.000 | 1.000 | 5.388 ms |
| 16 tokens, no overlap | 0.889 | 0.889 | 6.109 ms |
| 16 tokens, four-token overlap | 0.889 | 0.889 | 6.141 ms |

With duplicate documents competing for the top five, optional cross-document
diversity reduced repeated canonical text from 0.50 to 0.00 while retaining
recall@5 and MRR of 1.00; measured query time changed from 5.008 to 5.386 ms.
The shipped retrieval policy remains unchanged because these small synthetic
ablations do not establish a general quality gain. The test uses fake vectors,
so it does not measure real `gemini-embedding-2` retrieval or a title benefit;
the editable document title is excluded from the indexed representation.
The 2026-09-25 rerun added bounded-OR lexical retrieval on the same nine
authored cases: recall@5 and MRR were both 1.00, duplicate rate was zero and
query p95 was 6.6 ms. Opt-in OR also passed disposable owner/enrollment,
publication, selected-document and corpus-fence checks. These synthetic
measurements do not replace the private reviewed/hybrid comparison gate.

## Lane 0 paused diagnostic baseline

The focused Lane 0 corpus runs only deterministic query embeddings and the
real exact pgvector/FTS retrieval path. Its report records vector and lexical
candidate ranks, selected evidence pages, retrieval latency, and the current
answer/support fields for every case. Since Ask admission and execution are
paused, every observed answer outcome is `not_run_ask_paused`, false
abstention is `not_measured`, remote tokens/cost/physical calls are zero, and
the local-support verdict is explicitly `not_implemented`. The future expected
accept/reject labels remain authored evaluation targets for Lane 5; they are
not claimed as measured results. The
[dated implementation record](../.agent/logs/2026-09-22/2026-09-22-product-quality-lanes-0-1-implementation.md)
contains the captured report and verification boundary.

## Lane 5 local-support result

`scripts/evaluate_local_support.py` loads the pinned local NLI and extractive-QA
ONNX artifacts, repeats the eleven-case Lane 5 corpus and emits only content-free
case IDs and resource measurements. It performs no network or provider call.
The 2026-09-23 installed-bundle run repeated every case three times: all 11/11
cases passed, with zero supported false rejections and zero unsupported false
acceptances. The verified bundle was 181,734,633 bytes, model startup was
3,248.539 ms, p95 check latency was 82.263 ms and the measured working-set
increase was 330.555 MiB. All fixed release ceilings passed. The same-case
design comparison scored literal quote only 4/11, NLI only 9/11, literal
extractive QA only 8/11 and the selected combined gate 11/11. A definition
question that extracted a nonliteral phrase initially failed the live local
gate. The corrected policy requires independent QA on the claim and at least
0.90 bidirectional NLI equivalence for that phrase; the additional authored
case passes without weakening the existing entailment or conflict thresholds.

This small authored corpus establishes the selected policy's checked direct,
paraphrase, relevance and conflict controls on the measured host. It does not
establish general semantic accuracy, another platform's resource behavior or a
remote answer model's current quality. Retain the existing citation, privacy,
retrieval and abstention gates alongside it.

## Lane 6 private-course diagnostic boundary

The separately authorized 2026-09-26 BLEU test verified seven affected runtime
source digests against the current checkout before using that image. It made
one query embedding plus one answer request with no retries. Baseline top-five
retrieval contained the expected expansion; the answer claim also contained it,
but its short quote omitted the acronym subject. Local entailment was 0.675
and QA found no span, so v1 refused at `entailment_rejected`. This distinguishes
the sampled support/output-window failure from an evidence-retrieval miss or
provider outage. The USD 0.00270285 usage-price estimate is not an invoice;
embedding usage and previous-attempt cost remain uncertain. See the
[dated diagnostic record](../.agent/logs/2026-09-26/2026-09-26-real-query-and-ask-diagnostics.md).

The [real-query diagnostic](../scripts/evaluate_private_query_retrieval.py)
is provider-free by default. Separately authorized execution uses one native
Embedding 001 request for six authored questions, retains the active
`QUESTION_ANSWERING` task/space, and compares read-only local retrieval policies
using the same in-memory vectors. Its result must remain separate from generated
answer quality, reviewed holdout coverage and source-representation cutover.

The first separately approved six-question batch attempted once, with no
retry or answer call, but returned no usable metrics. Its original safe catch
did not retain a failure stage; the reason and actual cost remain unknown.
The harness now reports whitelisted failure stages and preserves attempt/usage
provenance. A subsequently reproduced ORM rollback-context defect was repaired
and its current stored-source-vector SQL oracle completes. That oracle does
not diagnose the prior paid call or qualify a real-query retrieval policy.

After a fresh scoped approval, the repaired harness completed one six-question
embedding request with zero retries. Baseline actual-query page/chunk recall@5
was 1.0 and page MRR 0.6944; bounded AND/OR/OR-section/OR-section-diversity
MRR was 0.5833/0.4778/0.6111/0.6111, with OR recall falling to 0.8333.
All remained below the preregistered MRR 0.8/nonregression selection gate.
Keep the exact baseline; these variants do not justify a retrieval cutover.
The USD 0.0000206 local estimate is not a receipt and does not resolve the
previous attempt's unknown cost. No answer call, reindex or vector persistence
occurred. Six direct questions do not establish paraphrase/followup/holdout quality.

The separately approved [public calibration audit](../scripts/calibrate_local_relation.py)
uses the same pinned instruction artifact and unchanged joint prompt, 96
independently reviewed public cases, and one preregistered public-only rule
selection. Its [frozen corpus](../backend/tests/fixtures/rag_eval/local_relation_calibration_v1.json)
separates 24-positive/24-negative calibration and heldout scenarios/constructions.
Global nonlabel winners, missing complete inputs and uncertain/unavailable
decisions cannot count as semantic passes. Calibration failure keeps heldout
closed; even a public pass cannot activate runtime support or prove private
course quality. See the [preregistration and evidence](../.agent/logs/2026-09-26/2026-09-26-local-relation-calibration.md).

The one public calibration audit completed 48 inferences: seven correct global
A/B labels and 30 nonlabel winners; eleven of the eighteen A/B winners were
wrong. No preregistered rule passed. Heldout and private replay remained closed.
Startup was 14.90 seconds, complete-case p95 3.17 seconds and peak additional
RSS 2,000.70 MiB. The candidate remains unselected: a confidence-floor change
alone does not correct its observed classification errors. No provider request,
database write or runtime activation occurred.

The owner subsequently approved one isolated Qwen3-4B CPU export experiment,
using the same frozen public fixture, joint task and calibration procedure.
The [supervisor](../scripts/calibrate_local_relation_4b.py) enforces startup30s,
whole-audit600s and ten-second complete checks under the separate experimental
memory/CPU limits. Its [candidate](../scripts/local_relation_4b_candidate.py)
checks immutable bytes and graph/external-data contracts before model loading.
The final 519-byte public model card remained unavailable after the separately
approved corrected-root request. One expressly approved seven-runtime-file
diagnostic then timed out at the **30-second startup bound**, before a validated
case result. It cannot classify the model's semantic quality, does not qualify
the incomplete artifact bundle and leaves the selected Ask policy unchanged.
No activation follows from artifact transport or offline harness tests. See the
[current experiment record](../.agent/logs/2026-09-26/2026-09-26-local-relation-4b-experiment.md).

The 2026-09-25 read-only local probe narrowed a reproduced support-rejected
question to currently reviewed, published, ready Knowledge. Full-question and
bounded-AND lexical searches found no eligible chunks; a bounded-OR lexical
probe found five eligible chunks with relevant concept flags. This establishes
an FTS candidate-channel miss, not a historical hybrid top-five miss: the old
job retained neither its query vector nor its discarded source selection. Two
source-contiguous authored-claim checks returned one local entailment rejection
and one contradiction rejection. Without an owner-reviewed claim/evidence label,
neither is classified as a verifier error. The other retained questions and
the source's distinct fact capacity remain under review. Private questions,
document text, source identifiers and model output stay outside tracked
fixtures and logs.

The separate read-only, no-provider
[`evaluate_private_rag_corpus.py`](../scripts/evaluate_private_rag_corpus.py)
probe compared 21 local lexical-only cases from retained owner questions and
ephemeral authored paraphrase, unresolved-follow-up and unsupported controls.
Six distinct direct questions covered BLEU expansion and evaluation focus,
bag-of-words, logistic regression and topic modeling; the retained Subject had
no cosine question. Eleven direct or paraphrase cases had a machine-detected
topic concept somewhere in currently authorized, published chunks. These are
**source-discovery proxies**, not owner-reviewed relevance or answer labels.

| Lexical-only ablation | Proxy recall@5 | Proxy MRR | Duplicate rate | Query p95 |
| --- | ---: | ---: | ---: | ---: |
| Full-question AND | 0.000 | 0.000 | 0.000 | 39.4 ms |
| Twelve-term AND | 0.000 | 0.000 | 0.000 | 33.4 ms |
| Twelve-term OR | 0.818 | 0.408 | 0.000 | 37.8 ms |
| Twelve-term OR plus section | 0.818 | 0.523 | 0.000 | 41.1 ms |
| Twelve-term OR plus diversity | 0.818 | 0.408 | 0.000 | 40.1 ms |

OR also returned candidates for all five generic unresolved follow-up and all
five unsupported-question controls. Candidate retrieval alone does not establish
that an answer is supported. The historical exact-v1 **hybrid vector plus FTS**
top-five evidence is unavailable because rejected jobs did not retain the query
vector or selected chunks. Therefore these lexical-only metrics cannot prove a
hybrid recall improvement or justify activating another retrieval policy. The
pre-registered cutover gate requires owner-reviewed answerable cases in at least
five topics, no recall@5/MRR regression against the actual hybrid baseline,
zero unauthorized/private exposure and zero unsupported or conflicting accepted
answers. The opt-in retrieval switches remain outside queued Ask policy snapshots.
The page-number-only review hints are emitted locally by the script and are not
stored in this document.

A subsequent read-only audit matched each of the three published Knowledge
documents to an original local lecture PDF by exact file digest and visually
reviewed the five owner-confirmed answer-bearing pages. The original PDF,
canonical stored page and eligible indexed chunk all retain the relevant
facts for bag-of-words/TF-IDF, topic modeling, cosine similarity, BLEU and
logistic regression. Native PDF extraction and the canonical stored text
matched exactly on those pages, and every nonempty canonical line appeared in
the eligible chunk body or its section field. This rules out missing PDF text
or failed indexing for these five reviewed facts; it does not reconstruct a
historical Ask selection or prove that the current retrieval policy ranks
every fact within its top five. On the cosine page the concept name resides
in the chunk's section field while the angle/magnitude explanation resides
in its body, so body-only lexical lookup can miss that heading. Temporary
page renders were removed; the audit made no provider calls or database edits.

After the lexical proxy run, the owner reviewed narrow original-PDF page
locations and confirmed source concepts across five distinct topics, including
two BLEU question forms. This establishes that the visibly rendered PDF has
the facts the owner expected. It does not prove all facts survived canonical
text extraction or that a particular old job selected the relevant chunk.
The content-free current-policy inventory contains 12 completed abstentions,
each with a support rejection, and five answer-stage failures, with no retained
supported answer. Historical model claims and selected source chunks were not
stored, so those counts alone cannot identify false local-verifier rejections.

Correction to the initial cosine page probe: keyword-based discovery selected
page 23, a recap that mentions cosine but does not state the requested
angle/magnitude distinction. Its 518-character canonical text exactly matched
native pypdf extraction and the independent pdfplumber extraction was similar;
the neutral 0.985/no-QA result for that page was expected, not evidence of an
extraction defect. Visual inspection of the exact source PDF located the
explicit sentence and formula on page 13. The current canonical page 13 text
contains that sentence, and a local-only authored claim/contiguous-quote probe
passed the pinned support gate (entailment 0.993). This supports answerability
for that reviewed page, but does not reconstruct the evidence or claim selected
by a historical Ask job. Source-discovery proxies must distinguish topic
mentions from answer-bearing passages before they become evaluation labels.

The separately authorized 2026-09-25 private Ask diagnostic used one physical
query embedding and one physical answer request. On that current published case,
the shipped exact-v1 hybrid and diagnostic bounded-OR policies each selected
five eligible chunks containing the targeted concept; exact-v1's selected rows
had vector ranks 1–5 and no lexical ranks. This is direct evidence that the
**current** exact-vector channel recovered concept-bearing candidates for that
case. It does not reconstruct the older screenshot attempt, establish that the
answer model made a correct supported claim, or justify switching retrieval.
The answer stage failed with the safe `ai_provider_unavailable` category before
local support ran; the underlying provider outcome and cost remain uncertain.
The diagnostic made no automatic retry. The read-only comparison harness's
cleanup issue was repaired and its keyless guards passed afterward.

The separately approved second one-shot comparison used the shipped exact-v1
evidence for the answer. Both retrieval policies again selected five eligible
chunks containing the target concept. Exactly one embedding and one answer
request occurred, with no automatic retry. The answer failed before local
support with safe `ai_provider_unavailable` / `http_server_error` codes. The
USD 0.01107135 conservative admission estimate is not a provider receipt;
actual answer-call cost remains unknown. The 415-byte provider JSON schema and
roughly 1,200-token admitted answer input do not themselves establish why the
server returned 5xx. The owner later approved a third one-shot attempt with the
same explicit envelope. It again selected five concept-bearing chunks under
each retrieval policy and made one embedding plus one answer request, with no
automatic retry. The answer provider returned `STOP`, one claim, 1,126 combined
input tokens and 114 output tokens. The local gate rejected the claim as
`entailment_rejected`. Since the diagnostic never retained its private
claim/quote, it cannot label the generated claim correct or classify that
verdict as a false rejection. USD 0.00270285 is an estimated usage cost, not a
bill; prior-attempt cost remains unknown. No supported answer was established
by these three live runs. Additional calls require separate owner approval and
a reviewed endpoint/model/price/call/token/time/cost bound.

For the reproduced BLEU acronym shape, an additional local-model ablation
excluded the cited chunk from the contradiction scan. The same authored-claim
rejections remained: one entailment and one contradiction from other selected
evidence. Neither quote had multiple sentences, so rechecking a component of
its own quote did not explain this case. No original rejected model claim or
source selection survives for replay. There were zero retained successful
citations in this owner's Subject from which to measure a real quote/claim
token-length distribution. Do not lower NLI, QA or contradiction thresholds or
change the 384-token contract based on these probes.

A subsequent visual review of the original PDF located the BLEU acronym and
evaluation-focus evidence on its published page 22. A read-only local probe of
that page's current canonical chunk tested authored claims with contiguous
quotes. For the correct acronym claim, the shortest quote scored 0.992 NLI
entailment and yielded a QA span; nevertheless the whole-chunk contradiction
scan rejected it. Five of six sentence units in that chunk received a
contradiction score above 0.50 against the claim, including units about a
different metric or without the BLEU acronym. Their QA checks for the acronym
question yielded no answer span. A short focus quote likewise passed NLI
(0.942) and QA but was rejected by the whole-chunk contradiction scan; longer
source windows sometimes made extractive QA return no span. Authored false
acronym and recall-instead-of-precision controls failed entailment with high
contradiction scores. This demonstrates a local-verifier false rejection for
**these authored, reviewed page-22 positives**, not for the unknown claim from
the third live provider run. The global sentence scan and quote-window
sensitivity need a versioned, negative-controlled support-policy evaluation
before Ask admission can pass the quality gate.

Historical, retired execution: `scripts/compare_private_ask_once.py` now refuses
`answer_generation_retired` before any paid call. The former diagnostic used an
envelope for one current published case on the configured local installation.
It compares the exact-v1 and bounded-OR candidate retrieval with the same
single query embedding, then sends at most one selected evidence set for one
answer. It requires separate operator approval for the endpoint, current
`gemini-3.6-flash`/`gemini-embedding-001` profile, conservative prices, two
physical calls, 512 embedding/12,000 answer-input/1,024 answer-output
estimated tokens, 30 seconds per provider call, 60 seconds overall and a
USD 0.04 admission ceiling. It does not run from CI or a normal test. Only
allowlisted aggregate ranks, verdicts, usage and uncertainty are emitted. An
opt-in first-claim diagnostic also reports bounded NLI token count/scores,
QA-span presence and fixed BLEU concept flags; it never emits claim or quote
text. A failure in that diagnostic does not replace the normal support verdict.
An admitted estimate is not a provider invoice. See [AI evaluation](AI_EVALUATION.md)
and the dated Lane 6 implementation record for the exact observed result and
whether a reviewed retrieval/support policy was selected.

A fourth separately approved BLEU comparison again found the target concept in
the shipped top five and diagnostic candidate top five. It made one embedding
and one answer request, with zero automatic retries. The answer provider
returned a safe HTTP 503 server-error outcome before generating a claim, so
the new first-claim diagnostic did not run. The conservative admitted estimate
was USD 0.01107135; actual cost remains unknown without a usage receipt. This
is a distinct transient provider failure, not a retrieval or local-support
result. No answer/retrieval policy was activated from it.

A later provider-free private support comparison selected six fixed authored
positive/negative question shapes across the five owner-confirmed topics from
currently eligible published chunks in the matching active space. It selected
an exact, shortest contiguous line window for each case. Both the shipped v1
verifier and an unshipped structural v2 candidate rejected all six authored
positive claims; both also rejected all six wrong-claim controls. The v2
candidate only removes a clearly separate headed topic from the conflict scan,
so same-topic ancillary BLEU facts still cause false contradiction. Other
positives failed quote entailment or extractive question relevance. The cosine
quote alone lacks the subject name, which is in the chunk section. These
automatically chosen exact quote/claim pairs were not individually reviewed by
the owner, and no answer-model output was replayed; 0/6 is **this diagnostic's
feasible-claim yield**, not general Ask accuracy. The evaluation used no
provider requests, database writes or private text in output. It is a release
gate failure: do not activate this v2 candidate or spend the remaining approved
live Ask attempt on v1.

The owner later reviewed the local-only six-case sheet and confirmed all six
selected quote/question/positive-answer pairs, all six negative controls and
their original-PDF page meaning. This upgrades those six exact pairs from
machine-selected candidates to owner-reviewed labels. It does not turn the
single-source diagnostic into model-output or real-query retrieval evidence.

The [Lane 6 private review packet builder](../scripts/build_private_lane6_review_packet.py)
extends those six direct seeds with authored paraphrases, one resolvable and
one ambiguous follow-up, and explicit negative/control placeholders. Running it
without `--create` performs no database read; `--create` reads the current
authorized, reviewed/published source and writes one escaped static
`review.html` in a new neutral-named directory under the OS Temp directory.
It prints only the neutral local path, fixed availability counts and zero-call/
zero-write status. The create command requires
`CARDCH_LANE6_REVIEW_OUTPUT_DIR` to name the exact writable Temp root; in the
answer-worker container it must be the `/lane6-review` bind mount, and `TMPDIR`
must resolve to the same mount. An absent mount or Python Temp fallback fails
before any database read. With the local development stack already running,
the PowerShell invocation from the repository root is:

```powershell
$lane6ScriptsPath = (Resolve-Path -LiteralPath .\scripts).Path
$lane6TempPath = [System.IO.Path]::GetTempPath().TrimEnd('\')
docker compose --profile development -f docker-compose.yml -f docker-compose.dev.yml run --rm --no-deps -T `
  -v "${lane6ScriptsPath}:/diagnostics:ro" -v "${lane6TempPath}:/lane6-review" `
  -e TMPDIR=/lane6-review -e CARDCH_LANE6_REVIEW_OUTPUT_DIR=/lane6-review `
  answer-worker python /diagnostics/build_private_lane6_review_packet.py --create
```

The returned `/lane6-review/.../review.html` maps to the host Temp directory.
Open the file locally, compare each exact excerpt to
the indicated original PDF page and record Yes/No/Unsure by case ID outside
the repository; browser radio choices are not saved. Do not copy source text
into logs or tracked fixtures, and remove the exact Temp packet directory after
the owner has recorded decisions. Eight source-free rows are labelled planned
separate controls, with no owner radio selection; they are not application
errors. In particular, N02 needs a separate corpus-wide unsupported-question
evaluation, while unpublished/cross-Subject, provider/schema and generation
controls need their own guarded tests or source review. N01 asks whether its
selected excerpt alone rules out the wrong claim; a No means the excerpt lacks
counter-evidence and must not be silently converted to a passing negative.
This packet does not by itself
finish the representative corpus, real-query holdout or Ask quality gate. Any
later replay must reauthorize the same Subject, published revision and embedding
space; discard the labels if the source snapshot has changed.

The [separate private negative packet](../scripts/build_private_lane6_negative_packet.py)
offers two authored wrong claims against source excerpts selected for explicit
counter-evidence and one true but question-unrelated claim. It excludes the
earlier N01 acronym alternative because the owner found its selected excerpt
insufficient to refute that claim. For the unrelated case, review source support
and question relevance separately; only an independently reviewed explicit
refutation, or source-supported but irrelevant pair, can become a negative
quality label. A plausible wrong answer, a source pointer, or an unrun control
does not count. This script uses the same current authorized published-source
scope and Temp-output guard as the first packet. Its default command reads no
database; the optional creation command below makes no provider request or
database write and reports no private content:

```powershell
$lane6ScriptsPath = (Resolve-Path -LiteralPath .\scripts).Path
$lane6TempPath = [System.IO.Path]::GetTempPath().TrimEnd('\')
docker compose --profile development -f docker-compose.yml -f docker-compose.dev.yml run --rm --no-deps -T `
  -v "${lane6ScriptsPath}:/diagnostics:ro" -v "${lane6TempPath}:/lane6-review" `
  -e TMPDIR=/lane6-review -e CARDCH_LANE6_REVIEW_OUTPUT_DIR=/lane6-review `
  answer-worker python /diagnostics/build_private_lane6_negative_packet.py --create
```

The returned local HTML requires owner review of the exact excerpt and original
PDF page. Radio choices are not saved, and labels remain pending until reported
by case ID. Source selection or page-alignment failure removes the review
controls for that case. Remove only the exact task-created Temp directory once
review decisions have been recorded.

The owner reviewed one generated packet on 2026-09-26: N11 was **No** because
the selected excerpt did not explicitly refute the candidate; N12 was **Yes**
for explicit refutation; and U01 was **Yes** for source support but **No** for
question relevance. Thus N12 and U01 provide two distinct reviewed negative
shapes, while N11 remains unusable as a contradiction label. These decisions
are tied to those exact source excerpts and need current publication/revision/
space revalidation before a later replay. They do not show that any local
verifier or Ask policy handles the cases correctly.

A separate read-only source-window ablation compared those fixed chunk quotes
with exact contiguous heading-to-answer spans from the immutable canonical
pages. Cosine's 35-token page span raised quote-to-claim NLI entailment from
0.528 to 0.991 and produced a QA span; the current chunk quote lacks the
concept heading held in `section`. A non-contiguous section-plus-quote
composite gave the same local scores, but is **not** a valid citation under the
current contiguous-chunk contract. The extracted cosine answer span is not
contained in the authored claim, so equivalence still needs a separate check.
For BLEU acronym, the exact page span equals the current quote and the global
contradiction veto remains. Bag-of-words and logistic spans had entailment
0.904 and 0.962 but no QA answer span; topic modeling's selected page span
was neutral at 0.978; a safe BLEU-focus heading span could not be selected.
Thus heading preservation has measured value for one topic but is not a
complete Ask fix. Reindexing the real Subject would require separately
authorized document embeddings and a versioned rollout; staging currently
bumps corpus revision and can hide earlier citations even while Knowledge
remains published. This history behavior needs an explicit product decision
and disposable regression before any cutover.

A QA-on-generated-claim fallback would have opened two of those six authored
positives in a local probe, with no wrong controls accepted in that small set.
It is not a safe release rule: a span extracted from the model's own claim
and merely present in the quote does not prove the source expresses the
questioned relation. With a false NLI entailment, swapped entities, negation
or an incidental same word can pass. Keep a missing source-QA span as a
fail-closed result while testing a stronger independent source-question check.

An offline, public synthetic comparison also checked the pinned quantized
`cross-encoder/nli-deberta-v3-base` ONNX artifact as a possible replacement for
the small NLI model. Its 244,422,412-byte model file projected a 323.08 MiB
complete verifier bundle with the retained QA/tokenizer files, above the
current 200 MiB release cap. On six synthetic NLI pairs, it scored an
unrelated ROUGE-to-BLEU statement as 0.958 entailment and a same-BLEU wrong
acronym as only 0.449 contradiction, below the current 0.50 conflict gate.
These are isolated NLI scores, not full-verifier false acceptances because QA
and quote checks still apply. No private corpus or provider call was used;
the pinned artifact checksum was verified and its temporary download removed.
The larger model was not selected. Scope-aware source evidence and reviewed
adversarial evaluation remain necessary before a verifier cutover.

A separate provider-free quote-window ablation tested 64 bounded, exact
substrings from the currently eligible chunks across the six authored cases.
The shipped full local verifier accepted one positive window, for the logistic
case, and zero of 64 wrong-claim windows. A fixed shortest window had accepted
zero positives. Quoting each entire eligible chunk also accepted zero of six
positives, so more context is not a general fix. This was a single-chunk
diagnostic: those quote/claim pairs had not been individually owner-reviewed,
and the normal top-five conflict context was not replayed. Choosing whichever
window passes a verifier would increase the multiple-candidate false-accept
surface; retain a deterministic source-window rule and adversarial gate before
using any such selection in Ask.

A dormant v2 answer contract now gives the model bounded start/end IDs for
server-issued, offset-preserving source units and derives the exact contiguous
quote, chunk reference and joined answer on the server. Migration `0020`
extends the v1 one-embedding/one-answer stage constraint and remote-attempt
uniqueness to this future policy. The active release constant, provider factory
and local support policy remain v1. Worker fakes and disposable PostgreSQL
tests prove the dormant contract's source binding, citation rejection and call
caps; they do not prove answer quality.

The read-only, keyless six-case replay on the local published Knowledge now
binds all six owner-reviewed quote selectors to server-issued unit ranges after
grouping PDF line wraps within sentences and permitting up to six adjacent
units under the unchanged character/token caps. The current full verifier
accepted none of the six bound positives; wrong-claim and unrelated-question
controls also remained rejected. These are single-source diagnostics whose six
exact quote/question/claim pairs were confirmed by the owner on the private
local review sheet. There were zero model-answer replays and no real
query-vector replay. An unshipped narrow
verifier V3 prototype improves a synthetic exact acronym case while preserving
the wrong-expansion rejection. A separate read-only, single-source run of V3
on the six selected private quotes accepted zero of six authored positives,
so the synthetic improvement does not translate to this course sample. It has
not passed the broader adversarial release gate. The only active verifier
change here rejects an empty or whitespace-only extractive QA span, which
cannot establish relevance.

Further provider-free, read-only comparisons on the six owner-reviewed
source/claim pairs did not find a safe replacement. Collapsing PDF whitespace
before local QA left all verdicts unchanged. A quantized MiniLM NLI candidate
accepted zero of six positives and scored one wrong expansion as more likely
entailed than the pinned NLI model. A quantized DistilBERT QA candidate with
the pinned NLI model accepted one of six positives and no sampled controls.
Both public model bundles were checksum-verified for the probe and removed;
neither is selected. The corrected v2 replay reports one positive rejected at
contradiction, four at entailment and one at question relevance. This makes
the support-policy gate the measured blocker; relaxing one numeric threshold
or replacing one small model has no demonstrated safe release benefit.

A separate provider-free retrieval ablation compared the active exact-vector
plus lexical policy with bounded AND/OR, section and diversity candidates on
the same six page-confirmed probes. It used stored source-chunk vectors as
explicit oracles or different-topic surrogates because historical Ask query
vectors were not retained. With source oracles, the active baseline reached
6/6 page recall@5 and MRR 1.0; simple bounded OR fell to 5/6 and MRR 0.70.
Section/diversity restored 6/6 in that surrogate setup, but different-topic
surrogates mostly missed and none of these vectors represents a real Ask query.
The comparison is useful for rejecting an unqualified OR cutover; it cannot
justify changing retrieval without reviewed answerability and real query
embeddings under the same remote-call envelope. No retrieval policy changed.

## Live deployment-model boundary

The operator approved a separate larger-local-verifier experiment on
2026-09-26: up to 1 GiB model artifacts, 2 GiB additional RSS, 20 seconds
startup and 5 seconds p95 support latency. These are experimental ceilings,
not changes to the maintained release thresholds above. The small pinned
runtime bundle and current policy remain active. Public artifact downloads
must be revision/digest pinned; private Knowledge stays local and this
experiment makes no provider calls. Compare the owner-reviewed positives,
wrong claims, unrelated questions, conflict/ambiguity/injection controls and
the maintained corpus before proposing a runtime budget change.

The approved experiment was completed with the keyless, read-only
[larger-verifier evaluator](../scripts/evaluate_larger_local_support.py).
Revision/digest-pinned quantized DeBERTa-v3-base MNLI/FEVER/ANLI and
RoBERTa-base SQuAD2 artifacts totalled 381,768,174 bytes (364.08 MiB).
An isolated container was limited to two CPUs and 2 GiB total memory; the
installed bundle and runtime factory were untouched. Each combination ran
three repetitions of six reviewed single-source positives, their six wrong
claims and six unrelated questions, plus the maintained eleven-case corpus.

| Combination | Reviewed positives | Wrong claims / unrelated questions accepted | Maintained corpus | Current-quote p95 | Canonical-page p95 |
| --- | --- | --- | --- | --- | --- |
| Installed NLI + installed QA | 0/6 | 0/6 + 0/6 | 11/11 | 123.02 ms | 139.36 ms |
| Larger NLI + installed QA | 1/6 | 0/6 + 0/6 | 11/11 | 372.23 ms | 442.32 ms |
| Installed NLI + larger QA | 0/6 | 0/6 + 0/6 | 11/11 | 154.08 ms | 173.09 ms |
| Larger NLI + larger QA | 1/6 | 0/6 + 0/6 | 11/11 | 422.03 ms | 402.45 ms |

Startup was 13.88 seconds for current quotes and 15.17 seconds for the
separate canonical-page hypothesis. Sampled resident-memory increase was
973.92 and 973.65 MiB respectively; this is not a peak-memory measurement.
All sampled private verdicts were stable across the three repetitions.
Only the acronym positive improved. The second experiment found six bounded
exact page windows, but three were not citable under the current body-only
chunk contract. It used hypothetical page evidence, not a deployed citation
policy. There were no provider calls, database writes or real model-answer
replays. Resource feasibility and the sampled negative results do not establish
general safety or answer quality: the larger artifacts remain unselected,
release budgets remain unchanged, and five reviewed positives still fail.

The owner then approved one isolated instruction-model candidate with at most
three predeclared configurations under the same experimental resource ceilings.
The [relation classifier](../scripts/local_relation_candidate.py) checks
source/claim entailment, question/claim answerability and same-proposition
conflicts, independently of Gemini generation. It uses exact source-unit slices
and a decision token only, not a replacement answer or a Gemini self-check.
Unknown, malformed, low-confidence or inconsistent decisions safely abstain;
they do not count as successful semantic negatives. The
[evaluator](../scripts/evaluate_local_relation.py) pins public fixture identities
before reporting labels, bounds every private/public case and reports failed
development configurations after one repetition. Only a complete pass advances
to the required three repetitions. The
[24 public adversarial controls](../backend/tests/fixtures/rag_eval/local_relation_adversarial_v1.json)
add conflict, distractor, ambiguity, negation, changed-number, mixed-claim and
injection cases; they are development controls, not an independent reviewed
holdout. No runtime policy, model bundle, dependency or release budget changes
during this experiment. See the
[dated experiment record](../.agent/logs/2026-09-26/2026-09-26-local-relation-checker-experiment.md)
for candidate identity, CPU preflight, measured results and remaining gates.

The first approved instruction-model experiment completed all three declared
configurations with **0/6 reviewed private positives** each. No configuration
qualified for the three-repeat gate. Startup was 13.27 seconds, peak RSS
increase 2,000.94 MiB, and joint-check p95 5.08 seconds. The latter exceeds the
experimental latency ceiling. Joint-check conclusive passes were 2/11 on the
maintained corpus and 1/24 on the new adversarial corpus; nine unavailable and
39 uncertain decisions among its 53 cases were not counted as semantic passes.
Its private wrong-claim/unrelated-question acceptances were zero, but this
does not establish useful verification when all positives reject. The frozen
token-level confidence cutoff is uncalibrated; model capability, prompt design
and decision-policy calibration are not separated by this experiment. Keep
the candidate unselected and the Lane 6 quality gate open.

An additional unshipped [exact-acronym prototype](../backend/app/ai/extractive_support.py)
requires a whole-line explicit source relation, exact expansion agreement and
independent local NLI/QA. Its six-case diagnostic accepted one positive and
no sampled wrong claims or unrelated questions; it remains unselected.
The 2026-09-26 exact canonical-page hypothesis produced no full support passes
among five bounded available spans; the sixth deterministic span was
unavailable. All tested wrong claims and unrelated questions rejected. Three
spans were not citable under current body-only chunk contracts. Neither result
justifies reindexing or a new answer policy.

Normal tests make no remote calls. The replacement guarded harness in
[`test_live_rag_evaluation.py`](../backend/tests/integration/test_live_rag_evaluation.py)
admits one authored current-question embedding only, with zero retries and
no answer/verifier request. It is a transport/selector smoke, not private
retrieval or page-open quality proof. Fresh explicit endpoint/model/price/call/
token/time/cost authorization remains required; historical answer-run approval
cannot opt it in. See [testing](TESTING.md) for its dedicated authorization.

On 2026-09-23, the operator separately authorized two bounded synthetic live
diagnostics. The first completed one embedding and one answer request but
failed the local-support gate; its provider cost is unknown. After the
definition-paraphrase fix, the final authorized sample passed in 28.05 seconds
with exactly one embedding and one answer request, no retries, and enforced
12,000 input-token, 1,024 output-token, 60-second and USD 0.04 estimated-cost
ceilings. This verifies that one synthetic question passed the current code and
configured provider. It is not a provider billing receipt or a broad quality
claim. Earlier preflight invocations were rejected before any remote call.

On 2026-09-20 the operator explicitly authorized the then-current bounded live evaluation.
The final historical-policy run passed once in 27.25 seconds (`1 passed, 10
deselected`) using the pinned native Gemini answer and embedding profiles. Two
earlier bounded diagnostic runs made no automatic retry: one exposed a
truncated 512-token answer and one exposed a 30-second timeout under the
provider-default thinking effort. That historical run used a 1,024-token answer
ceiling, a 60-second wall limit and explicit `minimal` thinking. This proves the
guarded sample at that time; it does not establish future availability, price,
provider billing completeness or quality for every production Subject. See
[AI evaluation](AI_EVALUATION.md), [testing](TESTING.md), the
[selected profile](decisions/ADR-014-native-gemini-rag-profiles.md)
and the [archived RAG plan](<archive/Cardchemy-Subject-Scoped RAG Implementation Plan.md>).
