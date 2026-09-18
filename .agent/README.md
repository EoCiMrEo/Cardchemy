# `.agent/` Workspace

Last Updated: 2026-09-14

## Purpose

`.agent/` is Cardchemy's durable workspace for AI-agent supporting material.

It exists to preserve useful implementation history, verification evidence, and other agent-generated artifacts that may help future AI sessions or developers understand **what happened during previous work** without depending on chat history.

This directory is **supporting evidence, not the canonical source of truth** for product behavior, architecture, requirements, or repository navigation.

## Source-of-Truth Boundary

Use the repository context system in this order:

1. `AGENTS.md` — operating rules for AI agents.
2. `docs/00-START-HERE.md` — project orientation and current high-level truth.
3. `PROJECT-MAP.md` and module MOCs — repository navigation.
4. `docs/architecture/` and `docs/decisions/` — current architecture and accepted durable decisions.
5. Source code, migrations, schemas, configuration, and tests — current implementation truth.
6. `.agent/` — historical implementation and verification evidence.

If an `.agent/` artifact conflicts with current documentation or code, **do not treat the artifact as authoritative**. Verify the current implementation and update the canonical documentation if a real inconsistency exists.

## What Belongs Here

Commit material that remains useful across AI sessions or developer handoffs, such as:

- dated implementation/remediation logs;
- verification and test evidence summaries;
- important investigation findings tied to a completed body of work;
- concise handoff evidence explaining what changed, why, and how it was validated;
- future agent-support artifacts that are useful long-term but are not canonical architecture or product documentation.

The current durable content is under [`logs/`](logs/).

## What Does Not Belong Here

Do not store:

- passwords, API keys, tokens, secrets, private environment values, or credentials;
- user data or sensitive application data;
- canonical product requirements;
- canonical architecture or ADRs;
- duplicated copies of `README.md`, `PROJECT-MAP.md`, architecture docs, or source documentation;
- dependency caches, build output, database dumps, large binaries, or generated artifacts that can be reproduced;
- raw chain-of-thought, private model reasoning, or unreviewed conversational transcripts;
- temporary scratch files that have no value after the task ends.

Temporary agent work should remain local and uncommitted, or live in an explicitly ignored temporary directory.

## Artifact Standard

A committed agent artifact should be useful to someone who did not participate in the original work.

For substantial logs, include when relevant:

- date;
- scope;
- decisions that were already approved before implementation;
- implementation summary;
- affected areas or paths;
- verification performed;
- known limitations, deferred work, or follow-up;
- repository revision/branch context when it materially helps reproduce the work.

Do not copy large sections of source code into logs. Link to repository paths instead.

## Naming Convention

Prefer:

```text
YYYY-MM-DD-<scope>-<kind>.md
```

Examples:

```text
2026-09-14-phase-2-remediation.md
2026-09-20-pdf-job-verification.md
2026-10-02-auth-regression-investigation.md
```

Use lowercase kebab-case after the date.

## Logs

`.agent/logs/` records durable development history: what changed, why the work was needed, problems encountered, important decisions applied, and how the result was verified.

Rules for logs:

- keep historical logs historically accurate;
- do not rewrite an old log merely because the current system later changed;
- factual corrections are allowed, but material supersession should be stated explicitly;
- add new work as a new dated log when it represents a distinct phase or substantial change;
- keep `.agent/logs/README.md` updated as the log index.

## Maintenance

Whenever `.agent/` gains, removes, or materially changes a durable artifact:

1. Update [`MOC.md`](MOC.md).
2. Update the relevant local index, such as `logs/README.md`.
3. Confirm the artifact does not duplicate canonical project documentation.
4. Remove or ignore temporary material that no longer has long-term value.

If `.agent/` later grows additional durable areas, create a new subdirectory only when it has a clear responsibility. Add that directory to `MOC.md` and give it a local `README.md` when its purpose or rules are not obvious.

## For AI Agents

Do **not** begin a normal coding task by recursively reading `.agent/`.

First read the canonical project context defined by root `AGENTS.md`. Read `.agent/` only when historical evidence is useful—for example, when investigating why a previous remediation was implemented, reproducing verification, or understanding a past failure.

The goal of `.agent/` is to reduce repeated investigation, not to become another documentation tree that every session must load.
