# Project Map

## Current local Lane 6 closure — 2026-10-04

The local source-only v8/visual-v5/admission-v2 installation on head `0033`
is enabled after its measured quality, PDF/display and release gates. Fresh
installations remain default-off. See the
[closure and activation evidence](.agent/logs/2026-10-03/2026-10-03-lane6-final-closure-and-activation.md). Earlier installation
checkpoints below remain historical snapshots; the linked closure supersedes
their off/pending status, while default-off and upgrade safeguards still apply.

## Matching v8 source completion — 2026-10-03

The prospective [v5 wire](backend/app/ai/source_judgment_visual_v5.py),
[v2 admission service](backend/app/services/rag_question_context_v2.py),
[v5 source preparation](backend/app/services/source_visual_preparation_v5.py)
and [additive 0033](backend/alembic/versions/20261002_0033_visual_clarity_policy.py)
combine the conservative parser with narrow current-question clarity repairs.
The frontend fences admission/retry to v8/v5 while retaining historical sources.
[Private hybrid](backend/scripts/prepare_private_navigation_v8.py) and
[seed preparation](backend/scripts/prepare_private_navigation_seed_v8.py)
use current source/SQL guards without providers. See
[completion evidence](.agent/logs/2026-10-03/2026-10-03-v8-completion-work.md).
The [retained cutover](.agent/logs/2026-10-03/2026-10-03-v8-retained-cutover-and-release-checks.md)
is at 0033/v8/visual-v5 with healthy matching services. Ask/source judging stay
off until matching private displayed-source and release gates pass.

Prospective [visual-v4 selection](backend/app/ai/source_judgment_visual_v4.py)
and [context-v2 clarity](backend/app/ai/source_navigation_context_v2.py) repairs
are inert and retain current source-only bounds. See their
[evidence and remaining integration](.agent/logs/2026-10-02/2026-10-02-candidate-local-and-question-clarity-repair.md).

## Dormant retained v7 — 2026-10-02

[Admission context](backend/app/services/rag_question_context.py),
[v3 source preparation](backend/app/services/source_visual_preparation_v3.py),
[v3 provider](backend/app/ai/providers/source_visual_v3.py) and
[additive migration 0032](backend/alembic/versions/20261002_0032_literal_subject_context.py)
implement immutable literal-subject context in the current source-only
worker/API/disclosure. They preserve one raw-question embedding, at most one
ID/category-only judgment and no answer/verifier/retry. Source and retained
head are `0032`; matching services are healthy, with Ask and source judging
off pending quality/release gates. The effective judge deadline is 120 seconds.
See [cutover and release checks](.agent/logs/2026-10-02/2026-10-02-v7-retained-cutover-and-release-recheck.md).
The earlier dated preparation and v6 sections below are historical snapshots.

The [private trial planner](scripts/prepare_private_visual_trial_v7.py) performs
keyless signed-input/budget preflight. The separate
[dispatch guard](backend/scripts/private_visual_dispatch_guard_v7.py) rechecks
current SQL grants, revisions, exact text and authenticated PDFs in fresh
read-only transactions. Its [actual rehearsal](backend/scripts/rehearse_private_visual_dispatch_v7.py)
has no provider transport or credentials. The [prospective caller](scripts/run_private_visual_trial_v7.py)
is restricted to synthetic mocks and cannot execute a real trial. These
diagnostics do not admit persisted Ask jobs, prove browser display, or enable Ask.

## Inert follow-up context preparation — 2026-10-02

The [literal subject helper](backend/app/ai/source_navigation_context_v1.py)
preserves the raw current question and resolves only a bounded exact subject
from the most recent preceding user turn; ambiguous input requests clarification.
It performs no provider/DB work and is not wired into retained runtime. The
[independent local probe](.agent/logs/2026-10-02/2026-10-02-literal-subject-context-preparation.md)
matches both previously unresolved private follow-ups without changing the other
ten questions. Immutable admission ordering, a separately versioned wire,
private-transfer approval and actual displayed-source quality remain required.

The [pure visual-v3 wire](backend/app/ai/source_judgment_visual_v3.py) adds local
admission-snapshot validation and sends no preceding question body, assistant
text, local IDs, hashes or timestamps. It remains detached from the retained
worker; see its [offline preparation record](.agent/logs/2026-10-02/2026-10-02-visual-v3-subject-contract-preparation.md).

