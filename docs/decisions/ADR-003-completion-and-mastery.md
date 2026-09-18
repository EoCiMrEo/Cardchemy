# ADR-003: Completion and mastery are separate metrics

## Status

Accepted; existing behavior verified 2026-09-16.

## Context

Attempting every card and retaining knowledge across spaced review are
different learning milestones.

## Decision

Completion is attempted cards (`last_reviewed` present) divided by total
approved cards. Mastery is cards in `review` or `mastered` divided by that
same total. Empty sets yield zero; percentages round to one decimal.

## Rationale

An incorrect first attempt still represents participation, while longer
scheduled intervals represent a separate retention signal.

## Consequences

UI and API must label the metrics separately. Status thresholds are learning
below 7 days, review at 7–20, mastered from 21. Accumulated correct attempts
are not completion percentage.

## Related Areas

[Progress service](../../backend/app/services/flashcard.py),
[progress tests](../../backend/tests/test_study_progress.py),
[study flow](../architecture/STUDY-PROGRESS-FLOW.md), [ADR index](ADR-000-INDEX.md).
