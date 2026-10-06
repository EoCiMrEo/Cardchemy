# Lane 7: final documentation, architecture and 0.2.0 release

Date: 2026-10-05 (operator-local date).

## Authority and starting context

The operator defined the final Lane 7 as repository cleanup, current release
documentation/diagrams, and GitHub rollout with publication of version 0.2.0.
All earlier approved phase and product-quality work is complete. The operator
authorized publishing the complete current changes and closing existing PRs;
they explicitly requested no change to the working AI behavior.

Starting branch: `codex/repository-cleanup`; starting main/HEAD:
`61b34ebda127b712bf22e36f84fb393f1343f707`. Pre-existing cleanup changes were
preserved. The source-grounded orientation included root instructions, Start
Here, project/module maps, current state, accepted ADR-023/024, AI/configuration,
testing and release guides, and relevant dated closure/publication logs.
Independent bounded agents reviewed Ask architecture, prepared diagrams and
reconciled milestone documents.

The prior [cleanup record](../2026-10-04/2026-10-04-repository-cleanup.md)
contains deletion/consumer rationale, native and clean-Linux offline suites,
disposable PostgreSQL/Mailpit, frontend, deterministic journeys, image/security
checks and an exact-source fresh-clone Compose boot with eight healthy services.
Those results are local/disposable evidence, not hosted CI or paid-provider proof.

## Changes and preserved behavior

- Nine visual guides in `docs/diagrams/` cover system boundaries, auth/email,
  generation, Knowledge, Ask, study, data/operations and release. Diagrams cite
  implemented source and distinguish repository defaults from dated installation
  configuration, local fallback and remote work.
- README, orientation, roadmap/current state, module maps and guide navigation
  describe the completed architecture. Completed plans stay archived; archive
  banners explicitly record the operator's final Lane 7 definition rather than
  changing historical checklist bodies.
- Version metadata, package/lock metadata, Compose default, configuration default,
  CI/release checks and supported release examples align to 0.2.0. The changelog
  gathers shipped product-quality work, cleanup and visual documentation.
- Corrected stale active Knowledge/privacy and frontend policy descriptions to
  v8/visual-v5/admission-v2 with bounded original-page text/PNGs and the eligible
  admitted literal preceding subject. These are documentation corrections.
- No AI policy, provider/model setting, retry behavior or application flow was
  changed for this release work. The actual operator root `.env`, retained data,
  volumes and all existing migrations remain preserved.

## Ask AI observation

Read-only validated root settings and stopped retained worker configuration agree:
Ask is enabled; query embeddings use Gemini `gemini-embedding-001` (1,536
dimensions), and source-ID judgment uses Gemini `gemini-3.5-flash-lite`, HIGH
thinking, visual-v5, zero retries. Flashcard generation is enabled and configured
to use `gemini-3.5-flash-lite`; the repository default remains `gemini-3.8-flash`.
Disabled retired `RAG_AI_PROVIDER_ENABLED` means no old answer-model execution;
it does not disable embedding or source judgment.

Ask performs at most one current-question embedding, authorized local SQL
retrieval, and at most one bounded source-ID judgment when candidates exist.
It returns up to three exact original-PDF references and makes no answer/verifier
call. Eligible transient embedding failures permit local lexical retrieval;
candidate source judgment still uses Gemini. Published lecture browsing/search
is an independent local path. No database/private job contents were inspected,
so this observation does not identify the search mode of the most recent Ask job.
All retained services were stopped during inspection. Zero paid calls were made.

## Operator functional report and accessibility waiver

On 2026-10-05, the operator reported testing the full app, including Ask AI,
flashcard generation and student invitations, with all flows working well.
They explicitly waived the repeated packaged spoken-output/screen-reader check
for this unchanged-UI 0.2.0 release. This is a release-specific operator waiver,
**not a newly measured screen-reader pass**. Automated frontend/accessibility
results and older Lane 6 operator reports remain separately labeled.

## Local release validation

- Release metadata 0.2.0: passed.
- CI workflow/protection/budget validation: passed (four workflows).
- Release/configuration/operations/AI-migration contracts: **287 passed**;
  offline, no live-provider opt-in.
- Context: **46 required files, 94 active guides, 1,679 local links** validated.
- Canonical license/brand notices and current-change whitespace: passed.
- All **19 Mermaid blocks** parsed/rendered with exact Mermaid 12.1.0 in local
  Chromium, external browser networking blocked; zero browser errors. Independent
  visual review corrected clarification arrows and the local Mailpit boundary.
- External publication evidence is recorded below once completed; local checks
  alone do not establish publication.

The local Python launcher emitted a stale installation-location warning while
returning successful test/check results. Clean supported Python/runtime results
are separately available in the cleanup record and hosted CI.

## GitHub rollout and signed release

Pending actual protected PR/main CI, signed draft/package/image verification and
public release. No deployment to a production server is claimed.
