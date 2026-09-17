# ADR-001: Four-option multiple-choice cards

## Status

Accepted; existing behavior verified 2026-09-16.

## Context

Manual editing, AI generation, study selection and database persistence need
one consistent card contract.

## Decision

The current product supports only `multiple_choice`: exactly four trimmed,
nonempty options, unique without case distinctions, with `back_content`
matching one option and canonicalized to its stored text.

## Rationale

A shared contract removes ambiguous answers and lets the server validate
manual, generated and partially edited content consistently.

## Consequences

Other card types require a deliberate contract change. API validation and
PostgreSQL checks enforce the invariant; editors keep an explicit correct-option selection.

## Related Areas

[Card schemas](../../backend/app/schemas/flashcard.py),
[card model](../../backend/app/models/flashcard.py),
[validation tests](../../backend/tests/test_flashcard_validation.py),
[data model](../architecture/DATA-MODEL.md), [ADR index](ADR-000-INDEX.md).
