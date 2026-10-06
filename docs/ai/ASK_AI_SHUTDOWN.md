# Ask AI maintenance and shutdown

## Current source-only release — 2026-10-04

Ask AI is enabled in the retained local installation (verified 2026-10-04). Fresh installations remain default-off. The operator
enables Ask separately from Knowledge with `RAG_ASK_ENABLED` and
`RAG_SOURCE_JUDGE_PROVIDER_ENABLED`; source/schema migration alone never
enables either. Original-PDF browsing, reviewed Knowledge and authorized private
history remain usable when Ask is off.

The current new-job identities are `related_knowledge_navigation_v8` /
`hybrid_source_navigation_v9` / `visual_source_id_v5`, with immutable
`literal_subject_admission_v2` context on retained/source head `20261002_0033`.
Each attempt allows at most one raw-current-question embedding and one bounded
source-ID judgment, zero generated-answer/verifier calls and zero automatic
retries. It returns zero to three exact current published-PDF page references,
each visibly unverified; weak pages are never padding. An eligible unresolved
follow-up can transfer only a unique literal subject from the strictly preceding
user question (at most 160 characters/twelve words), immutably bound and
rechecked. Full history and assistant text stay out of provider input.

The judge is `gemini-3.5-flash-lite`, HIGH thinking, 32,768 input/4,096 output
tokens including thinking, a 120-second deadline and zero retries. It receives
only the current question, authorized published exact text and up to four
bounded original-page PNGs, plus the admitted literal subject when applicable.
The API reports no generated-answer capability. A failed judge is not a true
no-match. A transient embedding failure may use bounded local lexical search
without another embedding request; the degraded mode and failure remain visible.

Original PDFs are encrypted and revision-bound, attached only by exact source
SHA/page count, and read through authenticated metadata/byte ranges after
current bundle authorization. The viewer opens the physical cited page with
adjacent exact extracted text; text offsets do not claim visual highlighting.

The accepted quality floor is **80% useful among all actually displayed cards**,
with separate positive hit/form, ordinary no-match/availability and zero
fabricated, stale, unauthorized or wrong-page source gates. See the
[actual local closure evidence](../../.agent/logs/2026-10-03/2026-10-03-lane6-final-closure-and-activation.md),
[ADR-023](../decisions/ADR-023-original-pdf-source-navigation.md) and
[ADR-024](../decisions/ADR-024-gemini-source-id-judge.md). Evidence distinguishes
real provider outcomes/current SQL/PDF guards from controlled frontend replay,
and preserves historical failures and unknown costs. No hosted CI or production
deployment is claimed by local activation.

## Activating or pausing the current v8 installation

1. Keep both installation flags false while upgrading or changing policy. Drain
   writers, preserve a restore-verified backup/archive key and all data, migrate
   forward only when needed, and check every current Alembic head/model drift.
   Preview/resolve incompatible queued/running Ask jobs with the guarded CLI
   below; never reinterpret an old snapshot or replay uncertain provider work.
2. Require matching image, Subject embedding space, role flags, nonzero current
   prices, divided quota labels and isolated worker credentials. Complete the
   independently frozen displayed-card/page, source/access, keyboard/spoken and
   offline/disposable/image/security gates. A migration, configured key or
   architecture approval is not provider-evaluation authority. Every live trial
   still needs its exact endpoint/model/price/call/token/time/cost envelope.
3. After an approved measured release opens the v8 source fence, set only the
   two Ask/judge flags in the existing root `.env` and recreate matching API and
   workers under the selected documented Compose profile. Development binds
   source into API/generation/email, but index/answer workers execute immutable
   image bytes; an API reload or restart does not refresh that worker or its
   environment. Preserve default-off template values and all unrelated settings.
4. Verify current heads/drift, all process/edge health and the authenticated
   `/subjects/{id}/rag/profile`: v8, active-space match, Ask and judge available,
   visual-v5/HIGH and published-text/image/literal-subject disclosure; answer
   availability false with null answer provider/model. Negative wrong-space,
   old-policy retry and lost-access cases remain closed. Do not issue a paid
   question as an unapproved health check.
