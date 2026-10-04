# Lane 6 Gemini source-ID architecture decision

Date: 2026-09-28 (America/Chicago). Branch `main`, starting HEAD
`6c02d6c`, shared uncommitted remediation worktree. Scope: documentation
only. The retained populated database, root `.env`, encrypted original PDFs,
public audit ledgers and disabled Ask policy were not changed.

## Starting evidence and decision

The source-selection root-cause review found useful original PDF pages in
the displayed top three for 11/11 exposed published questions, but only
19/33 displayed cards useful. The public pair-score pool held useful
cue/pages in top three for 36/36 calibration positives, yet three distinct
one-shot local display selectors failed their combined calibration gates.
All three ledgers are consumed, no public heldout score for those candidates
was accepted, and the fresh two-PDF release holdout remains unscored.
These observations justify testing a different page-selection signal, not
claiming a model defect or quality pass. See the
[root-cause review](2026-09-28-source-selection-root-cause-review.md) and
[source judge options](2026-09-28-source-judge-options.md).

The operator broadly approved the recommended next steps on 2026-09-28.
The approved architecture permits a prospective source-only Gemini source-ID
judge. Repository AI-evaluation rules still require a separate exact paid
request envelope before *any* live call; broad architectural approval does
not specify endpoint/model/price/call/token/time/cost limits or authorize
private lecture transfer. No paid call or private transfer occurred for
this documentation task.

## Documentation changes

- Added [ADR-024](../../../docs/decisions/ADR-024-gemini-source-id-judge.md)
  because one remote source-judgment request and candidate page-text egress
  reverse part of ADR-023's provider/privacy boundary. It preserves source-
  only pedagogy, current-question-only embedding, ID-only judgment, local
  canonical reference derivation and whole-bundle revalidation, with a new
  prospective v4 snapshot and `source_judgment` stage. The prior-answer
  model/verifier remains retired.
- Linked the partial supersession from [ADR-023](../../../docs/decisions/ADR-023-original-pdf-source-navigation.md)
  and the [ADR index](../../../docs/decisions/ADR-000-INDEX.md), while retaining
  the historical failed local audit records.
- Updated [Lane 6](../../../docs/development/PRODUCT-QUALITY-REMEDIATION-PLAN.md)
  and [current state](../../../docs/development/CURRENT-STATE.md) to distinguish
  prospective architecture from the currently running, Ask-off v3 policy.
  None of four open Lane 6 boxes was closed.
- Updated [AI evaluation](../../../docs/AI_EVALUATION.md),
  [RAG evaluation](../../../docs/RAG_EVALUATION.md) and
  [privacy](../../../docs/PRIVACY.md) with public-first measurement, the
  independent >=90%-of-all-displayed-pages plus question-hit/no-match gates,
  cost uncertainty, and prospective lecture-content egress disclosure.

## Boundary and next work

The first trial is public-PDF-only and must freeze deployment-shaped
multi-PDF candidates, same-topic weak/no-useful controls, selection/schema,
calibration/holdout, model and hard resource/cost budgets before scoring.
The preliminary target is Gemini 3.8 Flash with low thinking and no answer
text, up to four exact public page candidates and 8,192 input/1,024 output
tokens per source-rank call; these are design guards, **not** an authorized
live envelope. Its four-page pool cannot by itself prove runtime behavior
with up to twelve locally inspected pages. A public failure stops that
candidate; it does not permit heldout tuning or automatic fallback to a
failed local selector. The fresh two-PDF twelve-question holdout remains
unscored until a candidate/rule is frozen, and real published Knowledge
egress needs a separate disclosed quality/cost decision.

The release fence remains closed: useful original PDF page in displayed
top three >=10/12 overall and >=3/4 for each direct/paraphrase/follow-up
form, exposed regression >=10/11, >=90% useful among **every displayed
card**, zero fabricated/unauthorized/stale/wrong-page references, plus
no-match, PDF-open, privacy, accessibility and operational checks. A
prospective judge score is not verified evidence and cannot answer students.

## Verification and limits

Documentation-only change. `python scripts/check_context.py` passed:
37 required files, 79 active guides and 1,449 local links. `git -c
core.safecrlf=false diff --check` passed. These checks validate context
links and whitespace, **not** source-judge behavior, provider availability,
privacy terms, the independent usefulness gate or a release. No code,
migrations, root settings, Docker service, provider request, Knowledge
index or release flag changed here. Current runtime source-only v3 and
disabled Ask remain authoritative.
