# V4 private candidate-recall diagnostic preparation

Date: 2026-09-29 (America/Chicago). Branch `main` at `6c02d6c`. This is a read-only, keyless diagnostic for the exposed eleven-case published-lecture regression under accepted [ADR-024](../../../docs/decisions/ADR-024-gemini-source-id-judge.md). The working tree, populated database, root `.env`, original PDFs and disabled Ask installation were preserved. No provider request, private text egress or retained database write occurred in preparation.

## Diagnostic contract

`backend/scripts/diagnose_source_judge_v4_candidates.py` pins the already reviewed roster and precomputed current-question vector packet by their recorded SHA-256 digests. It defaults to a no-database preflight. Execution requires an explicit principal, Subject, corpus revision, embedding space and optional selected documents; all input/output paths must stay under the isolated `/private` operating-system Temp mount. It refuses AI credentials, Ask enablement, non-development or non-Compose database targets, changed files, scope drift and missing current reviewed gold pages.

Each case runs the current v9 authorized hybrid retrieval and the actual worker `_v4_candidate_pool` using its precomputed vector, inside a repeatable-read read-only transaction. It compares the designated reviewed gold physical page to the pages inspected (up to twelve) and the pages sent to the judge (up to four). It makes no embedding, source-judgment, answer or verifier request, opens no Ask job, and stores only content-free aggregate counts in an exclusive private Temp output. Standard output contains the same safe aggregates or a fixed failure code. The v4 slate does not yet have independently reviewed usefulness labels for every exact page, so any-useful-page hit is explicitly **ungraded**; keyword overlap is never counted as usefulness.

## Verification and remaining measurement

- Synthetic diagnostic, source-judgment worker and prior private-navigation probe tests: **54 passed**.
- Default CLI preflight, strict read-only transaction ordering, scope/gold drift refusal, inspected-versus-sent designated gold hits, no-content aggregate, credential/target refusal, exclusive output and rollback/close behavior were exercised with fake data.
- The retained eleven-case diagnostic has **not yet been executed** in this slice. It requires the existing private Temp packet/roster, a scoped one-off container without AI credentials, and explicit current principal/Subject/revision/space inputs. The fresh two-PDF holdout remains untouched. This diagnostic alone cannot establish source usefulness, judge quality or the Ask release gate.
