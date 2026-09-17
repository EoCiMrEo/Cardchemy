# ADR-006: Validate grounded AI cards before persistence

## Status

Accepted. Current implementation verified on 2026-09-16.

## Context

PDF text and model output can contain instructions, malformed data, invented
facts, duplicate questions, and fabricated provenance. Structured provider
output alone cannot establish trustworthy teaching material.

## Decision

Use strict server-side contracts and deterministic grounding before persistence.
Each candidate must identify a server-issued chunk, contain four unique options
and one matching answer, and supply a quote found in that chunk after evidence
normalization. The answer must occur in that quote. Derive page/section from the
trusted chunk, reject near duplicates, and refill within configured bounds.
Persist only a complete result matching the requested count, as an unpublished
set of unapproved cards. Approval requires an explicit instructor action.

## Rationale

Server-owned provenance and independent validation keep model behavior outside
the persistence trust boundary. Atomic complete results avoid partial or empty
sets, while instructor review retains editorial responsibility.

## Consequences

Invalid output is rejected rather than coerced or truncated. A provider can
fail a job even when some candidates are valid. Grounding verifies evidence
containment and distinctness; it does not prove every question's educational
quality. No model confidence score approves a card.

## Related areas

- [AI generation architecture](../architecture/AI-GENERATION-FLOW.md)
- [Contracts](../../backend/app/ai/contracts.py), [grounding](../../backend/app/ai/grounding.py),
  [pipeline](../../backend/app/ai/pipeline.py), [persistence](../../backend/app/services/flashcard.py)
- [AI evaluation](../AI_EVALUATION.md), [ADR index](ADR-000-INDEX.md)
