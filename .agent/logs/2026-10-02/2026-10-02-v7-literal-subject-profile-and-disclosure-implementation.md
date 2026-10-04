# V7 literal-subject profile and browser disclosure implementation

## Scope and authority

Implemented the approved prospective navigation v7 public-profile and browser
disclosure changes after the [earlier read-only draft](2026-10-02-v7-literal-subject-disclosure-draft.md).
The main Lane 6 task authorized these matching backend/frontend contracts;
the separate public pilot remains owned by that task. Read the applicable
repository guidance and React best-practices skill, and preserved the shared
dirty working tree and pre-existing changes.

This change does not enable retained Ask/source judging, build or replace
retained services, inspect keys, make provider requests, read private Knowledge,
or mutate the database/root `.env`. It does not modify consumed public pilot
code, visual-v2 source/preparation/renderer code, signed private labels or frozen
review evidence. Retained enablement and usefulness/release gates remain open.

## Implemented contract

- [Backend schema](../../../backend/app/schemas/rag.py) and
  [profile router](../../../backend/app/routers/rag.py): add navigation v7 and
  the non-secret Boolean `source_judge_transfers_literal_subject_context`.
  It is true only for v7 with `visual_source_id_v3`; historical policies report
  false. Include v7 in visual metadata, retain Subject authorization before
  profile/space disclosure, and retain unavailable/wrong-space/default-off
  behavior and `answer_available=False`. No prior question, subject value,
  provenance identity, private hash or credential appears in the HTTP profile.
- [Typed API contracts](../../../frontend/src/services/types.ts) and
  [Ask panel](../../../frontend/src/components/rag/AskAiPanel.tsx): require
  v7, visual-v3, explicit context capability, HIGH/page-image transfer and the
  existing availability/profile predicates before new search. Missing/false
  capability and the old wire fail closed. Profile comparison includes the
  capability before enqueue and before manual retry confirmation.
- Historical v6 references remain readable. Only matching v7 jobs can show
  or execute retry under a valid v7 profile; old jobs cannot be replayed under
  the new processor.
- [English catalog](../../../frontend/src/i18n/en.ts): disclose the unchanged
  current question for at most one query embedding and selected authorized
  published text/full-page PNGs in at most one page-selection request. An
  unclear follow-up may supply a literal subject of at most 160 characters
  from the immediately preceding user question in this conversation only to
  page selection. Full earlier questions, chat history, assistant answers and
  original PDF file bytes are not sent. Page labels/IDs are unverified reading
  suggestions, with no generated answer.
- Manual retry presents the same scope, possible additional cost and explicit
  confirmation; the existing unknown-previous-cost warning remains. Browser
  submission still contains only the current question and existing selected
  document IDs. It does not extract a prior subject or append history itself.

The profile expresses possible transfer even while Ask is paused. Browser
checks are UX fences; authoritative admission ordering, source access,
provider authorization and release controls remain backend responsibilities.

## Verification actually completed

| Check | Result |
| --- | --- |
| New injected [v7 profile contracts](../../../backend/tests/test_source_literal_subject_profile_v7.py), `venv/Scripts/python.exe -m pytest tests/test_source_literal_subject_profile_v7.py -q --disable-warnings` from backend | 10 passed, with no operator environment, provider or real DB |
| Focused [Ask component contracts](../../../frontend/tests/components/askAiFailureCopy.test.tsx), `npx vitest run tests/components/askAiFailureCopy.test.tsx --coverage=false` from frontend | 36 passed |
| `npm run typecheck`, `npm run typecheck:components`, `npm run typecheck:e2e` | Passed |
| Scoped ESLint on the six changed frontend source/test/fixture files | Passed |
| [Knowledge/Ask Chromium contracts](../../../frontend/e2e/rag-knowledge.spec.ts), `npm run test:e2e -- rag-knowledge.spec.ts --workers=1` | 8 passed; managed local test server ended normally |
| Scoped `git diff --check` | Passed; existing CRLF conversion notices only |

Coverage includes historical capability false, old visual wire, unauthorized
Subject, mismatching embedding space, paused profile, absence of private
profile fields, missing/false browser capability, current-question-only body,
v6 history without replay, draft preservation after capability changes,
pre-confirmation retry refresh, unknown previous cost, cancellation and one
explicit retry dispatch. The browser suite also retains Knowledge independence,
durable job states, extracted-page fallback, paused Ask and changed-provider
disclosure checks.

Two new test expectations were repaired before the final passing runs: the
component test initially used nonexistent catalog keys, and a browser body
assertion omitted the pre-existing empty `document_ids` list. Those were test
fixture mistakes; neither required a runtime behavior change. A deliberate
mock PDF-metadata 404 logs the expected text fallback in the browser suite and
is not evidence about the retained original-PDF service.

## Limits and handoff

The full frontend check/build/bundle gate, full backend/journey/release checks,
independent private usefulness and live retained browser behavior were not run
by this bounded implementation task. The main Lane 6 task must complete those
integrated checks and the authoritative v7 worker/admission path before any
activation. New disclosure copy must remain inside the approved measured bundle
budgets; no coverage/accessibility/security threshold was changed here.

The old draft and signed review remain historical evidence. Public model
quality, private-data transfer authorization and activation are not established
by these mocked contracts. Retained Ask remains disabled.