## Historical dormant visual Ask contract — 2026-10-01

Source and retained schema are `20261001_0031`; matching API/workers/frontend
are healthy with Ask disabled after a restore-verified forward cutover. The
prepared `related_knowledge_navigation_v6` / `hybrid_source_navigation_v9`
path authenticates the complete current PDF archive before isolated Poppler
rendering, binds exact text and up to four bounded page PNGs, and permits
at most one query embedding plus one ID/category-only source judgment.
It makes no answer/verifier call or automatic retry. The archive key is also
required by the answer worker; provider keys remain isolated to their roles.

The current dormant application contract `visual_source_id_v2` uses
Gemini 3.5 Flash-Lite, HIGH thinking, 32,768 input / 4,096 output tokens
including thinking and a 60-second provider deadline. Adaptive full-page
rendering reduces scale only after definitive PNG oversize. Complete public
calibration passed; separate heldout preparation makes no provider calls.
Historical v5/v1 snapshots remain fenced and unchanged. The user's
prospective release target is 80% displayed usefulness, at least 10/12
conclusive no-match controls and all existing hit/availability gates.
Fabricated, unauthorized, stale or wrong-page references still require zero.
Independent different-PDF and private/release gates remain open.

See the [current verification record](.agent/logs/2026-10-01/2026-10-01-visual-v6-matching-contract-and-backup.md).
Earlier v4 details below describe retained historical policies where they differ.

The current [private v7 input diagnostic](backend/scripts/prepare_private_navigation_v7.py)
and [signed-review bridge/scorer](scripts/score_private_source_display_v7.py)
retain 44 exact signed source labels and four freshly reviewed changed slots
while separately binding current v7
runtime, request and literal-question-context identities. They are provider-free;
simulated frozen-case admissions do not establish SQL enqueue ordering or release.

The [raw-query projection](scripts/navigation_raw_query_projection_v1.py)
executes only SHA-pinned pure production navigation functions for diagnostic
raw-clarity validation, without Settings/provider imports. Source IDs are bound
to reviewed local UUID/page/revision identities independently of provider aliases.
The [separate public v8 caller](scripts/run_visual_public_heldout_v8.py) and
[foreground supervisor](scripts/launch_visual_public_heldout_v8.py) implement the
exact one-use sixteen-question successor; consumed callers stay immutable.

The separate [private v6 display scorer](scripts/score_private_source_display_v6.py)
implements the accepted 80% every-card metric with complete frozen case/candidate
reviews, exact issued-source bindings, 10/12 holdout and 3/4-per-form hits,
seed/control and zero source/policy violations. It imports no provider or
settings and cannot establish real source/display evidence or enable Ask.
Historical v4 scoring rules remain unchanged.

The [private v6 question-vector preparer](scripts/prepare_private_query_vectors_v6.py)
binds twelve current questions to frozen gold/current-source bytes, prepares an
owner-private manifest without settings/keys or provider/DB calls, and keeps
execution dormant pending a separate exact envelope and resource-fenced caller.
Its [keyless contracts](backend/tests/test_private_query_vectors_v6.py) verify
the native singleton batch route and durable no-replay/checkpoint boundaries.
Its [inert outer caller](scripts/run_private_query_vectors_v6.py) supplies
separate fresh UUID/code/profile approval, role-isolated process settings,
suspended Windows resource assignment, durable safe aggregates and a hard
360-second process-tree fence; no root credential loader or default live path.

The [private hybrid-input preparer](backend/scripts/prepare_private_navigation_v6.py)
requires externally pinned current-question vectors and frozen source/gold,
then runs production hybrid retrieval and visual preparation in one read-only
authorized snapshot. Its default CLI is inert; explicit execution needs a
credential-isolated four-CPU/two-GiB container and an outer hard 300-second
process limit. It preserves all twelve cases and establishes no displayed
quality, provider permission or release pass.


The [source-usefulness contract audit](scripts/audit_source_usefulness_contract_v1.py)
prepares one approved public-only, shuffled calibration review and seals
wire-only judgments before releasing original-PDF identities to each reviewer.
It has no provider, private-data or Ask execution path. Its tri-state schema
keeps input sufficiency, page usefulness and cue navigation separate; old
pilot labels/results and heldout remain intact.
Its [sealed-review summarizer](scripts/summarize_source_usefulness_contract_v1.py)
binds both reviews, prepares a vote-free disagreement packet, preserves
unresolved cases and reports complete old/new label mappings without reading
historical model responses or producing a release pass.

