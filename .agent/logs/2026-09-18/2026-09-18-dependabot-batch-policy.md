# Dependabot batch policy

Date: 2026-09-18

## Scope and evidence

After the approved RAG feature and original dependency queue merged, Dependabot
immediately opened PRs #26-#32. Five simultaneous npm PRs consumed the configured
limit. Several were independent major upgrades (Python 3.14, TypeScript 7,
Node 26 types, jsdom 30 and globals 17); the TypeScript PR failed the required
frontend, journey, dependency-audit and frontend-image checks. Python 3.14 and
Node 26 also exceed the supported runtimes in `docs/RUNTIMES.md`. The operator
asked to close the current queue and prevent unnecessary PRs, while retaining
new PRs for deliberate features or batch updates.

## Change

Each Dependabot ecosystem now checks monthly and permits one open routine
version-update PR. Npm, pip and Docker minor/patch updates are grouped by
ecosystem; Actions updates remain one group. Major npm, pip and Docker version
updates are ignored across dependencies. Python's Docker tags use the language
major as the tag's SemVer minor, so an explicit `>=3.12` ignore keeps the image
on the reviewed 3.11 line. Dependabot's update-type ignore applies to version
updates, so npm/pip/Actions security groups remain eligible. Major runtime or
toolchain work must be initiated as a deliberate, reviewed upgrade rather than
a stream of independent bot proposals. Future pip batches still require the
repository's Windows lock generator before merge.

The seven pre-existing bot PRs are closed separately after this policy reaches
protected main, preventing freed PR slots from producing another unnecessary
queue under the old rules. No dependency, lockfile, runtime, application code,
provider configuration, database, volume or secret changes are included.

## Verification

The repository context, CI workflow/protection contracts, YAML syntax and exact
diff are checked locally. GitHub's Dependabot configuration validator and the
complete hosted current-base gate must pass before protected merge. The live
open-PR list is checked again after closing #26-#32.
