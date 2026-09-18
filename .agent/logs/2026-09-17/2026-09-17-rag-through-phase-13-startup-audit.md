# Subject-scoped RAG through Phase 13: startup audit and decision dependencies

Date: 2026-09-17 (operator timezone).

## Scope and starting context

The operator requested implementing the beginning of
[the Subject-scoped RAG plan](<../../../Cardchemy-Subject-Scoped RAG Implementation Plan.md>)
through Phase 13, completing its tasks and marking verified checkboxes. This
includes Preparation A, Preparation B, Phase 12 and Phase 13. Phases 14-21
remain outside this implementation request. The full plan was read to understand
downstream contracts; those phases are not implemented by this audit.

Starting branch: `main`; HEAD: `e10f5839735379e4277d35600067835f53272a89`.
The existing tracked change was `.agent/logs/README.md`, with two prior RAG
entries. Existing untracked files were the plan and its review/update logs.
These are operator-owned work and were preserved. Root guidance is the only
repository `AGENTS.md` found.

Followed root guidance, Start Here/project map, architecture/ADR index and
affected accepted decisions, backend/frontend maps, current state/remediation
roadmap, agent governance/log index, the prior RAG review/update and relevant
PDF/generation/request-efficiency/privacy logs. Read affected settings,
authorization, pipeline/grounding, workers, models, privacy and frontend
configuration/workflow boundaries, plus test/runtime/dependency/DB guides.
Three explicitly requested read-only subagents audited quality, configuration,
and Knowledge schema/runtime. This is an audit of the affected contracts,
not a claim that every unrelated source or test body was read.

The plan has 859 lines and 208 unchecked checklist items. Its beginning through
Phase 13 contains 77 unchecked items and zero checked items. This audit changes
no implementation checkbox or plan body.

## Explicit dependencies requiring operator answers

The plan's execution-gate section says: "Do not choose silent defaults or mark
a gate satisfied merely because it appears in this plan." The
[approved update log](2026-09-17-rag-implementation-plan-update.md) explicitly
records that approving recommendations left six choices unresolved.
Implementation authorization does not establish an undocumented outcome.

Questions were presented for the five gates needed by the requested scope:

| Gate | Question/proposal awaiting the operator | Dependent work |
| --- | --- | --- |
| G1 | Mandatory PostgreSQL 16 + pgvector for all installs, or supported non-vector installs? Proposed mandatory support retains one unconditional migration chain. | Phase 12 runtime/schema |
| G2 | Proposed 90-day private own-chat retention, published-ready Knowledge for Ask AI including instructors, and hiding derived answers/citations when supporting content becomes unavailable/replaced. Different retention/history policy remains possible. | Privacy design before Phase 13 writes |
| G4 | Proposed Knowledge-only upload, same-Subject identical-upload replay, fresh review for changed content, and document deletion preserving linked cards. Regeneration-required upload remains possible. | Phase 13 associations/versioning |
| G5 | Exact embedding provider/model/dimensions and intended answer provider/model, without credentials. Supported dimensions/task modes/representation will be verified after selection. | Phase 13 vector schema |
| G6 | Proposed separate flashcard/index/answer processes, role-specific credentials/reserved capacity, and explicit operator division of shared account/project quotas across profiles/replicas. | Preparation B wiring and Phase 12 ADR |

The initial questions are recorded above as presented. Operator replies received
during this audit approve G1: mandatory PostgreSQL 16 + pgvector for every install,
including RAG-disabled installations; and G2: the proposed 90-day private own-chat
policy, ready/published Knowledge for all Ask AI, and hidden stored answers/
citations when supporting content is unpublished, deleted or replaced.
No exact image/package support claim follows before artifact/runtime validation.
The operator also approved G4: Knowledge-only uploads, replay of identical uploads
only within the same Subject, fresh review/publication for changed content, and
document deletion preserving linked flashcards.
G5/G6 still await answers. No dependent source/config/schema implementation
began. G3 post-capture cancellation is needed before Phase 14,
beyond the requested endpoint; it was not made a prerequisite for this scope.

## Source-grounded audit findings

Preparation A remains unimplemented. The
[pipeline](../../../backend/app/ai/pipeline.py) asks for up to the target, lacks
versioned generation/map/reduce prompts and accepted-card refill exclusions,
and concurrently produces same-source split requests. Ten requested cards have
a 5,376-token output cap under the current formula. Added instructions and
exclusions must enter rendered packing and conservative preflight. Existing
orchestration fixtures add artificial uniqueness markers; they do not establish
realistic yield or instructor teaching-quality judgment. Preserve strict
batch/grounding validation, exact complete results, atomic persistence and
legitimate insufficient-source failure. Human quality review and any remote
A/B evidence must be reported separately from deterministic fixtures.

