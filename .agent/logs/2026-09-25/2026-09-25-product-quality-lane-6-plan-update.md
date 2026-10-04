# Product quality Lane 6 plan update

Date: 2026-09-25. Scope: approved documentation plan update only. Starting
branch `main`, HEAD `6c02d6cf063acf83f4da5c08cfc4a3aa2c94be57`. The
checkout already had substantial uncommitted Lanes 0–5 work and an untracked
product-quality plan; all pre-existing work was preserved.

## Starting context and decision

Read root `AGENTS.md`, Start Here, project/backend maps, current state,
roadmap, the product-quality plan, relevant architecture and ADRs, and the
September 17, 21, 22, 23 and 25 quality/RAG logs. The
[same-day investigation](2026-09-25-ask-generation-quality-investigation.md)
records the local Ask provider failures, support abstentions, retrieval limits,
and insufficient-card generation case with their evidence limits. A bounded
read-only subagent reviewed the proposed lane against current contracts.

The operator approved adding a remediation lane before the existing Lane 6.
The approved user-visible generation choice keeps the requested count exact:
when a bounded attempt cannot meet it, retain fully validated candidates
temporarily, report the observed valid count, and require explicit confirmation
of a smaller target no greater than that count before creating any set. The
count is an observed lower bound, not a proof of document capacity. No new
provider call follows that smaller-target confirmation.

## Documentation changes and rationale

- `docs/development/PRODUCT-QUALITY-REMEDIATION-PLAN.md`: adds dated
  post-Lane-5 findings without rewriting historical starting findings;
  records the approved exact-count decision; inserts pending Lane 6 for safe
  diagnostics, reviewed private source-backed evaluation, measured retrieval
  and local-support changes, adaptive generation, bounded private candidate
  staging and release gates. Renumbers the existing integration/rollout lane
  to Lane 7. The staging design must receive a new numbered ADR extending
  ADR-006/008 before runtime work, and a new migration if the durable schema
  changes.
- `docs/development/CURRENT-STATE.md` and `ROADMAP.md`: distinguish completed
  Lanes 0–5 from approved but pending Lanes 6–7. Do not present a plan edit as
  a shipped fix.
- `.agent/logs/README.md`: indexes this approval and plan change separately
  from the preceding read-only investigation.

## Preservation and limits

No runtime code, migration, ADR, root `.env`, database state, container, volume
or private content was changed for this plan update. No paid provider call or
live evaluation was made. Current cases still do not establish the precise
provider subreason, whether each discarded Ask answer was correctly supported,
or whether the Week 3 source contains 20 distinct testable facts. Later
implementation must preserve Ask's one embedding plus one answer and zero
automatic retries; independently authorized live spending remains required.

## Checks and cleanup

- `python scripts/check_context.py`: passed; 37 required files, 74 active
  guides and 1,096 local links validated.
- `git -c core.safecrlf=false diff --check -- ROADMAP.md
  docs/development/CURRENT-STATE.md .agent/logs/README.md`: passed.
- Trailing-whitespace scan of the untracked plan and this new log: passed.
- No runtime/backend/frontend, disposable-database, hosted, browser or paid
  provider test was run for this documentation-only change; the earlier
  investigation's offline checks are recorded in its own log.
- No temporary resources were created.
