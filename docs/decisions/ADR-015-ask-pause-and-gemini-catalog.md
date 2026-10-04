# ADR-015: Pause legacy Ask AI and require a verified Gemini text catalog

## Status

Accepted 2026-09-22 for product-quality Lanes 0 and 1. This supersedes
ADR-012's historical OpenAI-compatible provider selection for new work and
ADR-014's unrestricted text-model and active three-call Ask execution choices.
ADR-014's `gemini-embedding-001` task modes and space identity remain accepted.
The replacement decision is now
[ADR-019](ADR-019-two-request-local-support-ask.md). This record still owns the
closed text catalog, default-off Ask switch and historical three-call fence.

## Context

The existing Ask worker uses a query embedding, an answer request and a remote
semantic-support request for a supported answer. A reported case reached
retrieval and then failed support validation. Gemini 3.7 and 3.8 reject the
`minimal` thinking level. Accepting arbitrary text model IDs under a shared
wire policy can therefore admit work that fails only after provider execution.
Historical jobs and embedding spaces must retain their original identity.

## Decision

Ask AI has a separate default-off, fail-closed availability gate. New thread,
question and manual-retry admission and answer-worker execution stay blocked
while the legacy three-call policy is installed, even if an operator sets the
flag true. Authorized private history and source reads, cancellation, Knowledge
capture, indexing and reindexing remain available according to their own
access and feature gates. Operators stop admission before resolving queued or
running old jobs; uncertain provider execution is never silently replayed.

New text work uses native Gemini only. Flashcard and Ask roles have independent
model settings but resolve through one versioned, closed capability catalog:
`gemini-3.5-flash-lite`, `gemini-3.5-flash`, `gemini-3.6-flash`,
`gemini-3.7-flash` and `gemini-3.8-flash`. The catalog records role, supported
thinking levels, output/context ceilings, the provider-default sampling rule,
usage treatment, current reviewed prices and the inline JSON schema policy.
`minimal` is rejected for 3.7 and 3.8 before a provider call. The independent
3.8 Flashcard and 3.5 Ask defaults remain. Catalog and schema-policy versions
are snapshotted at enqueue and checked again in the worker; an old or changed
snapshot is terminal rather than being silently mapped to a new model.

New settings and provider factories reject `openai_compatible` and custom
base URLs. Historical rows, private history and OpenAI-compatible embedding
space identities remain readable for recovery, but new work must not use or
relabel those vectors. Existing operators run the name-only configuration
preflight, preserve their root `.env` and data, drain old jobs, and use canonical
stored pages plus staged reindex/cutover for a historical active space. They
must not rewrite used migrations or rotate installation secrets as part of this
provider change.

## Rationale

A separate Ask gate stops the expensive legacy path without disabling private
Knowledge. A closed catalog catches known model-parameter incompatibilities
before quota or cost is spent. Versioned snapshots preserve the meaning of
queued work and make policy changes explicit. Keeping historical identities
supports restore and source/history ownership without allowing mixed spaces.

## Consequences

- The legacy remote-support path and its old snapshots stay terminally fenced.
  ADR-019 defines the only new Ask execution policy; operators still keep the
  default-off switches false until its local artifacts and release gates pass.
- A catalog or schema-policy change requires version review and explicit
  resolution of queued work. A generation job with an incompatible snapshot
  fails safely and removes retained source; manual retry cannot reinterpret it.
- A configured key, catalog price or model entry is not live-test or deployment
  authorization. Current prices and availability must be reviewed before paid
  execution. Routine CI uses offline fakes.

## Related areas

[ADR-012](ADR-012-subject-knowledge-and-rag-boundaries.md),
[ADR-014](ADR-014-native-gemini-rag-profiles.md),
[ADR-019](ADR-019-two-request-local-support-ask.md),
[Ask shutdown operations](../ASK_AI_SHUTDOWN.md),
[provider guide](../AI_PROVIDERS.md),
[profile migration](../AI_PROFILE_MIGRATION.md),
[Knowledge flow](../architecture/SUBJECT-KNOWLEDGE-FLOW.md),
[active remediation plan](../development/PRODUCT-QUALITY-REMEDIATION-PLAN.md).
