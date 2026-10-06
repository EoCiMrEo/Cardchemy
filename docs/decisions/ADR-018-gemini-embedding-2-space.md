# ADR-018: Stage Gemini Embedding 2 as a distinct space

## Status

Accepted 2026-09-22 for product-quality Lane 4. This extends the native Gemini
embedding decision in [ADR-014](ADR-014-native-gemini-rag-profiles.md).
`gemini-embedding-001` remains the default and existing active spaces are not
reinterpreted. Embedding 2 is an optional staged profile that needs an explicit
per-Subject cutover after evaluation.

## Context

Google's stable model ID is `gemini-embedding-2`. It supports text inputs with
different formatting and request rules from `gemini-embedding-001`: Cardchemy
must send distinct `Content` objects, must not send the older `task_type`
parameter, and must express retrieval intent in versioned text. Equal output
dimensions do not make the models' vectors compatible. Mutable document titles
also cannot silently change the indexed representation.

The existing database already supports staged spaces, canonical-page reindex,
ready checks and atomic Subject cutover. Lane 4 must use those controls rather
than relabeling rows or changing one deployment-wide worker profile while old
jobs are still queued.

## Decision

The default profile remains native `gemini-embedding-001`, `raw_text_v1`,
1,536-dimensional normalized float32 cosine, with provider task types
`RETRIEVAL_DOCUMENT` and `QUESTION_ANSWERING`.

The optional Embedding 2 profile is:

| Field | Value |
| --- | --- |
| Provider/model | Native Gemini / `gemini-embedding-2` |
| Dimensions | 1,536, selected from the model's supported 128–3,072 range |
| Format version | `gemini2_qa_section_v1` |
| Document mode identity | `title_section_text_v1` |
| Query mode identity | `question_answering_query_v1` |
| Document text | `title: <immutable chunk section or none> | text: <canonical chunk>` |
| Query text | `task: question answering | query: <question>` |
| Provider request | One ordered `Content` object per input; no `task_type` |
| Maximum configured text input | 8,192 tokens |

The format and both mode identities participate in the embedding-space hash.
Migration `20260922_0016` admits this exact combination while retaining the
historical OpenAI-compatible and Embedding 001 combinations for restore. Its
downgrade refuses to remove the constraint support while any Embedding 2 space
exists. Vector validation retains exact count and order, fixed dimensions,
finite nonzero values, float32 conversion and L2 normalization for the selected
1,536-dimensional representation.

Indexing supplies the immutable server-derived chunk section as the formatting
title. The editable document title is excluded, so title edits do not mutate
the indexed input. Canonical chunk text remains the only citable evidence.
Bounded lexical terms, section-aware FTS and cross-document diversity exist as
explicit evaluation ablations; the shipped `hybrid_exact_v1` retrieval policy
and its thresholds remain unchanged until corpus results justify a new policy.

Staging uses canonical stored pages and a distinct space revision. Operators
stop Ask admission, drain or terminally resolve old-space index and answer jobs,
verify backup and capacity, build every target revision, evaluate matching
model-2 query embeddings, atomically cut over each Subject, align the process
configuration and then verify disclosure and retrieval. A partial failure
restores every switched Subject and the old process configuration, or leaves
Ask disabled. One single-profile answer worker never serves mixed active
spaces.

## Rationale

Versioned formatting makes the physical provider contract reviewable. A
distinct space hash prevents equal-dimension vector mixing. Staging from
canonical pages preserves the source of truth and provides a reversible
cutover without deleting old vectors. Keeping 001 as the default avoids an
unmeasured fleet-wide model change.

## Consequences

- Configuring model 2 also requires `gemini2_qa_section_v1`, a new space
  revision, the current reviewed input price and an 8,192-token-or-smaller
  input bound.
- The profile endpoint reports both configured and active identities. Ask is
  unavailable for a Subject until they match; Knowledge indexing remains
  available for first-time or staged indexing.
- Current official availability, price and limits must be reviewed again before
  a paid evaluation or operator root `.env` change. The reviewed 2026-09-22
  planning price was USD 0.20 per million text input tokens.
- Existing 001 and historical spaces remain readable and restorable. No
  migration relabels or deletes them.

## Related areas

[ADR-012](ADR-012-subject-knowledge-and-rag-boundaries.md),
[ADR-014](ADR-014-native-gemini-rag-profiles.md),
[configuration](../operations/CONFIGURATION.md), [profile migration](../ai/AI_PROFILE_MIGRATION.md),
[RAG evaluation](../ai/RAG_EVALUATION.md),
[Knowledge flow](../architecture/SUBJECT-KNOWLEDGE-FLOW.md).

Primary provider references:
[Gemini embeddings](https://ai.google.dev/gemini-api/docs/embeddings),
[Gemini models](https://ai.google.dev/gemini-api/docs/models), and
[Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing).