The [public visual-page preparer](scripts/prepare_visual_page_source_input_v1.py)
binds faithful bounded PNGs to the same four approved public PDFs, physical
pages and exact text/cues inside an isolated Windows process tree. The inert
[visual source-ID wire/parser](scripts/prototype_visual_page_source_judge_v1.py)
accepts only issued IDs and closed page/status judgments; it separates
clarification from conclusive no-match. Neither helper calls a provider or
changes the application policy. See the
[approved offline scope](.agent/logs/2026-10-01/2026-10-01-visual-page-source-input-approved.md).
Its [blind feasibility projection](scripts/prepare_visual_source_feasibility_review_v1.py)
keeps gap/weak roles and old labels out of fresh reviewer inputs, retaining
uncertainty and a separate prospective no-match control. A bounded
[image access helper](scripts/prepare_visual_review_access_v1.py) creates
byte-identical owned scratch copies when the read-only image tool cannot
open Windows Temp; original inputs and raster hashes remain unchanged.
The [complete review summarizer](scripts/summarize_visual_source_feasibility_v1.py)
keeps both sealed judgments and uncertainty, reporting a development input
stop independently of any model or release score.
The separately approved [semantic/control projection](scripts/prepare_visual_semantic_control_v2.py)
uses opaque IDs and byte-identical images for three semantic pairs and one
four-page source group. Its [clarity-aligned wire](scripts/prototype_visual_page_source_judge_v2.py)
distinguishes discovery questions from dangling referents without changing
the completed v1 freeze. The [conservative bound summarizer](scripts/summarize_visual_semantic_control_v2.py)
preserves historical positive obligations, withholds credit from conflicting
or unknown labels, and assembles inert current-question inputs without a
provider request or model-quality claim.

The separately approved [public visual calibration caller](scripts/run_visual_public_calibration_v2.py)
revalidates frozen public requests and shuffled review bindings before a
SHA-bound one-use provider trial. Its [pure scorer](scripts/score_visual_public_calibration_v2.py)
keeps historical obligations, unknown/display/error denominators and separate
clarification/no-match states. The [hidden resource supervisor](scripts/launch_visual_public_calibration_v2.py)
starts the worker suspended inside a four-CPU/two-GiB process tree; it reads
no credential. These helpers cannot open heldout or activate application Ask.

The successor [checkpoint caller](scripts/run_visual_public_calibration_v3.py),
[80% complete-denominator scorer](scripts/score_visual_public_calibration_v3.py)
and [resource supervisor](scripts/launch_visual_public_calibration_v3.py)
retain the frozen v2 trial and admit only its four SHA-bound valid receipts.
They never resend those groups; the remaining 63 requests need a fresh
precise provider authorization. Completeness is diagnostic while hit,
availability and clear empty no-match remain gates. The helpers cannot
open heldout, transfer private Knowledge or enable Ask.

Current navigation, updated 2026-09-25. Begin with
[orientation](docs/00-START-HERE.md); use this map to find the smallest relevant
source area. [Backend MOC](backend/MOC.md) and [frontend MOC](frontend/MOC.md)
give the next level of detail.

