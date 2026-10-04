# Categorical page judge: approved keyless prototype and regression proof

Date: 2026-09-30 (America/Chicago). This is offline implementation and
verification evidence, **not** a public quality pass or Ask activation.

## Starting context and authorization

Lane 6 was 3/7 with Ask disabled at migration `20260928_0029`. The public
Flash-Lite Boolean judge underselected useful pages. The separately approved
Gemini 3.5 Flash comparison stopped after seven valid responses and three
HTTP 503s, before a calibration score; its one-use ledger is consumed. The
different-PDF 60-case holdout remains unopened. The owner approved the
[categorical proposal](2026-09-30-categorical-page-judge-recommendation.md)
for a Lane 6/ADR-024 amendment and **keyless offline prototype only**. This
does not authorize a provider call, private Knowledge transfer, runtime policy
or enablement.

## Changes

- Added a prospective, separate four-label public wire and deterministic
  parser in `scripts/prototype_categorical_page_judge_v1.py`, with focused
  synthetic contracts in
  `backend/tests/test_categorical_page_judge_public_prototype.py`.
- The wire asks for one label per issued page ID: `DIRECT_RELATION`,
  `USEFUL_BRIDGE`, `TOPIC_ONLY`, `IRRELEVANT`. The local parser requires exactly
  four unique issued IDs, rejects extra fields/text/duplicates/foreign IDs
  and selects the first at most three direct/bridge pages in issued order.
  A valid empty selection is distinct from a transport/schema failure. The
  prompt requires both the shown cue and page to provide a concrete link to
  the requested relationship, and rejects same-topic transitions.
- Updated Lane 6, ADR-024 and the ADR index for this **prospective** candidate.
  Existing 66 exposed calibration cases, 60 sealed heldout cases, 90%-of-all-
  displayed usefulness, exact-cardinality, no-match and availability gates
  remain intact; no checklist item was closed.

## Checks and results

- Full backend offline suite before the new prototype: **2,728 passed, 151
  skipped, 2 deselected** in 287.07 seconds. The skipped/deselected tests do
  not establish provider, service or browser success.
- New categorical and prior Boolean prototype focused tests after the change:
  **51 passed**. A keyless read-only preflight accepted **66/66** exposed
  calibration wires; maximum wire size was **8,012/8,192 bytes**. The sealed
  heldout was not read by this preflight.
- Disposable PostgreSQL service suite using the project backend environment:
  migration head/drift and empty-schema downgrade/re-upgrade passed; **131
  passed, 3 skipped, 2,747 deselected** in 133.20 seconds. The disposable
  container and generated credentials were cleaned up; the populated local
  database was not used. An initial invocation with system Python failed
  because it lacked the project's dependencies; the correct venv invocation
  passed.
- Deterministic disposable browser journey passed both RAG-disabled and
  Knowledge/index/source-only-Ask-enabled paths, including authorized page
  references; disposable containers, data, fixture and credentials were
  cleaned up. The journey uses no live provider call.
- `python scripts/check_ci.py` passed mandatory workflow/protection and
  bundle-contract validation. `python scripts/check_context.py` passed with
  37 required files, 79 active guides and 1,632 local links before the final
  ADR amendment; the documentation agent then reran it at 1,634 links and
  passed. `git -c core.safecrlf=false diff --check` passed.

## Limits and next gates

These are parser/synthetic and regression results, not evidence that a model
will label lecture pages correctly. `USEFUL_BRIDGE` can admit weak pages; a
follow-up with an unclear referent may still be mishandled by a remote judge.
The dormant application v4 uses a different wire, response shape, candidate
count and model, so even a passing public pilot cannot activate it unchanged.
The proposal's 66-case calibration and sealed 60-case heldout require a new
frozen candidate, one-use receipt and **separate exact live-provider envelope**
before any request. Independent private original-PDF/page/cue review, matching
runtime, access, accessibility and release measurements remain open. Ask stays
disabled; Lane 6 stays **3/7**.
