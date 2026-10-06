# AI profile configuration migration

The former `AI_*` flashcard settings are removed in favor of
`FLASHCARD_AI_*`. The legacy `GEMINI_API_KEY` fallback is removed. Existing
installations must edit the one root `.env` or their private process-injection
configuration before recreating application processes. The exact 29-key mapping
is retained in the [archived approved plan](<../archive/Cardchemy-Subject-Scoped RAG Implementation Plan.md#mandatory-key-mapping>).
The application does not rename values or write an existing `.env` automatically.

The two-request Ask enablement section below is **historical**. New Ask work
follows source-only [ADR-022](../decisions/ADR-022-related-knowledge-primary-ask.md)
and the [Ask maintenance runbook](ASK_AI_SHUTDOWN.md). Do not enable an answer
model or local verifier for new Ask jobs.

## Safe sequence for an existing installation

1. Preserve the installation's Compose project/database identity and take a
   private, access-controlled backup of the current root `.env` and database.
   Do not run bootstrap over the existing file or rotate the signing,
   source-encryption or database secrets during this rename.
2. Pause new PDF generation admission with the old deployment. Inspect active,
   queued and source-retained retryable generation jobs through the authorized
   instructor UI/operations; let them complete, or use their existing cancel
   workflow before changing provider endpoint/account/model. Do not silently
   replay queued jobs against a different provider account. Record any jobs
   that must remain pending for a compatible worker. Stop/drain the generation
   worker as described in [deployment](../operations/DEPLOYMENT.md).
3. In a private editor, rename every nonempty old `AI_*` value to its matching
   `FLASHCARD_AI_*` name. Move a legacy-only `GEMINI_API_KEY` value to
   `FLASHCARD_AI_API_KEY`. If both old key names have nonempty values, resolve
   which credential is actually intended before editing; never print either
   value to a terminal, log or ticket. Remove the old names, including empty
   old template entries. New installation templates have no compatibility alias.
4. Choose explicit quota buckets and divide the provider account/project's
   actual RPM/input-TPM capacity across all enabled flashcard, indexing and
   answer worker roles and replicas. Separate keys do not create additional
   account quota. Keep `RAG_ASK_ENABLED=false` through this upgrade. Old
   three-call policy snapshots remain terminal under the current worker.
   Preserve the existing `RAG_ENABLED` choice for Knowledge capture/indexing.
   Set current model prices and confirm endpoint/model availability before any
   paid execution.
5. Run `python scripts/check_config_migration.py` from the repository root
   before `docker compose config --quiet` or native process startup. The
   preflight reports only removed key **names**, never values. Check private
   process-injected settings as well as the root file. Base Compose also has a
   name-only interpolation guard for nonempty old keys, including direct
   `config`/`up` invocations. Keep the explicit preflight in operator procedures;
   an empty process value can shadow a nonempty old root value during Compose
   interpolation, whereas the preflight checks both sources independently.
   The Compose defense-in-depth guard uses single-pass interpolation to append
   only nonempty removed key names to the otherwise valid one-shot migration
   service scale; that makes direct `config`/`up` fail without passing old
   values to a container or relying on version-sensitive nested interpolation.
   The mandatory standalone preflight remains authoritative for empty/root/
   process names and reports the complete migration mapping.
   The backend validates effective settings when each process starts.
6. Recreate the affected API/worker containers, since Compose interpolates
   values when creating containers; a plain restart keeps old injections. For
   native deployments, restart the affected processes with role-limited secret
   injection. Verify ready/health, availability controls, queued-job snapshot
   compatibility and the isolated no-quota deterministic journey before
   restoring new generation admission.

Historically, `RAG_AI_*` and `RAG_EMBEDDING_*` were independent profiles. The
former answer profile was `gemini-3.5-flash`; the initial vector space is
`gemini-embedding-001`, 1,536-dimensional float32 cosine, with document and
query formatting `raw_text_v1`. The new source-only Ask worker needs only the
query-embedding credential; an indexing worker needs only its embedding credential.
The existing generation worker needs only the flashcard credential. The API,
email worker and browser never receive provider keys. Dedicated index/answer
execution is implemented, but defining or enabling these settings alone does
not authorize paid RAG evaluation or provider spending.

The provider/model snapshot on an existing generation job remains a durable
contract; this migration does not rewrite used migrations or old job fields.
Changing a URL, key account or model can make a pending snapshot incompatible
even when the renamed values validate. Use the existing cancellation/draining
workflow to resolve that condition explicitly. Do not regenerate installation
secrets or delete a populated volume to fix configuration.

## Gemini-only Lane 1 upgrade

The 2026-09-22 provider decision accepted native `gemini` for Flashcard,
historical Ask-answer and embedding work. New Ask has no text-model role.
This is separate from the earlier `AI_*` key
rename. Run the name-only `python scripts/check_config_migration.py` preflight
against both root `.env` and private process injection before recreating any
service. It reports configured legacy provider/custom-endpoint **names** only;
never print credentials or provider URLs. In a private editor, set
`FLASHCARD_AI_PROVIDER` and `RAG_EMBEDDING_PROVIDER` to `gemini`, leave
historical `RAG_AI_PROVIDER_ENABLED=false`, and remove retired `*_BASE_URL`
fields. Also remove the retired
embedding document/query task-mode fields. Choose each text model from
the [verified catalog](AI_PROVIDERS.md) for Flashcards; keep the 3.8 Flashcard
and embedding-001 defaults unless changing them is deliberate. The
closed catalog rejects 3.7/3.8 with `minimal` thinking before a provider call.

Before this change, stop new admissions, drain compatible queued/retryable
Flashcard and index work, and use the
[Ask shutdown runbook](ASK_AI_SHUTDOWN.md) to terminally resolve old answer
jobs. Do not silently execute an old provider/model or old catalog-policy
snapshot on a new worker. A generation job whose snapshot is incompatible
fails before PDF extraction and removes its retained encrypted source; its
  manual retry returns a policy conflict. Record the terminal result and submit
  a new, explicitly authorized job if the source is still available. Keep Ask
  disabled until the two-request/local-support preflight below passes.

Keep historical `openai_compatible` rows and embedding-space identities for
restore and readback. If an active Subject uses a historical space, rebuild
from its canonical stored pages into a staged native Gemini space, validate
readiness and evaluation, then make an explicit atomic Subject cutover. Matching
vector dimensions do not permit relabeling. Preserve backup and old space until
the cutover and rollback evidence is complete. Follow
[database operations](../database/DATABASE_OPERATIONS.md) for a populated installation;
neither the real `.env` nor named volumes need deletion for this upgrade.

## Embedding 2 staging and Subject cutover

`gemini-embedding-001` remains the default. To evaluate
`gemini-embedding-2`, preserve the active 001 settings and backup first, then
use a separate controlled staging process configured with all of:

- `RAG_EMBEDDING_MODEL=gemini-embedding-2`;
- `RAG_EMBEDDING_FORMAT_VERSION=gemini2_qa_section_v1`;
- a new `RAG_EMBEDDING_SPACE_REVISION`;
- `RAG_EMBEDDING_MAX_INPUT_TOKENS` no greater than 8192; and
- the freshly reviewed input price, availability and quota limits.

Stop new Ask admission and drain or terminally resolve queued old-profile index
and answer jobs before changing a deployment-wide worker profile. Reindex from
canonical pages into the staged space, run the model-2 query/retrieval corpus,
verify every target content revision is ready, then use the guarded Subject
cutover. After all target Subjects move, align the index and answer worker
configuration and verify the authorized profile endpoint reports the matching
active/configured identities. Ask stays unavailable for a mismatched Subject.

On partial failure, atomically restore every already switched Subject to its 001
space and restore the old process configuration, or keep Ask disabled while
repairing the staged state. Retain old spaces and the backup. Do not relabel
vectors merely because both profiles use 1,536 dimensions. Migration
`20260922_0016` refuses schema downgrade while an Embedding 2 space exists.

## Historical Ask snapshots

The former answer/local-verifier policy is retired from new execution. Preserve
historical provider/model/space/job identities and source-access/redaction rules;
never install its old research artifacts or replay an uncertain attempt to
migrate it. Current source-only Ask activation/pause uses the separate
[maintenance procedure](ASK_AI_SHUTDOWN.md), explicit Ask/judge flags and matching
current policy, active embedding space, prices and release evidence. Manual Retry
requires a fresh idempotency/quota identity and possible-extra-cost disclosure.