Preparation B remains unimplemented. All 29 template `AI_*` settings and the
legacy Gemini fallback are active in
[Settings](../../../backend/app/config.py). Rename active settings consumers,
fixtures/harnesses/Compose/docs together, while retaining persisted/API
`ai_provider`/`ai_model` contracts and used migrations. A container-only detector
cannot see old host root keys after Compose stops forwarding them; the launch
contract needs safe host detection or nonsecret presence metadata. Never forward
old credential values to other containers just to detect removed names.
Generation disablement currently puts its worker into heartbeat-only mode, so
RAG cannot be appended to that loop without independent role enablement.

No Knowledge models, pgvector dependency/extension migration, retrieval or chat
implementation exists. The migration chain ends at `20260917_0008`.
[Subject access](../../../backend/app/services/subject.py) enforces ownership
or enrollment, without Knowledge visibility/revision checks. Ready/private
Knowledge needs additional eligibility checks; set publication is independent.
[Privacy export/deletion](../../../backend/app/services/privacy.py) currently
handles existing records/workers, not Knowledge/indexing/chat contracts.

Five direct PostgreSQL image consumers require coordinated Phase 12 updates:
base Compose, `scripts/test_services.py`, `scripts/test_journey.py`,
`scripts/test_smtp_tls.py`, and the PostgreSQL startup-probe test. Recovery/demo
and hosted CI inherit those consumers. Current application image scanning/SBOM
lists omit the DB image; its artifact coverage needs an explicit contract.

Phase 13 needs private publication tied to reviewed content identity, canonical
page numbering, revision-aware chunks/embedding space, complete durable indexing
claim schema, permanent capacity bounds and subject-consistent FKs. Nullable
document links must preserve surviving cards and Knowledge after job-history
expiry. Composite FK deletion must clear only the document link, preserving
required Subject identity; SQLite portability requires deliberate handling and
does not prove deployed constraints.

Primary documentation was refreshed: [pgvector](https://github.com/pgvector/pgvector)
supports exact/approximate retrieval with representation-specific index limits
and filtered-recall considerations; [Python integration](https://github.com/pgvector/pgvector-python)
documents SQLAlchemy/asyncpg integration. PostgreSQL 16 documents
[extension installation privileges](https://www.postgresql.org/docs/16/sql-createextension.html)
and [selected-column SET NULL](https://www.postgresql.org/docs/16/ddl-constraints.html).
No model, dimension, image digest or package pin was guessed or declared supported.

## Verification actually executed

| Check | Fresh result |
| --- | --- |
| Backend offline, root: `venv/Scripts/python.exe -m pytest -q` from backend | 376 passed, 50 skipped, 1 deselected in 64.28 seconds. Skips are service gates; live AI is deselected. |
| Focused quality/provider/governor, quality subagent | 42 passed in 5.64 seconds. |
| Config/harness safety/providers, configuration subagent | 29 passed in 2.44 seconds. |
| Initial context validation | 37 required files, 61 active guides, 789 local links passed. Navigation evidence only. |
| Initial tracked whitespace check | `git diff --check` passed; normal Windows newline advisory. |
| Plan statistics and image/migration inventory | Counts above verified from current text; five direct image consumers/current migration chain confirmed. |

An initial `rg` inventory used wildcard path arguments that PowerShell did not
expand. It returned a filename-syntax error. Repeated with explicit Compose
paths and directory searches using `-g`; the corrected inventory passed.

No frontend/service/vector/image/security/SBOM/journey/recovery/hosted CI or
human accessibility gate was run. No paid/live model request was made. Existing
backend passes are baseline evidence, not validation of unimplemented RAG.
New code will require its full scope checks before checkbox completion.

## Preservation, cleanup and status

No real root `.env` was read, edited or regenerated. No secrets/private data,
operator DB or populated volume was used. No services were started; no branch,
commit/push/merge/deployment, migration or destructive cleanup occurred.
All three audit agents completed read-only tasks. No temporary resources need
cleanup. Only this new evidence log and its nearest index are changed by this
audit. The prior plan/log bodies remain intact.

Work is paused for the remaining G5/G6 answers requested by the plan and the
operator's instruction to stop for required information. No preparation or
phase is claimed complete. Resume Preparation A, then B, then Phases 12 and 13
after recording applicable choices; mark only implementation with actual
passing acceptance evidence.

Final context validation passed: 37 required files, 61 active guides and 790
local links. The new audit body's local links also passed direct validation
using the context checker's parser; historical log bodies are excluded from
its normal active-guide scan. `git diff --check` and direct new-file
whitespace/newline validation passed. SHA256 comparisons confirmed the plan
and both pre-existing RAG log bodies remained identical to startup; the index
retains both pre-existing entries and adds this audit entry only. HEAD remains
unchanged. No implementation file changed.