The separately approved, offline [source-ranker audit](scripts/audit_source_ranker.py)
and [bounded public bundle downloader](scripts/download_source_ranker_bundle.py)
are experiment tools only; they do not select or activate an Ask runtime policy.
See the [audit evidence](.agent/logs/2026-09-27/2026-09-27-learned-source-ranking-audit.md).
The separate [Mixedbread bundle downloader](scripts/download_reading_usefulness_bundle.py)
and [load-only preflight](scripts/preflight_reading_usefulness_bundle.py) are
public-artifact experiment tools; they do not score private Knowledge or change
the Ask policy. The public PDF corpus acquisition and quality gate are tracked
in the [Lane 6 evidence](.agent/logs/2026-09-28/2026-09-28-reading-usefulness-load-preflight.md).
The [v4 local corpus derivation](scripts/derive_reading_usefulness_corpus_v4.py),
[blind review projection](scripts/build_reading_usefulness_blind_review.py),
[fixture admission](scripts/validate_reading_usefulness_fixture.py), and
[one-shot offline scorer](scripts/audit_reading_usefulness.py) are separate
public-only audit tools. They do not activate Ask or use private Knowledge.
The later [selective one-shot scorer](scripts/audit_reading_usefulness_selective.py)
tested separate no-match and per-card decisions on the same reviewed public
corpus; it also stopped at calibration, with its heldout unscored and Ask off.
The subsequent [groupwise one-shot scorer](scripts/audit_reading_usefulness_groupwise.py)
tested a 0–3 count cap plus individual card utility on that public corpus.
It too stopped at calibration after 20 local calls. These three scorers are
offline research tools with consumed ledgers, not Ask runtime selectors.
The [v4 original-PDF display scorer](scripts/score_source_judgment_display_v4.py)
is a separate, default-preflight-only release measurement contract. It binds
independently signed Temp-only exposed and fresh-holdout page/cue reviews to
actual displayed IDs, requires gold-to-slate bridge admission, rejects
duplicate frozen JSON keys and counts every shown card plus top-one utility;
it has no real holdout score and does not enable Ask.
The [private gold-to-slate bridge](scripts/bridge_private_source_gold_v4.py)
checks a caller-supplied current-source snapshot against the stage-1 gold,
candidate roster and exact-cue review bytes. Its synthetic contract does not
collect the authorized snapshot or score the real private holdout.
The [exhaustive public source-ID prototype](scripts/prototype_exhaustive_source_id_v2.py)
builds an inert, four-candidate, ID-only request for a future independent
public quality audit. It has no provider client and does not change the
dormant Ask runtime, model or current source-ID policy.
The [fresh public PDF acquirer](scripts/acquire_fresh_public_source_id_corpus_v2.py),
[overlap and packet freezer](scripts/prepare_fresh_public_source_id_v2.py), and
[offline scorer](scripts/score_fresh_public_source_id_v2.py) are separate
public-only experiment tools. The source corpus has been acquired, but its
original 48+48 page-and-cue cases were reviewed and retained. The
[blind reserve reviewer bridge](scripts/review_fresh_public_source_id_v2.py),
[augmented freezer](scripts/prepare_fresh_public_source_id_v2_augmented.py),
[augmented scorer](scripts/score_fresh_public_source_id_v2_augmented.py), and
[approval-fenced caller](scripts/run_fresh_public_source_id_v2_augmented.py), and
[single-credential launcher](scripts/launch_fresh_public_source_id_v2_augmented.py)
bind those cases to 30 separately reviewed public cases. The 126-case
packet passed keyless freeze and caller preflight; its live model score
failed calibration: 66/66 valid responses, but one false display on a
no-match question and insufficient multi-page selection. Its 60-case heldout
stayed sealed. The
[per-page verdict prototype](scripts/prototype_per_page_source_verdict_v3.py)
is a separately approved keyless candidate that asks for two boolean judgments
per issued page and derives at most three IDs locally; it has no provider or
Ask runtime path. None of these tools enables Ask.

The approved [full-cue high-thinking prototype](scripts/prototype_full_cue_high_thinking_v1.py),
[runner](scripts/run_fresh_public_full_cue_high_thinking_v1.py),
[scorer](scripts/score_fresh_public_full_cue_high_thinking_v1.py),
[receipt preparer](scripts/prepare_fresh_public_full_cue_high_thinking_v1_approval.py)
and [launcher](scripts/launch_fresh_public_full_cue_high_thinking_v1.py)
provide a distinct public-only experiment candidate. They retain the frozen public gates,
paired selected-ID/usage/latency receipts and one-use claims; live execution
was separately approved once and has stopped after three physical calibration
claims: two valid journals and one HTTP response over the 8 KiB body cap.
The one-use ledger is consumed, with no full calibration or heldout score;
the [terminal evidence](.agent/logs/2026-09-30/2026-09-30-full-cue-high-thinking-public-stop.md)
does not select a runtime policy or enable Ask.

