# Cardchemy visual guide

Start with [the system map](SYSTEM.md), then choose a workflow below. These
diagrams describe the implemented application. GitHub renders the Mermaid
blocks directly; the surrounding text provides the same essential information.

| What you want to understand | Diagram guide |
| --- | --- |
| Services, deployment, credentials and trust boundaries | [System](SYSTEM.md) |
| Registration, sessions, invitations, recovery and SMTP | [Authentication and email](AUTH-AND-EMAIL.md) |
| PDF upload, Gemini, validated cards and instructor review | [Flashcard generation](FLASHCARD-GENERATION.md) |
| Stored lecture pages, embeddings, revisions and publication | [Subject Knowledge](KNOWLEDGE.md) |
| Ask AI, Gemini source selection, fallback and original PDFs | [Ask AI and lecture browsing](ASK-AI.md) |
| Answers, durable retries, scheduling and progress | [Study](STUDY.md) |
| Data relationships, retention, privacy, health and upgrades | [Data and operations](DATA-AND-OPERATIONS.md) |
| Protected GitHub flow, signed artifacts and deployment | [Release](RELEASE.md) |

## Models and settings at a glance

Model names below are repository defaults or the explicitly dated configuration
observation, not a promise of current provider availability. The configured
model is snapshotted into each job; a worker refuses incompatible snapshots.

| Work | Repository default | Execution and output |
| --- | --- | --- |
| Flashcard text generation | Native Gemini `gemini-3.8-flash`, LOW thinking | Generation worker; summaries and structured cards require local validation |
| Knowledge indexing | Native Gemini `gemini-embedding-001`, 1,536 dimensions | Index worker; canonical document chunks become validated vectors |
| Ask query embedding | The compatible active Knowledge embedding profile | Ask worker; at most one embedding of the unchanged current question |
| Ask source-ID judgment | Native Gemini `gemini-3.5-flash-lite`, HIGH thinking | At most one bounded text/PNG request; only issued-ID/category/cue judgments |
| Published lecture search, PDF viewing, study, OCR | Local application processing | No AI request for these operations |

Optional `gemini-embedding-2` has a separate staged embedding space; matching
dimensions alone do not make it compatible with 001. The closed flashcard
catalog also supports `gemini-3.5-flash-lite`, `gemini-3.5-flash`,
`gemini-3.6-flash` and `gemini-3.7-flash`, subject to model-specific thinking
and token validation. These are supported choices, not automatic fallbacks.
Retired `RAG_AI_*` answer settings remain historical compatibility metadata;
new Ask work does not generate an answer or run a local answer verifier.

On **2026-10-05**, the validated installation selected enabled flashcard
generation with `gemini-3.5-flash-lite`; its selected model differs from the
repository default. Validated root settings and the retained, stopped Ask
worker configuration agreed on Gemini embedding 001 and Gemini 3.5 Flash-Lite
HIGH source judgment, with Ask enabled. This observes configuration, not a
running request or the reason a past job displayed fallback. Fresh
installations keep AI/Ask enablement flags off until explicitly configured
and validated.

Sources: [settings](../../backend/app/config.py),
[root template](../../.env.example), [Compose](../../docker-compose.yml),
[Gemini catalog](../../backend/app/ai/gemini_catalog.py),
[source-judge contract](../../backend/app/ai/source_judgment_visual.py),
[ADR-024](../decisions/ADR-024-gemini-source-id-judge.md).

## Reading the arrows

An arrow labels a request, poll, transfer or dependency; it does not imply
that PostgreSQL pushes jobs to workers. Workers poll durable database queues.
Dashed paths show optional work or an operational boundary. Each workflow
links to its source and longer contract. The full guide index is
[one level up](../README.md).
