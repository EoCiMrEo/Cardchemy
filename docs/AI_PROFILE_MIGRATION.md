# AI profile configuration migration

The former `AI_*` flashcard settings are removed in favor of
`FLASHCARD_AI_*`. The legacy `GEMINI_API_KEY` fallback is removed. Existing
installations must edit the one root `.env` or their private process-injection
configuration before recreating application processes. The exact 29-key mapping
is in the [approved plan](<../Cardchemy-Subject-Scoped RAG Implementation Plan.md#mandatory-key-mapping>).
The application does not rename values or write an existing `.env` automatically.

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
   worker as described in [deployment](DEPLOYMENT.md).
3. In a private editor, rename every nonempty old `AI_*` value to its matching
   `FLASHCARD_AI_*` name. Move a legacy-only `GEMINI_API_KEY` value to
   `FLASHCARD_AI_API_KEY`. If both old key names have nonempty values, resolve
   which credential is actually intended before editing; never print either
   value to a terminal, log or ticket. Remove the old names, including empty
   old template entries. New installation templates have no compatibility alias.
4. Choose explicit quota buckets and divide the provider account/project's
   actual RPM/input-TPM capacity across all enabled flashcard, indexing and
   answer worker roles and replicas. Separate keys do not create additional
   account quota. Keep `RAG_ENABLED=false` until the relevant later execution
   phases are installed and deliberately enabled. Set current model prices and
   confirm endpoint/model availability before any paid execution.
5. Run `python scripts/check_config_migration.py` from the repository root
   before `docker compose config --quiet` or native process startup. The
   preflight reports only removed key **names**, never values. Check private
   process-injected settings as well as the root file. Base Compose also has a
   name-only interpolation guard for nonempty old keys, including direct
   `config`/`up` invocations. Keep the explicit preflight in operator procedures;
   an empty process value can shadow a nonempty old root value during Compose
   interpolation, whereas the preflight checks both sources independently.
   The internal `CARDCH_LEGACY_AI_CONFIGURATION_ERROR` sentinel must remain
   unset; configuring it can also bypass Compose's nested interpolation guard.
   Treat that guard as defense in depth. The mandatory standalone preflight
   rejects removed root/process names independently of the sentinel.
   The backend validates effective settings when each process starts.
6. Recreate the affected API/worker containers, since Compose interpolates
   values when creating containers; a plain restart keeps old injections. For
   native deployments, restart the affected processes with role-limited secret
   injection. Verify ready/health, availability controls, queued-job snapshot
   compatibility and the isolated no-quota deterministic journey before
   restoring new generation admission.

`RAG_AI_*` and `RAG_EMBEDDING_*` are independent profiles. The initial answer
profile is `gemini-3.5-flash`; the initial vector space is
`gemini-embedding-001`, 1,536-dimensional float32 cosine, with document and
query formatting `raw_text_v1`. An answer worker needs its answer and query
embedding credentials; an indexing worker needs only its embedding credential.
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
