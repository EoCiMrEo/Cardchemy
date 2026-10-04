# Cardchemy public roadmap

## Current Lane 6 local result — 2026-10-04

Ask AI is enabled in the retained local installation (verified 2026-10-04). Lane 6 is **7/7 complete** under the accepted
80%-all-displayed-card floor, with public usefulness 94/99 and independent
private twelve-case usefulness 21/24 (87.5%), 12/12 hits. Seed/control,
actual selected-PDF display and final image/profile/health results are recorded
in [the local closure](.agent/logs/2026-10-03/2026-10-03-lane6-final-closure-and-activation.md), alongside every retained physical
failure and unknown charge. New Ask jobs remain source-only v8/visual-v5 on
0033, one current-question embedding/one source-ID judgment maximum and zero
answer/verifier/retries. Fresh installations remain default-off. Lane 7 remains
three unchecked tasks; no hosted CI, protected merge, public release or
production deployment is claimed. Earlier dated updates below are historical.

Current Lane 6 update (2026-10-02): the [restore-verified retained cutover](.agent/logs/2026-10-02/2026-10-02-v7-retained-cutover-and-release-recheck.md)
reached **0032/v7/visual-v3**, preserving populated data, exact PDFs, root
configuration and backups. Matching services are healthy; full offline,
PostgreSQL, frontend/bundle, both RAG journeys, image smoke and isolated
security checks passed. Original PDF pages for Week 2–4 rendered in the
[real browser check](.agent/logs/2026-10-02/2026-10-02-v7-pdf-browser-and-security-verification.md).
The [latest public trial](.agent/logs/2026-10-02/2026-10-02-public-heldout-v10-terminal-result.md)
stopped at 56 evaluated questions/53 valid replies with partial 81/86 useful
cards; complete availability, private displayed usefulness and spoken
assistive-technology remain open. Ask/source judging stay disabled and
**Lane 6 remains 3/7**. Earlier dated snapshots are historical.

Earlier Lane 6 update (2026-10-02): [public v4](.agent/logs/2026-10-02/2026-10-02-public-heldout-v4-terminal-result.md)
stopped at 33 observed questions/30 valid replies despite 42/43 useful partial
cards. Availability and complete quality remain open. A separately approved
[28-call public trial](.agent/logs/2026-10-02/2026-10-02-public-heldout-28-approved-scope.md)
preserves all historical failures/costs. [V7 checkout integration](.agent/logs/2026-10-02/2026-10-02-v7-context-runtime-integration.md)
and source head `0032` add immutable literal-subject admission and matching
worker/profile/disclosure; full frontend/migration checks passed and backend
regressions still need rechecks. Retained v6/0031 stays unchanged; Ask off,
Lane 6 **3/7**. Earlier dated snapshots are historical.

Current Lane 6 update (2026-10-02): twelve fresh query embeddings and the
actual hybrid diagnostic establish **12/12** gold-page candidate recall,
not displayed quality. The [recovered independent signed review](.agent/logs/2026-10-02/2026-10-02-private-v6-independent-review-recovery.md)
covers all 48 candidate slots/44 original PDF pages, with 25 page-useful
and 24 cue-useful Yes labels, the remaining labels No and zero Unsure.
Two follow-up context bindings still need validation before private source
judgment. The [public v3 result](.agent/logs/2026-10-02/2026-10-02-public-heldout-v3-terminal-result.md)
stopped at 21 observed questions/19 valid replies/two inherited failures and
31/32 useful displayed cards because one reviewer Unsure violated its older
stricter frozen gate. All trials remain consumed; neither partial result
establishes the complete release gate. Ask stays disabled and Lane 6 remains
**3/7**, with original PDFs, populated data and root configuration preserved.

Prior Lane 6 update (2026-10-02): the independently prepared public trial
stopped after six requests on availability, with three valid replies and three
provider/network failures. Its [terminal result](.agent/logs/2026-10-02/2026-10-02-visual-public-heldout-terminal-result.md)
is not a complete source-quality pass. A separately versioned transport
successor remains inert pending its own exact envelope; private hybrid/display
and release gates remain open. Ask stays disabled and Lane 6 remains 3/7.

Previous Lane 6 update (2026-10-01): matching visual source-navigation v6,
visual contract v2 and additive migration 0031 are implemented and retained
services are healthy with preserved data/configuration. Complete public
calibration reached 89.32% useful cards; independent heldout/private and
release gates remain open, and Ask stays disabled. See the
[verified cutover](.agent/logs/2026-10-01/2026-10-01-visual-v6-matching-contract-and-backup.md)
and [public result](.agent/logs/2026-10-01/2026-10-01-visual-calibration-v5-independent-result.md).

This page describes implemented capabilities and proposals. It is not a
delivery-date commitment. [Current state](docs/development/CURRENT-STATE.md)
summarizes completed milestones; this page owns current proposals. Completed
engineering trackers are in the [documentation archive](docs/archive/README.md).
[Accepted ADRs](docs/decisions/ADR-000-INDEX.md) explain decisions already made.

## Implemented