The [v2 transport runner](scripts/run_fresh_public_full_cue_high_thinking_v2.py),
[launcher](scripts/launch_fresh_public_full_cue_high_thinking_v2.py) and
[receipt preparer](scripts/prepare_fresh_public_full_cue_high_thinking_v2_approval.py)
began as an offline repair prototype: a 64 KiB whole-HTTP-body bound, the
same v1 wire/parser/scorer, and separate execution identities. The
[proposal and mock evidence](.agent/logs/2026-10-01/2026-10-01-high-thinking-transport-repair-proposal.md)
now have [one exact new public-only pilot approval](.agent/logs/2026-10-01/2026-10-01-high-thinking-transport-pilot-approved-scope.md).
The consumed v1 ledger stays untouched. Approval is not a quality result,
private-transfer permission or runtime change; Ask remains disabled.
The v2 pilot subsequently [stopped on its quality gate](.agent/logs/2026-10-01/2026-10-01-high-thinking-transport-v2-quality-stop.md)
after 12 physical attempts; its approval is consumed and no heldout opened.

## Backend

Prepared visual source judging lives in [source_judgment_visual.py](backend/app/ai/source_judgment_visual.py)
and the complete authenticated [PDF archive reader](backend/app/services/knowledge_pdf.py).
They are not active worker policy or quality evidence; see the
[current deadline preparation](.agent/logs/2026-10-01/2026-10-01-visual-calibration-deadline-repair-preparation.md).

