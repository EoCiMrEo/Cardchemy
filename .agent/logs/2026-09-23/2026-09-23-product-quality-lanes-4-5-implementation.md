# Product quality Lanes 4 and 5 implementation and local release evidence

Date: 2026-09-23. Starting branch: `main`, HEAD `6c02d6c`. Scope: Lane 4
optional Gemini Embedding 2 preparation and Lane 5 two-request Ask with
independent local support. The pre-existing Lane 0–3 working tree was retained.
Read the root and applicable repository guidance, Start Here, project and
module maps, architecture/ADR index, current state, roadmap, the remediation
plan, task-specific source/tests and the September 21–22 agent logs. Bounded
subagents audited and implemented independent areas; their work was reconciled
against the shared tree.

## Changes and decisions

- Kept `gemini-embedding-001` as the default. Added a validated optional
  `gemini-embedding-2` profile with separate input representation, task modes,
  identity hash and pricing. The native adapter sends one `Content` per text,
  omits unsupported `task_type` for model 2, and rejects malformed, out-of-order,
  nonfinite and zero vectors. Migration `20260922_0016` and scoped retrieval
  keep 001, model 2 and historical OpenAI-compatible spaces distinct even at
  equal dimensions. Historical rows remain for restore but cannot be selected
  for new execution.
- Added canonical-page staged reindex and guarded per-Subject cutover/rollback
  operations. Staging and matching query retrieval were exercised with a
  deterministic model-2-shaped provider in disposable PostgreSQL; this is
  implementation and isolation evidence, not measured real-model-2 quality.
  No model-2 space was created or activated in the retained installation.
  The operator runbook requires backup, old-job drain, a maintenance window,
  aligned worker profile and subject-accurate disclosure before any future
  cutover. Nine-query isolated ablations measured recall@5, MRR, diversity and
  latency. The small synthetic corpus did not justify changing shipped
  retrieval policy or making an Embedding 2 quality claim.
- Added `two_request_local_support_v1` and Alembic `20260922_0017` with
  attempt-scoped stage accounting. Each Ask attempt allows at most one remote
  query embedding and one remote answer request, with zero SDK/application
  retries. An embedding failure prevents the answer call; uncertain execution
  cannot be replayed automatically. Old three-call snapshots remain fenced.
  SQL access/publication/revision/space filters, source reauthorization,
  canonical quote containment, citation checks and safe abstention remain.
- Pinned offline ONNX NLI and extractive-QA artifacts with verified hashes,
  graph signatures and bounded resources. The selected gate independently
  checks claim entailment, contradiction and relevant extractive answers; a
  definition paraphrase requires QA on both evidence and claim plus at least
  0.90 bidirectional NLI equivalence. It fails closed if models are missing
  or invalid. The bundle is operator-installed and mounted read-only. The
  dedicated answer worker runs as UID/GID 10001 in a pinned distroless Debian
  13 image with no network model download. Its legal attribution is included
  in the source and image.
- Added an accessible confirmation before each explicit manual Retry with a
  new attempt identity, an additional-cost estimate or an explicit unavailable
  estimate, and `Previous attempt cost is unknown` when appropriate. Profile
  disclosure refreshes before enqueue. Existing private history remains
  readable. ADR-018/019 and provider, configuration, migration, evaluation,
  deployment, database, accessibility, localization, runtime, roadmap,
  changelog, source maps and typed contracts were updated.

## Verification

- Backend offline suite: 845 passed, 2 skipped, 106 intentionally deselected.
  Focused local-support tests: 15 passed, 2 skipped. Targeted harness/release
  contracts: 87 passed. Disposable PostgreSQL: 89 passed, 3 skipped, including
  migration head/drift, empty downgrade/re-upgrade, staged-index/cutover,
  old-policy jobs, lifecycle races and uncertainty accounting. The guarded
  cross-stack journey passed with RAG off and on using the offline provider.
- The eleven-case authored local-support corpus (direct, paraphrase,
  unsupported and conflicting) passed 11/11 in three repetitions, with zero
  supported false rejections and zero unsafe acceptances. Literal quote-only,
  NLI-only and extractive-literal-only variants scored 4/11, 9/11 and 8/11.
  The 181,734,633-byte bundle started in 3,248.539 ms; check p95 was
  82.263 ms and RSS growth 330.555 MiB, within the documented ceilings.
  The first definition-paraphrase result exposed a real local-support false
  rejection; the independent QA/bidirectional-NLI fix passed the expanded
  corpus without relaxing the entailment or contradiction gates.
- The final explicitly authorized synthetic live Ask sample passed in
  28.05 seconds with exactly one query embedding and one answer request,
  no retries, and checked token/time/estimated-cost ceilings (at most
  $0.04). Earlier bounded diagnostics failed locally; one reached both
  provider calls. The provider did not provide a usable cost receipt for the
  failed attempt, so **previous attempt cost is unknown**. No additional paid
  call is inferred from a passing offline test. No real Embedding 2 provider
  quality evaluation was run.
- `npm run check` passed frontend types, lint, unit/component, coverage, build
  and Chromium checks: 4 unit, 36 component and 65 browser tests. The
  separately gated live password-reset browser test remained skipped. All
  four runtime image probes passed; the final answer image probe passed after
  the numeric ownership and legal changes. The final isolated Gitleaks and
  Trivy run passed Git-history/worktree secret gates and all four image
  HIGH/CRITICAL gates, retaining SBOMs and checksums under ignored
  `artifacts/security/`. An earlier Debian slim answer image failed the
  existing vulnerability threshold; switching to pinned distroless cleared
  it without lowering the gate. Two public tokenizer artifact digests triggered
  Gitleaks false positives and received line-specific suppressions.
- `check_context.py` passed 37 required files, 74 active guides and 1089
  links; `check_ci.py`, `check_release.py --version 0.1.0`, config migration
  preflight and `git diff --check` passed. Release validation initially found
  the backend NOTICE differed from its canonical/root/frontend copies; all
  three now match, images were rebuilt and the gates rerun.

## Retained installation and cleanup

Before upgrade, the stopped retained volume contained 3 users, 12 answer jobs,
one active 001 embedding space and no pending answer jobs. A restricted custom
backup was created and its catalog and SHA-256 checked; it was restored into
a separate rehearsal database, where schema revision and content-free counts
matched, then that disposable database alone was removed. The populated
`cardchemy_postgres_data` volume was never deleted or downgraded. Migrations
0016 and 0017 applied normally; Alembic current/head and drift checks passed.
After startup, content-free counts remained 3 users, 12 answer jobs, 3 private
threads and 17 private messages, with zero pending answer jobs, one 001 space
and zero model-2 spaces. The existing owner's history service returned ten
currently readable messages without exposing content; the active Subject
matched the configured 001 space and Ask's effective gate was true.

Only the three nonsecret Ask/local-support settings were appended to the
existing root `.env`; prior bytes and installation secrets were preserved.
Compose preflight passed. `docker compose up -d --wait --no-build` recreated
the local services on the migrated database; API, frontend and all workers
were healthy, routed `/healthz` and `/api/health/ready` returned 200, and an
unauthenticated private RAG profile request returned 401. Runtime inspection
confirmed API has neither RAG provider key, the answer worker has only its
required two RAG keys, and the index worker has only the embedding key.
Temporary scan/export containers and the disposable restore database were
removed; the verified pre-upgrade backup and protected volume were retained.

The local checkout and retained local stack are the evidence boundary. Hosted
CI on this uncommitted source, publication, another self-hosted installation,
real Embedding 2 relevance/cutover and the Lane 6 manual spoken assistive
technology release pass were not performed. Lane 6 remains open.
