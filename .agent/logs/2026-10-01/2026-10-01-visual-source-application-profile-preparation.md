# Visual source application contract and disclosure preparation

Date: 2026-10-01 (America/Chicago).

## Scope and authority

Offline application preparation follows the operator's standing aligned Lane 6
authorization in the [approved metric decision](2026-10-01-source-navigation-metric-alignment-approved.md).
The prospective displayed-card usefulness floor is 80% on the complete public
and independent private evaluations. These synthetic checks do not establish
that threshold or any release pass. Lane 6 remains 3/7; Ask remains fenced off.

Starting branch was `main`, HEAD `6c02d6c`. The shared working tree already
contained substantial implementation and evidence changes; those were preserved.
Read root governance, scoped application consumers, current settings, frozen
public visual request/parser source, and the existing disclosure/test contracts.
No real root environment, private PDF, heldout, operator database, provider key,
provider request or model inference was used for this preparation.

## Prepared contracts

- [Pure visual source contract](../../../backend/app/ai/source_judgment_visual.py)
  owns the immutable `visual_source_id_v1` request/parser contract. It accepts
  one to four genuine issued candidates and the current question up to 4,000
  characters, preserving the question and projecting only authorized page text,
  cue provenance and full-page PNG data. It contains no research-script import,
  provider, configuration, database or history access. Four-candidate requests
  retain the frozen public v2 wire semantics; other candidate counts and longer
  questions still require actual release validation.
- Request/response bounds remain 32,768 estimated input tokens, 2,048 output
  tokens, 6 MiB request and 2 KiB verdict. PNG validation requires canonical
  render metadata, correct source/page/hash bindings, safe decoded dimensions,
  at most 1,600 pixels per side, two million pixels and one MiB per PNG.
  Strict local parsing rejects malformed, extra, duplicate or unissued IDs and
  status ambiguity. It displays zero to three qualifying IDs without answers.
- [Backend profile schema](../../../backend/app/schemas/rag.py),
  [profile route](../../../backend/app/routers/rag.py) and
  [frontend types](../../../frontend/src/services/types.ts) add v5 plus
  `source_judge_thinking_level`, `source_judge_transfers_page_images` and
  `source_judge_contract_version`. Current v5 projects `HIGH`, true and
  `visual_source_id_v1`; older v4 metadata retains `LOW`, false and
  `source_id_only_public_v1`. Profiles disclose no credentials.
- [Ask panel](../../../frontend/src/components/rag/AskAiPanel.tsx) compares all
  three new processor fields before submission, requires consistent v5
  metadata and the existing enablement/availability fences, and permits retries
  only for v5 jobs. Older source history stays readable. Inconsistent or paused
  profiles show the paused notice and disable new work.
- [English disclosure](../../../frontend/src/i18n/en.ts) explains that the
  current question, selected published page text and full-page PNG renderings
  may go to Gemini. Earlier chat and original PDF file bytes are excluded;
  only page labels/IDs are returned and no answer is generated. The visual
  retry dialog retains additional-cost confirmation and unknown prior cost.
  Historical text-only disclosure remains available.
- [Root template](../../../.env.example) and
  [Compose](../../../docker-compose.yml) align with the prepared Lite/HIGH,
  32,768/2,048, 60-second, zero-retry and USD 0.30/2.50 per million profile.
  Ask and source-judge enablement defaults remain false. The answer worker
  receives `KNOWLEDGE_PDF_ENCRYPTION_KEY` for bounded original-page rendering;
  its provider credentials remain isolated from other workers/API.
- [Backend image](../../../backend/Dockerfile) installs Poppler and fonts in
  the default runtime independently of OCR. Tesseract remains opt-in through
  `INSTALL_OCR=true`; extraction ownership is unchanged.

## Checks and limits

- Root reported 46 pure-contract synthetic tests passing against the shared
  component. This subagent did not rerun that completed focused suite.
- `tests/test_source_visual_runtime_profile.py` plus the existing root-template
  /Compose default contract: **7 passed**. These use injected settings, fake
  profile reads and literal YAML parsing, with no database or provider.
- `tests/components/askAiFailureCopy.test.tsx`: **25 passed** after fixing the
  paused notice for inconsistent visual metadata. The initial run had three
  failures because disabled controls lacked that notice; the focused rerun
  passed. Tests cover PNG disclosure, old v4 history/fencing, changed processor
  review, cost confirmation and existing stale-access behavior.
- Component and e2e TypeScript checks and scoped ESLint passed. Matching
  [browser fixtures](../../../frontend/e2e/rag-knowledge.spec.ts) and
  [default mock profile](../../../frontend/e2e/support/mockApi.ts) now use v5;
  the browser suite itself was not run by this subagent.
- Scoped `git diff --check` passed. No image build, install, container recreation,
  deployment, schema migration, private-data transfer or Ask activation occurred.

Root owns the coordinated runtime/worker changes, context/index updates and
remaining broad frontend/backend/context checks. Public calibration success
cannot enable the former v4 runtime or substitute for independent private,
original-PDF/access and manual spoken accessibility release evidence.