| Area | Path | Responsibility |
| --- | --- | --- |
| API startup | [main.py](backend/app/main.py) | Router order, lifespan/migration verification, CORS and health |
| Configuration/database | [config.py](backend/app/config.py), [database.py](backend/app/database.py) | Root settings, validated boundaries, async sessions and heads/readiness |
| Authentication | [auth router](backend/app/routers/auth.py), [auth service](backend/app/services/auth.py), [password records](backend/app/services/passwords.py), [user model](backend/app/models/user.py) | Purpose-scoped tokens, compatible password hashes, sessions, invitations, registration and reset |
| Subjects/enrollment | [subjects router](backend/app/routers/subjects.py), [subject service](backend/app/services/subject.py), [subject model](backend/app/models/subject.py) | Subject ownership/deletion, invites/enrollment and set publication |
| Sets/cards | [flashcards router](backend/app/routers/flashcards.py), [flashcard service](backend/app/services/flashcard.py), [schemas](backend/app/schemas/flashcard.py) | CRUD, strict four-option validation, approval/publication |
| Generation admission | [generation router](backend/app/routers/generation.py), [generation service](backend/app/services/generation.py), [candidate storage](backend/app/services/candidate_storage.py) | Job reservation, raw-PDF upload, authorized duplicate and validated-card choices, encrypted staged candidates, quotas, polling/cancel/manual retry |
| Generation execution | [worker entry](backend/app/worker.py), [generation worker](backend/app/workers/generation.py), [compatibility facade](backend/app/agents/graph.py) | Lease claims, extraction, adaptive evidence allocation, per-attempt validation diagnostics, fencing and atomic exact-count result or encrypted smaller-target choice |
| Knowledge capture/indexing | [capture service](backend/app/services/knowledge_capture.py), [index operations](backend/app/services/knowledge_indexing.py), [index entry](backend/app/index_worker.py), [index worker](backend/app/workers/knowledge_index.py) | One-pass private capture, durable embedding claims, fenced batches, reindex staging and atomic space cutover |
| Knowledge retrieval | [retriever](backend/app/services/knowledge_retrieval.py), [embedding adapter](backend/app/ai/embeddings.py) | Worker-owned query embeddings and authorized exact cosine plus PostgreSQL FTS retrieval with bounded deterministic fusion |
| Subject Ask AI | [router](backend/app/routers/rag.py), [service](backend/app/services/rag_answers.py), [navigation selector](backend/app/ai/source_navigation.py), [visual v3 contract](backend/app/ai/source_judgment_visual_v3.py), [admission context](backend/app/services/rag_question_context.py), [historical sufficiency selector](backend/app/ai/source_sufficiency.py), [historical excerpt selector](backend/app/ai/related_evidence.py), [worker entry](backend/app/answer_worker.py), [worker](backend/app/workers/rag_answer.py), [models](backend/app/models/rag.py) | Private threads, dormant v7 visual jobs with immutable current/preceding-user context, at most one raw-current-question embedding and one source-ID judgment, bounded hybrid/lexical navigation and eligible neighbor search, unverified exact cues and original-PDF page reads; release fence remains closed. Historical answer contracts are retained only for old data. |
| Student published lectures | [browse router](backend/app/routers/published_knowledge.py), [schemas](backend/app/schemas/published_knowledge.py), [browser](frontend/src/components/knowledge/PublishedKnowledgeBrowser.tsx), [typed API](frontend/src/services/publishedKnowledge.ts) | Enrollment-scoped current published lecture catalog, local page search, extracted page text and authenticated original-PDF ranges, available independently of Ask admission. |
| Knowledge management | [router](backend/app/routers/knowledge.py), [service](backend/app/services/knowledge_management.py), [schemas](backend/app/schemas/knowledge.py) | Owner-only document state, explicit review/publication, persisted-page index retry, unpublish and card-preserving deletion |
| RAG evaluation | [v2 corpus](backend/tests/fixtures/rag_eval/subject_knowledge_v2.json), [local support corpus](backend/tests/fixtures/rag_eval/product_quality_lane5_local_support_v1.json), [metric support](backend/tests/support/rag_evaluation.py), [PostgreSQL evaluation](backend/tests/postgres/test_postgres_rag_pipeline.py), [local evaluator](scripts/evaluate_local_support.py) | Reviewed retrieval/security gates, two-request cap, local semantic/resource quality and exact-search/ANN/reranker decisions |
| Isolated local support experiments | [larger NLI/QA evaluator](scripts/evaluate_larger_local_support.py), [relation classifier](scripts/local_relation_candidate.py), [relation evaluator](scripts/evaluate_local_relation.py), [public calibration audit](scripts/calibrate_local_relation.py), [4B candidate](scripts/local_relation_4b_candidate.py), [supervised 4B audit](scripts/calibrate_local_relation_4b.py), [public artifact downloader](scripts/download_local_relation_4b.py), [reviewed public calibration/heldout](backend/tests/fixtures/rag_eval/local_relation_calibration_v1.json), [public relation controls](backend/tests/fixtures/rag_eval/local_relation_adversarial_v1.json) | Provider-free, version/digest-bound research under owner-approved resource budgets; no runtime selection or release claims |
| Private quality probes | [Ask page discovery](scripts/discover_private_rag_evidence.py), [Ask corpus proxy](scripts/evaluate_private_rag_corpus.py), [real-query retrieval](scripts/evaluate_private_query_retrieval.py), [source-navigation diagnostic](backend/scripts/diagnose_source_navigation.py), [one-shot query-vector packet builder](backend/scripts/build_private_query_vectors.py), [public Knowledge holdout preflight](backend/scripts/preflight_public_knowledge_holdout.py), [local Ask support comparison](scripts/evaluate_private_ask_support_v2.py), [bounded Ask comparison](scripts/compare_private_ask_once.py), [source-positive review packet](scripts/build_private_lane6_review_packet.py), [negative review packet](scripts/build_private_lane6_negative_packet.py), [generation no-provider preflight](scripts/preflight_private_generation_source.py), [bounded generation evaluation](backend/scripts/evaluate_private_generation.py) | Owner-authorized published-source discovery and aggregate-only diagnostics; a frozen eleven-case vector packet needs a separate explicit provider envelope and private output; attributed public holdout preflight checks OS-Temp PDFs without provider or DB access; other private review packets write exact excerpts only to guarded OS Temp HTML |
| AI quality/providers | [pipeline](backend/app/ai/pipeline.py), [prompts](backend/app/ai/prompts.py), [grounding](backend/app/ai/grounding.py), [Gemini catalog](backend/app/ai/gemini_catalog.py), [providers](backend/app/ai/providers/__init__.py), [rate governor](backend/app/ai/rate_limit.py) | Closed role/model preflight and policy snapshots, evidence packing, typed output, quality/duplicate rejection, one retry owner and request budgets |
| PDF/source protection | [PDF processor](backend/app/services/pdf_processor.py), [source storage](backend/app/services/source_storage.py) | Subprocess bounds, optional OCR, encrypted temporary sources and [revision-bound original-PDF archives](backend/app/services/knowledge_pdf.py) |
| Study/progress | [study router](backend/app/routers/study.py), [flashcard service](backend/app/services/flashcard.py), [models](backend/app/models/flashcard.py) | Eligibility, due/review-all queries, server grading/scheduling, receipts and distinct Progress/Attempted/Accuracy/Mastery metrics |
| Transactional email | [email service](backend/app/services/email.py), [worker entry](backend/app/email_worker.py), [email worker](backend/app/workers/email.py), [outbox model](backend/app/models/email.py) | Atomic enqueue, safe templates, SMTP delivery and ambiguity recovery |
| Operators | [CLI](backend/app/cli.py), [health probe](backend/app/healthcheck.py), [shutdown](backend/app/workers/shutdown.py) | Instructor bootstrap, queue status/retry and process health/drain |
| Diagnostics/privacy/audit | [safe diagnostics](backend/app/observability.py), [operations](backend/app/services/operations.py), [privacy](backend/app/services/privacy.py), [audit](backend/app/services/audit.py) | Correlation/errors, retained aggregate metrics, worker-loop health, operator lifecycle and transactional privileged history |
| Schema evolution | [Alembic versions](backend/alembic/versions), [env](backend/alembic/env.py) | Baseline to source and retained head `20261002_0032`; Lane 6 adds source-only results, at most three bounded references, parent-stage policy enforcement, exact canonical-page offsets, immutable historical navigation policies, encrypted original-PDF archives and immutable literal-subject admission metadata. Retained head/drift and matching services passed with Ask disabled; see [current state](docs/development/CURRENT-STATE.md). |
| Subject Knowledge foundation | [Knowledge models](backend/app/models/knowledge.py), [Knowledge lock](backend/app/services/knowledge_lock.py) | Private document/content/index revisions, reserved capacity, eligible-record predicate, durable index queue and ordered writer/deletion locking |

