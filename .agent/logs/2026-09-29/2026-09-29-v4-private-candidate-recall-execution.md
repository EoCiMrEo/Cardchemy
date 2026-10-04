# V4 private candidate-recall diagnostic execution

Date: 2026-09-29 (America/Chicago). Branch `main` at `6c02d6c`. This is the one-off, keyless execution of the [prepared diagnostic](2026-09-29-v4-private-candidate-recall-diagnostic.md) under [ADR-024](../../../docs/decisions/ADR-024-gemini-source-id-judge.md). The broad pre-existing working tree, retained database and volume, root `.env`, published Knowledge and original PDFs were preserved. Ask admission remained disabled.

## Frozen inputs and execution boundary

- The existing eleven-case exposed, owner-reviewed published-source roster matched SHA-256 `fca9588c20997424e716a726beac7a64db7bdde1036b18734db28ca4c8cdd730`. Its previously paid, precomputed current-question vector packet matched SHA-256 `7633a5a48c28386ec99fe72f24736f72a4b204413956fc2bb8ac1443f3e9ae47`. The packet was reused; no new embedding was requested.
- The newly built `cardchemy-backend:0.1.0` image matched the checkout hashes for the v4 worker, local-query resolver and authorized retriever. A separate one-off base-Compose backend container had the existing private operating-system Temp inputs at `/private`, no repository mount, no AI credential and no dependent service startup. The diagnostic's no-database preflight returned `preflight_unexecuted` with zero provider/database activity.
- Execution used the already scoped private principal/Subject/revision/space record, checked the frozen input bytes, current authorized gold pages and scope, and ran the actual v9 hybrid retrieval plus `_v4_candidate_pool`. Each case began a repeatable-read **read-only** transaction and rolled back. The output was an exclusive aggregate-only Temp file; no identifiers, questions, source text, vectors or raw observations were emitted. The one-off container was stopped and removed after the result was saved.

## Aggregate result

| Group | Cases resolved | Designated gold in SQL | Gold among inspected pages | Gold among up to four sent candidates | Pages inspected | Pages sent |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Direct | 6/6 | 6/6 | 6/6 | 6/6 | 72 | 24 |
| Paraphrase | 4/4 | 4/4 | 4/4 | 4/4 | 48 | 16 |
| Follow-up | 1/1 | 1/1 | 1/1 | 1/1 | 12 | 4 |
| **Total** | **11/11** | **11/11** | **11/11** | **11/11** | **132** | **44** |

The aggregate-only output is 1,065 bytes, SHA-256 `4b1b3d1c4f371119641b6d29ed9ea632ab4de8639d168e85139bc977d29c7f52`, with runtime fingerprint `88cbe19fae3a83bc7768c9689b912258416ff0b1bd12d8a74fd3e2ee23662460`. It records **zero provider requests, zero answer requests, zero database writes** and `release_gate_passed=false`. Its top-level fields matched the expected allowlist and contained no UUID-shaped text.

## Verification and limit

The focused synthetic diagnostic test file passed **8/8** before execution. This run measured designated-gold candidate recall on an **exposed development roster** with only one follow-up case. It did not independently grade every sent page's usefulness, make a Gemini source-ID judgment, open a browser PDF page, score the frozen new holdout, or satisfy the at-least-90%-of-all-displayed-pages gate. `any_useful_page_hit` remains **ungraded** because the exact v4 slate has no independent page-by-page usefulness labels. No Ask release or policy activation follows from this result.
