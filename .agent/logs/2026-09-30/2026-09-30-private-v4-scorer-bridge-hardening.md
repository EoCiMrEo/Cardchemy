# Private v4 display scorer: bridge and frozen-input hardening

Date: 2026-09-30 (America/Chicago).

## Starting context

Lane 6 remains 3/7 with Ask disabled. The new 12-case original-PDF gold
packet is frozen, but no fresh private candidate slates, signed exact-cue
reviews, runtime observations or actual score exist. The preceding public
per-page calibration failed multi-page selection, so the private holdout
remains sealed. Historical topic-pattern T01–T12 proposals are not fresh gold.

## Change

Independent read-only review found that the v4 release scorer accepted
signed components without requiring the existing stage-1 gold-to-slate
bridge, used duplicate-key-permissive JSON parsing on frozen CLI inputs and
omitted the ADR-023 top-one usefulness count. The offline scorer now requires
the exact frozen stage-1 gold, authorized-page snapshot, four-page slates,
candidate page/cue labels and bridge admission before aggregating a private
release result. It rejects duplicate keys, including nested keys, in every
frozen CLI JSON input and reports top-one useful/displayed and positive
top-one useful/positive-case counts. Synthetic tests cover the refusals.

Files changed: `scripts/score_source_judgment_display_v4.py`,
`backend/tests/test_source_judgment_display_v4_score.py`,
`docs/RAG_EVALUATION.md` and `PROJECT-MAP.md`.

## Checks and limits

The bounded agent ran 48 focused scorer/bridge tests; a separate root run
passed 85 public-caller/scorer/bridge tests after exact live-envelope pinning.
`python scripts/check_context.py` passed (37 required files, 79 active
guides, 1,626 local links) and `git -c core.safecrlf=false diff --check`
passed. An initial root pytest invocation from the repository root failed
because the backend package was outside `PYTHONPATH`; rerunning from the
backend directory passed. That invocation was a test setup error, not a
product regression.

The pure bridge validates a **caller-supplied** authorized snapshot. It
cannot prove that a future snapshot was captured from a live authorized
database transaction, or that a reviewer saw the original PDF. Those
provenance steps and a real private score remain outstanding. The scorer's
release flag remains closed. No private document text, database, provider
request, Ask activation or heldout score was used in this hardening.