## Frontend

| Area | Path | Responsibility |
| --- | --- | --- |
| Bootstrap/routes | [main.tsx](frontend/src/main.tsx), [App.tsx](frontend/src/App.tsx), [guards](frontend/src/components/auth/RouteGuards.tsx) | Providers, lazy pages and role-protected routes |
| Auth/API | [AuthContext](frontend/src/context/AuthContext.tsx), [api.ts](frontend/src/services/api.ts), [types](frontend/src/services/types.ts), [errors](frontend/src/services/errors.ts) | Memory tokens, single-flight refresh, typed HTTP/errors |
| Instructor workflow | [instructor pages](frontend/src/pages/instructor), [subject dialogs](frontend/src/components/subjects), [set dialogs](frontend/src/components/sets) | Subjects, generation, review/edit/approval/publication, invitation |
| Generation UI | [job hook](frontend/src/hooks/useGenerationJobs.ts), [job card](frontend/src/components/generation/GenerationJobCard.tsx), [flashcards API](frontend/src/services/flashcards.ts) | Reservation/upload, duplicate and smaller-target choice recovery, polling, cost-aware retry and bounded per-attempt/cumulative telemetry |
| Student workflow | [student pages](frontend/src/pages/student), [study slice](frontend/src/store/slices/studySlice.ts), [study API](frontend/src/services/study.ts) | Enrollment views, due/review-all sessions, durable save/retry/progress |
| Subject Knowledge/Ask AI UI | [KnowledgeArea](frontend/src/components/knowledge/KnowledgeArea.tsx), [AskAiPanel](frontend/src/components/rag/AskAiPanel.tsx), [Knowledge API](frontend/src/services/knowledge.ts), [RAG API](frontend/src/services/rag.ts) | Independent instructor Knowledge lifecycle plus principal-private conversations, source-only result states, unverified exact cues, original-PDF viewer and accessible recovery |
| Join/recovery | [JoinCourse](frontend/src/pages/JoinCourse.tsx), [ForgotPassword](frontend/src/pages/ForgotPassword.tsx), [ResetPassword](frontend/src/pages/ResetPassword.tsx) | Invite validation/join and account recovery |
| Shared experience | [UI controls](frontend/src/components/ui), [feedback](frontend/src/components/feedback), [English catalog](frontend/src/i18n/en.ts), [styles](frontend/src/index.css) | Accessible controls, errors, copy, responsive layout |

## Cross-cutting change paths

