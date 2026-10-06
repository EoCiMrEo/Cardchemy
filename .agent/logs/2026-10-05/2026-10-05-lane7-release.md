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
- Context: **46 required files, 94 active guides, 1,680 local links** validated
  on the release source; closure documentation receives a final link check.
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

- [PR 44](https://github.com/EoCiMrEo/Cardchemy/pull/44) merged normally, preserving
  required protection and history. Reviewed branch head:
  `6b251072ec0b92ac885c3aa7a4c62b3f80045294`; released merged source:
  `7f326e833c586d7008b18daf85d3a425623d3e72`.
- Exact-head [PR CI](https://github.com/EoCiMrEo/Cardchemy/actions/runs/37395611138)
  and exact merged-main [push CI](https://github.com/EoCiMrEo/Cardchemy/actions/runs/37395995321)
  both passed, including `ci-required`. Fresh pre/post-merge reads confirmed
  strict current-base protection matches the repository definition; no unresolved
  review threads, force-push, administrator bypass or protection change.
- Full Git history secret scan before push: **101 commits, zero leaks**.
- Existing Dependabot PRs **38, 42 and 43** were closed at the operator's request;
  their dependency upgrades were not incorporated into the working release.
- [Signed release workflow](https://github.com/EoCiMrEo/Cardchemy/actions/runs/37396275822),
  attempt 1, completed successfully. All three Linux/amd64 runtimes passed builds,
  smoke, dependency and HIGH/CRITICAL vulnerability gates including unfixed
  findings; complete SBOM/inventory artifacts were signed.
- Independently downloaded all **17** draft attachments. Verified Cosign **3.1.3**
  binary SHA256 `9fe59be0eca1271873ce019061335eb1ac419b7059202e797828467ddabe33be`
  against previously verified official provenance. Verified checksum signature,
  all 15 checksummed files, source tar/PAX commit, package/audit/SBOM/image/run
  bindings and the annotated remote `v0.2.0` target/hash.
- Signed checksum-manifest SHA256:
  `f3273adf49089622a0c46f82eef31810b3667323018ee8a3f72b8e96226991ed`.
  Exact signing identity:
  `https://github.com/EoCiMrEo/Cardchemy/.github/workflows/release-sbom.yml@refs/heads/main`;
  issuer `https://token.actions.githubusercontent.com`; every verification bound
  the independently reviewed source SHA and retained transparency verification.
- All three image digests pulled anonymously using a new empty Docker config;
  their exact-source signatures and unique remote tag/manifest bindings passed.
  Temporary Docker configs were removed.
- Published the existing verified draft, ID **404204618**, on
  **2026-10-06T01:02:11Z** (2026-10-05 operator-local):
  [public v0.2.0](https://github.com/EoCiMrEo/Cardchemy/releases/tag/v0.2.0).
  Before publishing, the exact release ID, 17 asset IDs/names/sizes and all bytes
  were revalidated. After publication, independently downloaded all **17** assets
  anonymously into another empty directory and repeated signature/package/tag
  checks successfully. No artifact or tag was overwritten.

| Runtime | Verified immutable manifest digest |
| --- | --- |
| `ghcr.io/eocimreo/cardchemy-backend` | `sha256:a6c88bb297c166a1babc0bb87a9392b8e73cd5a04eb2325ca5c7ac1e1c4905f3` |
| `ghcr.io/eocimreo/cardchemy-backend-ocr` | `sha256:bb15f8dbee7a9ee6f87fbb52fd3e0c3e1301551c31534422e36cbfe487b34c41` |
| `ghcr.io/eocimreo/cardchemy-frontend` | `sha256:aec2f7d7003745b188d3a18a7660288e83536f0daf376449f35e646ddd50e1f0` |

## Verification failures, boundaries and closure

The draft tag lookup endpoint returned HTTP 404 despite the successful workflow.
Authenticated release listing identified the unique existing draft; lookup and
download by release ID worked. No workflow rerun, second draft or new tag was
used to repair this read-only lookup.

An exact GitHub fresh clone of the reviewed source passed all eight healthy
services, migration exit zero, current head/no drift and SPA/API readiness.
Its optional synthetic login helper incorrectly sent JSON to the OAuth form
endpoint, then cleaned its owned resources before reaching the final postboot
hash assertion. This fixture failure is preserved separately; it is not an
application failure or a complete journey pass.

The bounded **core-only repeat passed all eight checks**, with no failures:
fresh actual GitHub clone at the reviewed release commit, normal root bootstrap,
base `docker compose up -d --build --wait` exit zero, eight healthy services and
migration exit zero, Alembic `20261002_0033`/current heads/no drift, SPA/edge/API
readiness, and clean Git/source bytes both before and after boot. All **944**
tracked files retained identical bytes; source-manifest SHA256
`ac81717ad303557b290e4beefb59c84f54d3a13f40a2fccb9e74eae8a843d786`.
No source edit or component `.env` was needed. Worker AI flags stayed default-off;
zero provider calls. Build/up/wait completed in 46.23 seconds with local build
cache; this timing is not a general installation estimate.

Owned disposable containers/network/two volumes/three absent-before image tags,
clone/generated credentials and one-use helpers were removed. The real root
`.env`, nine retained stopped containers, 286 baseline volumes and baseline
images were preserved. The original mixed fixture-failure receipt remains
unchanged alongside the distinct successful core-only receipt. Downloaded signed
release assets and content-free receipts remain ignored operator records;
credentials were neither written nor included in Git/release attachments.

All approved plans are completed and archived; Lane 7's operator-defined cleanup,
documentation/diagrams and protected signed-publication scope is **3/3 complete**.
The post-publication documentation records actual outcomes without replacing the
immutable signed release source/tag. Future roadmap proposals are not active
approved implementation plans. No production-server deployment, new paid AI
evaluation or new measured screen-reader pass is claimed.
