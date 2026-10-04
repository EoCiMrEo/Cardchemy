# Literal-context ORM parity and actual SQL binding contracts

## Scope and preservation

Continued the bounded v7 preparation after the parent assigned ORM integration.
Updated only [RAG models](../../../backend/app/models/rag.py), their
[exports](../../../backend/app/models/__init__.py), the new
[model contracts](../../../backend/tests/test_literal_subject_context_models.py)
and this record. Preserved pre-existing model changes, historical policies and
used migrations. The parent separately owns safe-error-pair integration,
enqueue/worker/configuration/frontend wiring and operational gates.

The additive `20261002_0032` migration is owned by the migration agent. Its
model-facing context/policy constants were coordinated before editing. This
task did not execute a migration, access retained data or environment settings,
read credentials, call a provider, change volumes or enable Ask.

## Model implementation

Added the two nullable job admission snapshots and the metadata-only
`RagAnswerQuestionContext` model with the exact 21 migration columns, named
primary key, three scoped cascade foreign keys and predecessor index. A prior
message's retention deletion removes its context binding while preserving the
newer Ask job. No message or literal subject body is copied into the binding.

The current model's identity, result, source-judge contract/retrieval pairing,
source-stage policy/cap and physical-attempt unique-index predicate now add v7
without reinterpreting v5/v6 snapshots. Old deadlines/contracts remain paired
to their existing versions. V7 is separately paired to visual-v3 and its finite
120-second ceiling.

PostgreSQL context checks match the migration strings exactly. Their regex
syntax is emitted only for PostgreSQL. Separately named SQLite-only equivalents
enforce the same 64 lowercase hexadecimal hashes using bounded nested replace
expressions, retaining complete-null-or-complete-present and span/lifetime
conditions. They permit the actual ORM-backed offline contracts without
weakening the deployed PostgreSQL checks or adding SQLite syntax to its DDL.

## Checks and evidence

- `venv/Scripts/python.exe -m pytest tests/test_literal_subject_context_models.py
  tests/test_rag_question_context.py tests/test_source_judgment_visual_v3.py
  tests/test_source_navigation_context_v1.py -q` from `backend`:
  **267 passed**; **28 new actual-model contracts** plus the prior 56 service
  contracts and pure context/visual contracts.
- Actual-model tests use isolated SQLite with foreign keys enabled and the
  production default helper/model. They commit and reload anchored, clear,
  expired-prior and ambiguous-prior admissions; verify predecessor deletion
  removes only the binding; and reject cross-Subject FK, bad hashes, partial
  context shape, changed policy/contract and exceeded v7 budgets.
- Metadata checks prove exact migration column/nullability/FK/index/check
  parity and PostgreSQL-versus-SQLite DDL separation.
- Initial four round-trip fixture failures came from reading expired ORM
  object attributes after deliberate `expire_all()`. Tests now retain IDs and
  expected invented text before expiry and explicitly reload with async SQL;
  no production behavior changed to make these fixtures pass.
- Persistence does not flush implicitly. The tested FK-safe caller order is:
  capture before current insertion; insert/flush current; assign job UUID;
  add job and prepare binding/snapshot fields; explicitly flush the job, then
  flush its binding in the same transaction. The parent must preserve this
  ordering when integrating enqueue.

These tests do not execute PostgreSQL triggers, prove source selection,
authorize private transfer or establish release readiness. The parent still
must run disposable PostgreSQL migration/drift/trigger/race checks and matching
worker/frontend/journey/release validation before any enablement.