- Instructor-owned subjects, invitation-backed student enrollment and revocable
  rotating sessions; instructor provisioning is operator CLI only.
- Bounded PDF upload, optional local OCR, encrypted temporary sources and
  PostgreSQL generation workers with leases, cancellation and manual retry.
- Native Gemini generation through a versioned five-model catalog, strict
  source-grounded four-option cards, quality checks and instructor
  approval/publication. Historical provider identities remain readable.
- Online student study with durable answer receipts, server-derived grading,
  stable per-card displayed-option shuffling and spaced repetition. Progress is
  correct-card coverage; Accuracy, Attempted and Mastery are separate views.
- Transactional password-recovery/invitation email, conservative delivery
  recovery, local Mailpit and encrypted production SMTP configuration.
- Root-only configuration, production-shaped Compose, Alembic schema ownership,
  guarded service/journey tests and mandatory CI/security/accessibility budgets.
- Content-free diagnostics/correlation, worker health, transactional audits,
  authorized operator exports/deletion and bounded metadata retention. Optional
  aggregate reporting remains disabled by default.
- Instructor-owned, revisioned Subject Knowledge with PostgreSQL/pgvector and
  full-text retrieval, isolated Gemini embedding and Ask workers, private
  durable Ask AI history, lifecycle controls and deterministic evaluation/
  recovery gates. The former two-request answer/local-verifier policy is
  historical. The approved new Ask path is source-only, default-off until its
  separate gate: at most one query embedding and exact published Knowledge
  excerpts, with no answer model. Embedding 001 remains default; Embedding 2 is an incompatible,
  explicitly staged/cut-over option. New-document repeats within one Subject offer
  an explicit reuse or separate-copy choice; unchanged explicit revisions avoid
  a second Knowledge capture/index.

## Release work and verification

