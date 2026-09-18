# ADR-002: Server-derived answer correctness

## Status

Accepted; existing behavior verified 2026-09-16.

## Context

Progress counters and scheduling must not trust client-provided correctness
or quality scores.

## Decision

Clients submit one option text/index or explicit null. The server compares it
with the canonical stored answer, derives correctness and assigns quality 5
for correct or 1 for incorrect/no-answer. Study sessions omit the answer;
feedback returns it after a committed submission.

## Rationale

All clients share one authoritative progress rule and cannot directly assign
their own score through the answer API.

## Consequences

Study needs online persistence before feedback/advance. Durable receipts make
logical answers safe to retry. General student card-read endpoints currently
expose `back_content`; this decision does not provide exam secrecy.

## Related Areas

[Study router](../../backend/app/routers/study.py),
[answer resolution](../../backend/app/services/flashcard.py),
[schemas](../../backend/app/schemas/flashcard.py),
[study flow](../architecture/STUDY-PROGRESS-FLOW.md), [ADR index](ADR-000-INDEX.md).
