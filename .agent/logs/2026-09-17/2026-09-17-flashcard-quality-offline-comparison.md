# Flashcard quality: offline comparison and instructor review

Date: 2026-09-17. Synthetic authored evidence only; no remote requests or private documents.

This replay freezes only the old generation renderer; both variants use the current system/map/reduce prompts, validator, allocation, budgets and pipeline. The deliberately underproducing scripted provider returns one fact per source and repeats it unless explicitly excluded. Results measure refill information and enforcement, not real-model prompt yield or injection resistance. Local latency is Python replay time; token counts use the local estimator and fixture prices of USD 0.10/million input and output tokens. No actual cost was incurred.

| Case | Renderer | Exact target | Accepted/raw | Duplicate rejections | Refill rounds | Requests | Transferred/expected chunks | Persistable card pages | Local input/output tokens | Fixture USD | Local ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| feasible_short_underproduction_refill | baseline renderer | clean failure | 1/3 | 2 | 2 | 3 | 1/1 | 0 | 1080/270 | 0.000135 | 10.029 |
| feasible_short_underproduction_refill | refined | pass | 2/2 | 0 | 1 | 2 | 1/1 | 1 | 1195/172 | 0.000137 | 5.907 |
| impossible_sparse | baseline renderer | clean failure | 1/3 | 2 | 2 | 3 | 1/1 | 0 | 1035/270 | 0.000131 | 5.875 |
| impossible_sparse | refined | clean failure | 1/1 | 0 | 2 | 3 | 1/1 | 0 | 1770/106 | 0.000188 | 5.890 |
| impossible_repeated_boilerplate | baseline renderer | clean failure | 1/3 | 2 | 2 | 3 | 1/1 | 0 | 1167/270 | 0.000144 | 6.256 |
| impossible_repeated_boilerplate | refined | clean failure | 1/1 | 0 | 2 | 3 | 1/1 | 0 | 1902/106 | 0.000201 | 6.147 |
| feasible_same_chunk_split_batches | baseline renderer | clean failure | 1/7 | 6 | 2 | 7 | 1/1 | 0 | 2674/630 | 0.000330 | 8.385 |
| feasible_same_chunk_split_batches | refined | pass | 3/6 | 3 | 2 | 6 | 1/1 | 1 | 3746/527 | 0.000427 | 8.343 |
| feasible_unicode_ocr | baseline renderer | clean failure | 1/3 | 2 | 2 | 3 | 1/1 | 0 | 1083/270 | 0.000135 | 6.059 |
| feasible_unicode_ocr | refined | pass | 2/2 | 0 | 1 | 2 | 1/1 | 1 | 1195/173 | 0.000137 | 6.053 |
| feasible_injection | baseline renderer | clean failure | 1/3 | 2 | 2 | 3 | 1/1 | 0 | 1161/270 | 0.000143 | 5.856 |
| feasible_injection | refined | pass | 2/2 | 0 | 1 | 2 | 1/1 | 1 | 1247/172 | 0.000142 | 6.057 |
| feasible_long_full_document | baseline renderer | pass | 1/1 | 0 | 0 | 10 | 8/8 | 1 | 17061/336 | 0.001740 | 25.036 |
| feasible_long_full_document | refined | pass | 1/1 | 0 | 0 | 10 | 8/8 | 1 | 17276/336 | 0.001761 | 24.958 |
| feasible_overlapping_chunks | baseline renderer | clean failure | 1/4 | 3 | 2 | 3 | 2/2 | 0 | 1759/357 | 0.000212 | 6.611 |
| feasible_overlapping_chunks | refined | pass | 2/3 | 1 | 1 | 2 | 2/2 | 1 | 1655/259 | 0.000191 | 6.471 |
| long_allocation_bottleneck | baseline renderer | clean failure | 1/1 | 0 | 2 | 8 | 3/3 | 0 | 14562/222 | 0.001478 | 17.685 |
| long_allocation_bottleneck | refined | clean failure | 1/1 | 0 | 2 | 8 | 3/3 | 0 | 15509/222 | 0.001573 | 18.165 |

Impossible cases expose no persistable partial result. Every accepted review card satisfies the same strict option, quote/answer and duplicate rules. Long target-one success demonstrates all-page evidence transfer (not accepted-card coverage of every fact). The overlap case uses 40 local overlap tokens with 128-token chunks. Same-source split requests still overlap; quota allocation remains weighted by text, not feasible fact count. The allocation-bottleneck document has two authored supported facts but cannot meet its assigned quotas: a longer administrative-only chunk receives quota again during refill. No redistribution was introduced. The scripted injection fixture proves the evidence remains on the untrusted wire and validation boundary, not that a remote model will refuse instructions.

## Instructor review sample

These four authored exemplars have not been scored by an instructor. The replay subset demonstrates mechanics; this sample provides reviewable wording/options/evidence for pedagogy. Score each criterion 0 (fails), 1 (needs revision), or 2 (meets); any unsupported or ambiguous answer fails regardless of total.

Criteria: one meaningful fact; unambiguous question/one answer; plausible parallel distractors; compact wording; exact contiguous evidence; useful coverage without repetition.

### Card 1