| Change | Trace and contract to read |
| --- | --- |
| Generation behavior | Instructor `SubjectDetails` → `useGenerationJobs`/flashcards API → generation router/service → generation worker → graph facade → pipeline/provider → models; [generation flow](docs/architecture/AI-GENERATION-FLOW.md) |
| Subject Knowledge/Ask AI | Generation/Knowledge reservation and upload → same-Subject duplicate decision or unchanged-revision no-op → shared bounded preparation → atomic capture/index enqueue → index worker → explicit publication/space cutover → one raw-current-question embedding → authorized retriever → prospective one bounded source-ID judgment over authorized published page cues/PNGs and an admitted literal subject only when needed → locally derived unverified references and original-PDF read; v7 remains dormant behind the Ask release fence. [Knowledge flow](docs/architecture/SUBJECT-KNOWLEDGE-FLOW.md) |
| Card review/publication | `SetView`/dialogs → flashcards/subjects APIs → routers/services → card/set/subject constraints and migration trigger; [data model](docs/architecture/DATA-MODEL.md) |
| Auth/invitation/reset | Auth/join pages and context → auth/subjects APIs → auth/subject services → user/session/invitation + outbox → email worker; [auth flow](docs/architecture/AUTH-FLOW.md) |
| Answer/progress | `StudyMode`/study slice → study API with receipt key → study router → flashcard service → progress/receipt/enrollment rows; [study flow](docs/architecture/STUDY-PROGRESS-FLOW.md) |
| Runtime/configuration | Root `.env.example` → settings/public loader/Compose → workers/API/Vite build; [configuration](docs/CONFIGURATION.md) and [system overview](docs/architecture/SYSTEM-OVERVIEW.md) |

## Configuration, infrastructure and verification

- [Root template](.env.example) is the only configuration template; real `.env`
  is private. [Bootstrap](scripts/bootstrap_env.py) never overwrites it.
- [Base Compose](docker-compose.yml), [development override](docker-compose.dev.yml),
  [production override](docker-compose.prod.yml), [backend Dockerfile](backend/Dockerfile),
  [frontend Dockerfile](frontend/Dockerfile) and [Nginx](frontend/nginx.conf)
  define the runtime. [Vite](frontend/vite.config.ts) and the
  [public loader](frontend/config/environment.mjs) define browser configuration.
- [Database inventory](runtime-artifacts.json), the
  [reviewed database recipe](docker/database/Dockerfile), and the
  [database image helper](scripts/runtime_database.py) own the pinned
  PostgreSQL 16/pgvector build and verified immutable consumer identity.
  [Artifact scanning](scripts/test_database_artifact.py),
  [vector recovery](scripts/test_pgvector_restore.py), and
  [prior-installation recovery](scripts/test_database_volume_upgrade.py)
  verify security and disposable restore contracts; see
  [database operations](docs/DATABASE_OPERATIONS.md).
- Backend [tests](backend/tests) separate offline, `postgres/`, and opt-in
  `integration/`; frontend [Node units](frontend/tests), [component tests](frontend/tests/components)
  and [E2E](frontend/e2e) cover client contracts.
- [Service harness](scripts/test_services.py), [real journey](scripts/test_journey.py),
  [CI validator](scripts/check_ci.py), [context validator](scripts/check_context.py),
  [coverage](scripts/check_coverage.py), [bundle](scripts/check_bundle.mjs),
  [security](scripts/test_security.py) and [images](scripts/check_images.py)
  validate distinct gates. See [testing](docs/TESTING.md).
- [TLS SMTP verifier](scripts/test_smtp_tls.py) and
  [production recovery rehearsal](scripts/test_production_rehearsal.py) verify
  local encrypted email and fresh production-profile backup/restore respectively.
  Their guides are [SMTP verification](docs/SMTP-VERIFICATION.md) and
  [production rehearsal](docs/PRODUCTION_REHEARSAL.md).
- [Release validator](scripts/check_release.py), [notice synchronization](scripts/prepare_release_notices.py)
  and [brand preparation](scripts/prepare_brand_assets.py) own exact release
  provenance and distribution notices/exports. See [releasing](docs/RELEASING.md)
  and the disposable [demo](docs/DEMO.md).
- [Workflows](.github/workflows), [coverage budget](.github/coverage-budget.json),
  [bundle budget](.github/bundle-budget.json) and [protection definition](.github/branch-protection.json)
  are explained in [CI](docs/CI.md). A local definition is not a fresh remote-status check.

## Documentation

[Guide index](docs/README.md) → [architecture](docs/architecture/SYSTEM-OVERVIEW.md)
and [decision index](docs/decisions/ADR-000-INDEX.md). [Local setup](docs/development/LOCAL-SETUP.md)
owns onboarding; [current state](docs/development/CURRENT-STATE.md) summarizes
completed phases; the [public roadmap](ROADMAP.md) owns current proposals.
[Dated logs](.agent/logs/README.md) and the [archive](docs/archive/README.md)
retain completed phase checklists and historical evidence. [Agent rules](AGENTS.md)
define context maintenance.