5. For immediate off rollback, close **both** Ask/judge flags, drain and recreate
   API/answer worker. Preserve global RAG/embedding availability, history,
   original PDFs, keys, data and uncertain execution records. Flag rollback
   requires no schema downgrade or restore; the preserved old immutable image
   is an additional off-mode recovery option. Each manually confirmed Retry
   acknowledges possible extra cost and unknown previous cost; no automatic
   provider replay occurs.

The following legacy-retirement procedure remains applicable. The dated v4
preparation section is historical; the current v8 contract and closure above
govern new work.

## Retiring a legacy installation

1. Record the exact code revision and current Alembic heads. Preserve the root
   `.env` and make a verified, access-controlled database backup using
   [database operations](../database/DATABASE_OPERATIONS.md). Keep the original volume.
2. Stop public Ask admission **before** changing the answer worker. On an old
   release without `RAG_ASK_ENABLED`, stop the API (`docker compose stop
   backend`) or block its Ask routes at the trusted edge. This may temporarily
   interrupt other API flows; schedule a maintenance window. Do not rely on
   `RAG_ENABLED=false`, which would also stop Knowledge work.
3. Let already running answer claims finish if acceptable under the previous
   policy. Use the private `operations-status` CLI from a still running worker
   container to inspect aggregate `rag_answer` status counts. A queued job has
   not begun provider execution; a running job with a provider boundary may
   have uncertain external execution. Do not automatically replay either under
   a new provider or policy. Stop the old `answer-worker` gracefully and verify
   no old answer worker replica remains before resolving jobs.
4. Deploy the new code and migrate with all writers stopped. Keep
   `RAG_ASK_ENABLED=false` in the single root `.env` or leave it absent so the
   Compose default remains false. Recreate the API and answer-worker containers
   to apply the effective setting. `docker compose restart` alone retains old
   container environment values.
5. Run `python -m app.cli resolve-ask-shutdown` to preview queued, running and
   possibly remote-executed jobs. With every answer worker stopped, run
   `python -m app.cli resolve-ask-shutdown --apply --writers-stopped` from a
   container with the new image and current database head. This marks remaining
   old jobs terminal with a safe shutdown code, preserves their question and
   history rows, records remote uncertainty, and prevents silent retry. Review
   the preview and applied counts. The command does not erase content.
6. Start the new API, Knowledge index worker and other normal services. The
   answer worker may run in its healthy disabled state. Verify the authorized
   `/subjects/{id}/rag/profile` response reports `ask_enabled=false` and
   `ask_available=false`; new thread/question/retry requests return the safe
   unavailable response. Existing owner-private history, source reads and
   cancellation remain authorized. Verify Knowledge upload/indexing/reindexing,
   generation and Study independently. Run `operations-status` again and
   confirm no queued/running answer jobs or new physical answer requests.

For a clean checkout with no running services, steps 2–3 have no active
containers to drain; still inspect retained jobs before starting an upgraded
answer worker. The resolution command is repeatable after the first successful
application. Keep `RAG_ASK_ENABLED=false` during restart and ordinary rollback.

Historical v4/0029 and earlier maintenance checkpoints are preserved in [dated logs](../../.agent/logs/README.md) and [ADR-024](../decisions/ADR-024-gemini-source-id-judge.md). Apply the current v8 activation/pause procedure above; do not replay their consumed attempts.

## Recovery and monitoring

Watch content-free answer status counts, safe failure stage/category, physical
request and retry counts by stage and attempt, uncertain execution flags, and
disabled worker health through [observability](../operations/OBSERVABILITY.md). These counters
are incomplete billing evidence, especially when a network call or process
ended ambiguously. Do not infer zero provider spend from a failed job.

If the shutdown deployment fails, keep new Ask admission closed. Restore the
prior code and database state only through the verified backup or a separately
proven, safe schema rollback with all writers stopped. Never restore the prior
answer behavior as a fallback. Flipping `RAG_ASK_ENABLED` alone is
insufficient: current embedding and source-judge prices/credentials, source-only release policy
and a matching Subject space must also pass. Never downgrade a populated database merely to
make a worker start, and never delete its volume as a rollback shortcut.