Which pigment absorbs light energy during photosynthesis?

Options: Chlorophyll; Hemoglobin; Melanin; Rhodopsin

Answer: Chlorophyll

Synthetic source quote: Chlorophyll absorbs light energy during photosynthesis.

### Card 2

What tissue transports water from roots to leaves?

Options: Phloem; Xylem; Epidermis; Cambium

Answer: Xylem

Synthetic source quote: Xylem transports water from roots to leaves.

### Card 3

Where does cellular respiration release usable energy?

Options: Ribosomes; Golgi bodies; Mitochondria; Nuclei

Answer: Mitochondria

Synthetic source quote: Mitochondria release usable energy through cellular respiration.

### Card 4

What force keeps planets in orbit around the Sun?

Options: Friction; Magnetism; Sunlight; Gravity

Answer: Gravity

Synthetic source quote: Gravity keeps planets in orbit around the Sun.

Reviewer note: the first draft used Keratin as a pigment distractor. It was replaced with Rhodopsin, another biological pigment, to keep options parallel; an instructor must still judge distractor plausibility for the intended students. Deterministic quality scores do not prove teaching quality.

Instructor decision: on 2026-09-18, the operator replied "very good" to the
explicit request to judge the four authored questions, answers, distractors and
evidence as the Preparation A baseline. This accepts this synthetic teaching
sample; no numerical 0-2 scores were supplied, so none are imputed. It does not
prove real-model yield or authorize paid/real-model A/B evaluation.

## Implementation and accounting

Generation/map/reduce prompts are versioned. Refill receives at most 32 clipped question/answer pairs in a complete JSON list capped at 384 local tokens. They remain untrusted exclusions, never supporting evidence. All original accepted cards remain in deterministic duplicate comparison. Preflight reserves the bounded refill list plus field overhead numerically to cover all token-estimator components, and renders reduction overhead. Per-call context and remaining-job input/output/cost envelopes are reserved before requests, including concurrent pending calls. Successful responses reconcile to reported usage; failed/cancelled requests move to conservatively charged uncertain envelopes until that run ends. Physical retry consumption without a usage receipt remains unknown; telemetry is not a billing ledger.

No output caps, token-weight allocation, same-source scheduling, retry owner, structural/grounding thresholds or complete-result semantics were relaxed. Model/schema failure still aborts the entire batch; no partial set is persisted.

Ten-card output capacity probe: `min(8192, 10 * 512 + 256) = 5376` local configured output tokens, below the 8192 ceiling. This unchanged cap is verified; no remote truncation/yield claim or cap increase is made. Compact answer/quote/options instructions precede any separately measured change.

Rendered preflight remains an estimate: provider output-token budgets and the local estimator are different measurements, and a valid summary can exceed its local planning surrogate. Context and remaining-job envelopes are checked again with the actual rendered summary/exclusions before each request, then with reported usage. These gates prevent subsequent overspending but cannot retroactively prevent already consumed remote tokens or prove a complete retry billing bound.

## Reproduction

From backend: `venv/Scripts/python.exe -m tests.support.quality_replay --output <absolute-output.md>`. The normal targeted suite includes `tests/test_ai_quality_refinement.py`; provider quota is never used.

## Scope, starting context and verification

Preparation A implementation only, following the operator-approved subject-RAG
plan on `codex/subject-rag-through-phase-13`, carried from source baseline
`e10f5839735379e4277d35600067835f53272a89`. Existing untracked plan/review logs and
unrelated working-tree state were preserved. Root `.env`, operator credentials,
used migrations, database data and volumes were neither read nor modified by
this workstream. Other agents own configuration migration and RAG schema work.

Implementation paths: `backend/app/ai/prompts.py`, `pipeline.py`, `grounding.py`;
authored corpus `backend/tests/fixtures/ai_eval/quality_v2.json`, replay helper
`backend/tests/support/quality_replay.py`, targeted contracts
`backend/tests/test_ai_quality_refinement.py`; supported evaluation and flow
guides `docs/AI_EVALUATION.md`, `docs/architecture/AI-GENERATION-FLOW.md`.
The shared indexes, context maps, roadmap and ADR work belong to the root task.

Direct checks: existing focused AI/contracts suite passed 42 tests after initial
refinement; final quality/pipeline/grounding selection passed 55 tests in 2.93s.
The 18-row comparison was reproduced after adding actual chunk overlap and the
allocation-bottleneck case. `git diff --check` passed. A reviewer caught and fixed
a non-conservative punctuation placeholder before final verification; the
additive reserve now covers all local estimator components. Source remained
stable for the root task's full offline and deterministic journey gates.

Root task reported the final full backend offline suite passed 413 tests with
50 service-gated skips and one live-AI deselection in 71.00s; the deterministic
browser/API/generation/email/PostgreSQL journey passed browser/database proof and
cleaned its owned resources. Those gated skips and the offline journey do not
establish real-provider quality, production deployment or external-mailbox
delivery. Root owns the final context/navigation check and integrated journal.

No temporary resources were created by this replay. No paid/live provider calls
were authorized or performed. Human sample judgment remains pending; remote
prompt yield and instructor pedagogy must not be inferred from these tests.
