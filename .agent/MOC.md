# `.agent/` Map of Contents

Last Updated: 2026-09-14

## Purpose

This file is the **high-level navigation map** for Cardchemy's `.agent/` workspace.

`.agent/` stores long-lived supporting evidence and agent-visible development history. It is not the canonical source of truth for current product requirements, architecture, ADRs, or source-tree navigation.

For governance, storage rules, naming, and source-of-truth boundaries, read [`README.md`](README.md).

---

## High-Level Map

| Area | Path | Responsibility |
|---|---|---|
| Workspace governance | [`README.md`](README.md) | Defines what belongs in `.agent/`, what does not, source-of-truth boundaries, naming, and maintenance rules. |
| Workspace map | [`MOC.md`](MOC.md) | High-level navigation for `.agent/`. |
| Development history | [`logs/`](logs/) | Dated implementation, remediation, investigation, handoff, and verification evidence. Use the local log index rather than listing individual logs here. |

This file should remain high-level even when `.agent/` becomes large.

Do **not** add every log, investigation, report, or generated artifact directly to this root MOC.

---

## Navigation Model

The `.agent/` workspace should use hierarchical maps as it grows:

```text
.agent/
├── README.md
├── MOC.md
│
├── logs/
│   ├── README.md
│   ├── MOC.md                 # optional once logs become large
│   ├── 2026/
│   │   ├── MOC.md
│   │   ├── 09/
│   │   │   ├── MOC.md
│   │   │   └── <dated logs>
│   │   └── 10/
│   │       ├── MOC.md
│   │       └── <dated logs>
│   └── ...
│
├── investigations/            # create only if recurring long-lived use appears
│   └── MOC.md
│
├── reports/                   # create only if recurring long-lived use appears
│   └── MOC.md
│
└── <future durable areas>/
    └── MOC.md
```

The exact subdirectories should be created only when the repository actually needs them.

The rule is:

> Root MOC maps durable areas. Area-level MOCs map subareas. Monthly or similarly scoped MOCs map individual artifacts.

This keeps navigation useful without turning one file into a giant index.

---

## Current Area: `logs/`

[`logs/`](logs/) is currently the only durable artifact area under `.agent/`.

It records historical implementation and verification evidence such as:

- remediation phases;
- major implementation work;
- investigations;
- regression analysis;
- verification results;
- important handoff context.

Use [`logs/README.md`](logs/README.md) as the current local index.

As log volume grows, do not keep expanding one flat index forever. Split navigation by time:

```text
.agent/logs/
├── README.md
├── MOC.md
├── 2026/
│   ├── MOC.md
│   ├── 09/
│   │   ├── MOC.md
│   │   └── ...
│   └── 10/
│       ├── MOC.md
│       └── ...
```

### Recommended responsibilities

- `logs/README.md` — explains what logs are, rules for writing them, and how the log archive is organized.
- `logs/MOC.md` — maps years or major log groups once the archive is large enough.
- `logs/YYYY/MOC.md` — maps months within a year.
- `logs/YYYY/MM/MOC.md` — indexes individual logs for that month.
- individual log files — preserve the actual historical evidence.

This pattern scales to hundreds or thousands of logs without making `.agent/MOC.md` expensive to read.

---

## Navigation by Intent

### I am starting a normal implementation task

Do **not** recursively read `.agent/`.

Follow the canonical project context path:

```text
AGENTS.md
→ docs/00-START-HERE.md
→ PROJECT-MAP.md
→ relevant architecture / ADR / module MOC
→ relevant source files
```

Read `.agent/` only when prior implementation history is directly useful.

### I need to understand why previous work was implemented a certain way

Go to the relevant durable area, normally:

```text
.agent/MOC.md
→ logs/
→ relevant year/month MOC or local index
→ relevant log
→ current canonical docs/code for verification
```

Historical evidence can explain why a decision or implementation existed at that time, but current documentation and source code remain authoritative.

### I need verification evidence from an earlier phase

Start with the log archive index, narrow by date or phase, then verify any still-important claim against the current repository.

### I am adding a new agent artifact

First decide whether it is durable.

If it is temporary, keep it local and uncommitted.

If it is durable:

1. place it in the appropriate `.agent/` area;
2. update the nearest local MOC/index;
3. update `.agent/MOC.md` only if a new durable **area** was added or an area's responsibility changed.

---

## Current Repository Context Relationships

`.agent/` should complement, not duplicate, the repository context system.

Current or planned canonical context includes:

| Context | Responsibility |
|---|---|
| `AGENTS.md` | AI operating rules and reading order. |
| `docs/00-START-HERE.md` | Project orientation and high-level current truth. |
| `PROJECT-MAP.md` | High-level source navigation. |
| `backend/MOC.md` | Backend navigation. |
| `frontend/MOC.md` | Frontend navigation. |
| `docs/architecture/` | Current cross-cutting system architecture. |
| `docs/decisions/` | Accepted durable architectural/product decisions. |
| `docs/development/CURRENT-STATE.md` | Current development phase and near-term state. |
| `.agent/` | Historical implementation and verification evidence. |

If `.agent/` conflicts with current canonical documentation or code, verify the current implementation rather than treating the historical artifact as authoritative.

---

## Expansion Rules

Create a new `.agent/` area only when all of the following are true:

1. the artifact type is expected to recur;
2. it has long-term value across sessions or team members;
3. it does not belong in canonical project documentation;
4. its responsibility is distinct from existing areas.

Examples that may eventually justify their own areas:

```text
investigations/
reports/
verification/
handoffs/
```

Do not create these folders preemptively.

When an area becomes large, add hierarchical MOCs rather than expanding the root map with individual files.

---

## Maintenance Rule

The root `.agent/MOC.md` changes only when the **workspace structure or area responsibilities** change.

Individual logs or artifacts should normally update only their nearest local index.

Example:

```text
New Phase 5 log added
→ update .agent/logs/2026/09/MOC.md
→ do NOT update .agent/MOC.md
```

New durable area added:

```text
.agent/investigations/
→ create investigations/MOC.md
→ update .agent/MOC.md
```

This separation keeps the root map stable, cheap to read, and useful for both developers and AI agents.