Phases 0–11 cover the secure self-hosted foundation, branding, governance,
no-quota demo, documentation/screenshots and verifiable release packaging.
Subject Knowledge/RAG Phases 12–21 cover the implemented retrieval, private
Ask AI, privacy, observability and release closure. Their completed task detail
is preserved in the [archived remediation tracker](docs/archive/issues-required-remediation.md)
and [archived RAG implementation plan](<docs/archive/Cardchemy-Subject-Scoped RAG Implementation Plan.md>).
Published artifacts belong to [releases](https://github.com/EoCiMrEo/Cardchemy/releases).

The separate v1.0 readiness gate passed clean-machine production-profile
deployment/recovery, actual local encrypted SMTP delivery/recovery, complete
release evidence and a reported human spoken assistive-technology check. See
[gate evidence](.agent/logs/2026-09-17/2026-09-17-v1-release-gate.md).
The published version remains 0.1.0. Each operator still verifies provider
quality, external SMTP/DNS/mailbox delivery and their own hosting/recovery goals.

## Product quality remediation and future proposals

The [product quality remediation plan](docs/development/PRODUCT-QUALITY-REMEDIATION-PLAN.md)
records the approved Gemini-only, Study, embedding-profile and repeat-Knowledge
decisions. Lanes 0–5 are implemented in this checkout: new text work uses the
verified Gemini catalog, Study distinguishes correct coverage from attempts,
repeat Knowledge upload has an owner choice, Embedding 2 is isolated from 001,
and Ask previously had the two-request/local-support policy. Default-off configuration and
deployment-specific provider, space, price, privacy and release
checks still govern actual enablement. These source changes are not a published
release.

The operator approved Lane 6 on 2026-09-25 to investigate and remediate current
Ask provider failures, published-Knowledge answerability and insufficient
grounded flashcard yield. Implementation is under verification in this checkout;
no Lane 6 release gate has been declared complete. The former cross-stack
integration lane is Lane 7. The exact requested card count and explicit
smaller-target choice over temporarily staged, fully validated candidates are
implemented and under release verification. The accepted
[original-PDF source navigation decision](docs/decisions/ADR-023-original-pdf-source-navigation.md)
supersedes the source-sufficiency and extracted-page-only parts of ADR-022:
new Ask jobs use exact, unverified Related published Knowledge references
with up to one query embedding and no answer generation or verifier. The
retained local database reached `20261001_0030` after a restore-verified
backup, with three exact original PDFs attached and matching services
healthy. Dormant v5 `visual_source_id_v1` is integrated behind the closed
Ask fence. It can send the current question, bounded published page text/cues
and rendered full-page PNGs for at most one source-ID judgment; it generates
no answer. The application currently caps output at 2,048 tokens. A separate
4,096-token public continuation is prepared but has made no new provider
call or quality pass. The prospective release floor is **80% useful among
every displayed card** and at least **10/12 ordinary no-match cases**;
fabricated, unauthorized, stale and wrong-page references remain disallowed.
Public calibration, different-PDF holdout, private release and accessibility
gates remain open. Ask stays disabled at Lane 6 **3/7**. See
[current state](docs/development/CURRENT-STATE.md).

The following paragraphs preserve the earlier public-pilot chronology. At
the 2026-09-29 checkpoint, the retained local database was at
`20260928_0029`, with three exact original PDFs attached and matching
services healthy. The prospective v4 source-ID judge was implemented behind
the closed Ask fence. Its early public attempts produced
no quality score: three Gemini 3.8 one-request stops, a Gemini 3.6 sandbox
transport stop, three valid 3.6 calibration calls followed by HTTP 503, and
a separately approved checkpointed continuation that received HTTP 503 twice
on the same unresolved group. The latter accepted no new group and left
heldout unopened. Those availability stops did not grade source usefulness.
Students can browse published
lectures and open the original PDF in the app; Ask remains disabled behind its
independent source-usefulness and release gates. The operator selected at
least 90% usefulness across all displayed citation cards as the independent
release target **at that time**; the prospective 80% floor above supersedes
this without regrading those pilots. Source/authenticity/access failures
remain disallowed.
One separately approved public-only Gemini 3.6 inline Batch pilot targeted
45 unresolved calibration groups, then 48 public heldout groups only if the
complete calibration passed. Its keyless harness was verified, but the single
public creation POST returned HTTP 400 without a job name or
quality score; the approval is consumed, actual cost is unknown, and the
exact rejection reason remains unverified. Ask remains off.

The operator subsequently approved one new synchronous, public-only
Gemini 3.5 Flash-Lite pilot on Free tier. Its 48-case calibration and
conditional 48-case different-PDF heldout use a distinct one-use envelope
and score; the operator has supplied the dedicated judge key and the exact
zero-call approval-aware preflight passed. The calibration then accepted
10 safe receipts before its eleventh physical request timed out at 30.006
seconds; the no-retry pilot stopped, its approval is consumed, full
calibration had no complete score at that point, and heldout remained unopened.
The consumed
Batch claim is not replayed, and this public experiment does not
authorize a private Knowledge transfer, select the application model, or
close the four remaining Lane 6 gates. Ask remains disabled.
The owner approved counting the timed-out eleventh Flash-Lite group as a
failed case without replay. A separately authorized continuation then made
37 accepted public calls for groups 12–48. Across the full 48-case
calibration, 47/48 responses were valid, useful-page hit@3 was 35/36 and
54/55 displayed cue-plus-original-PDF cards were useful. One of twelve
completed no-useful groups nevertheless displayed a page. This fails the
unchanged zero-false-display gate; the different-PDF heldout remains sealed,
the one-use authorization is consumed, and Ask stays disabled at **3/7**.
The approved next step is an offline, versioned
`public_exhaustive_page_and_cue_v2` ID-only prototype that judges each page
and visible cue independently, selects every qualifying page up to three or
none, and generates no answer. A new disjoint public PDF calibration and
different-PDF heldout need independent page-and-cue review before another
frozen evaluation. The existing availability, useful-hit, cardinality,
≥90%-all-displayed and zero-false-no-useful gates remain. Corpus acquisition,
paid calls, private Knowledge transfer, versioned runtime selection and Ask
activation retain separate approval and evidence gates.

The separately approved expanded public Flash-Lite pilot then received 66/66
valid calibration responses. It placed a useful original-PDF page in 53/54
positive groups and 81/84 displayed page-and-cue cards were useful, but one
no-useful group displayed a page and multi-page selection failed its frozen
cardinality thresholds. The 60 different-PDF heldout groups remain sealed;
Ask remains off at Lane 6 **3/7**. The later per-page Boolean prototype
received 65/66 valid public calibration responses. It showed 63/63 useful
cards and zero pages on all 12 no-useful cases, but selected the exact useful
set in only 4/17 two-page and 3/16 three-page cases, with 0/2 four-page
overflow. That gate also failed; the 60 different-PDF heldout remains sealed.
A stronger-model same-wire comparison is a proposal, not an approved result.
Private Knowledge transfer, a matching runtime version and Ask activation
still require separate approval and evidence. See
[ADR-024](docs/decisions/ADR-024-gemini-source-id-judge.md).

The subsequent same-wire public Gemini 3.5 Flash comparison stopped after
three HTTP 503 responses in ten calibration calls. It has no complete
quality score or heldout result; its one-use ledger is consumed. Ask remains
off, and another paid attempt needs a newly approved bounded plan.

The approved public offline ranker audit and the published-source development
retrieval measurements have not met that release target. See
[current state](docs/development/CURRENT-STATE.md) and the
[Lane 6 plan](docs/development/PRODUCT-QUALITY-REMEDIATION-PLAN.md) for
the exact open items and evidence boundaries.

Native mobile clients, another UI language, offline study/PWA/conflict handling,
quiz/rewards features, a broker/Redis/Celery layer and broader
multi-tenant/distributed governance have **no accepted implementation or
delivery commitment**. Evaluate a concrete user need, privacy/data design,
operating costs and compatibility before accepting any proposal.

The [documentation archive](docs/archive/README.md) contains the completed phase
trackers and early brainstorming, including superseded tooling and affiliation
claims. Cardchemy is a standalone project. Discuss new work in a feature issue;
do not treat archived prose as current instructions or a new architecture change.
