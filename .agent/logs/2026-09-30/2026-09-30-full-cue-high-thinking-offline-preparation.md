# Full-cue high-thinking candidate: offline preparation

Date: 2026-09-30 (America/Chicago). Scope: the owner's approved Lane 6 /
ADR-024 amendment and keyless public-only preparation. Starting branch
`main`, HEAD `6c02d6c`, with the existing extensive uncommitted remediation
work preserved. This is **not a provider-quality or release pass**. Lane 6
remains **3/7** and Ask remains disabled.

## Implementation and independent review

Prepared a distinct version of the unchanged four-page categorical request:

- `scripts/prototype_full_cue_high_thinking_v1.py`: identical current
  question, full page cues, order, prompt and four labels. The prospective
  REST settings change only thinking to `high` and combined output/thinking
  allowance to 2,048 for `gemini-3.5-flash-lite`.
- `scripts/run_fresh_public_full_cue_high_thinking_v1.py`: hard-disabled
  live flag, unapproved authorization ID, zero cost caps and distinct
  one-use ledger. Every attempt must be claimed before transport; no replay.
- `scripts/score_fresh_public_full_cue_high_thinking_v1.py`: retains all
  approved hit, exact-cardinality, overflow, no-match, availability and
  displayed-card usefulness gates. The final scorer and early-stop bound
  share the same gate function. The bound assumes every remaining case
  receives the best possible useful IDs and stops only when that cannot
  pass. It applies to heldout only after passing calibration admission.
- `scripts/prepare_fresh_public_full_cue_high_thinking_v1_approval.py` and
  `scripts/launch_fresh_public_full_cue_high_thinking_v1.py`: distinct
  SHA-bound approval, keyless admission before key access, isolated single
  credential, hidden detached execution and a consumed launch claim.
- `backend/tests/test_full_cue_high_thinking_public.py`: synthetic controls
  for request identity, disabled authorization, parser rejection, hidden
  thinking usage, interrupted/failed attempts, early stopping and the full
  calibration-to-heldout contract.

The first independent review found missing latency receipts, incomplete
early-stop coverage, raw structured output persistence and lost known usage
on an over-token response. All were repaired before live approval:

- Persist only locally validated issued `selected_ids`, content-free usage
  and latency. Raw provider JSON stays in memory and is discarded.
- Fsync the selected IDs and usage together in one per-attempt journal;
  scorer inputs are materialized only for a complete split. Partial stops
  have a distinct terminal receipt and cannot count as a full score.
- Record each attempt's latency, including transient failure; recompute
  p95 from receipts. Latency measurements are not policy identity fields,
  so different calibration/heldout durations cannot falsely reject a run.
- Preserve reported input/output usage when a response exceeds its token
  cap; stop without retry and report the already known cost.
- Preserve historical scripts, results and consumed ledgers.

A second independent read-only review found no remaining concrete
authorization or scoring blocker. If a process dies during final receipt
materialization, the run fails closed; this does not authorize a restart.

## Checks and evidence

- **50/50 targeted new and historical tests passed** from `backend`:
  `test_full_cue_high_thinking_public.py`,
  `test_run_fresh_public_categorical_page_judge_v1.py`,
  `test_score_fresh_public_categorical_page_judge_v1.py`, and
  `test_run_fresh_public_source_id_v2_augmented.py`.
- Syntax compilation of all five new scripts and `git diff --check` passed.
  `python scripts/check_context.py` passed 37 required files, 79 active
  guides and 1,660 local links. The distinct real ledger contains zero
  attempt claims. Caller/scorer SHA-256 at this disabled offline freeze:
  `c408d1a87f611235f2dafa26f251a65e734932caf1f27bb65ace0fe3bc5c2216` /
  `abdc630fd2d244ba8ccb47121f4241fa73d1e511c80459f37527b8aed180d5e2`.
- **66-case real public preflight passed**, without key access or provider
  traffic. Maximum REST body: **6,346 bytes**; maximum model-visible input:
  **5,942 bytes**, plus the existing 512-token protocol reserve below 8,192.
  The request body manifest SHA-256 remains
  `0ff18408612e54fbe58d60de1b921017352fc0c00525b37ed986098bbd4cf07c`.
  Freeze SHA-256:
  `c8b97e3851f081c40108d6f6a40b9bb675dc3b824329d4fc7f047480425017b1`.
- Source integrity admission re-extracts and hash-checks **all eight public
  PDFs**. The 60 real heldout questions, labels and model outcomes remain
  unopened. Plan/ADR wording now explicitly distinguishes those facts.
- A harmless fake child was launched through the actual detached launcher
  from a completed Codex tool invocation. A separate invocation observed it
  running; another observed its successful terminal receipt after 25 seconds.
  This confirms survival across that tool invocation's exit, not across a
  machine/app crash. No key or network was involved; the child exited.
- PDF extraction emitted its existing object-offset repair warnings; source
  identity, offsets and request admission still passed. The first large
  patch encountered changed context and applied nothing; it was corrected
  before the passing verification.

No Gemini request, real heldout scoring, private Knowledge transfer, database
write, reindex, runtime configuration change or Ask activation occurred.
Root `.env`, populated volumes, original PDFs and ignored backups were not
modified. No broad runtime suite was rerun for these offline harness changes;
earlier runtime/service evidence is not recharacterized as this candidate's
provider-quality evidence.

## Next bounded provider decision

The approved preparation does not authorize execution. A separate exact
live envelope is required by `AGENTS.md` before a real key can be used.
Google's [thinking documentation](https://ai.google.dev/gemini-api/docs/thinking)
and [pricing](https://ai.google.dev/gemini-api/docs/pricing?hl=en) were
rechecked: this model supports high thinking; Free tier lists zero price
and product-improvement use, while the Paid guard is USD 0.30 input and
USD 2.50 output (including thinking) per million tokens.

A prospective single staged pilot is 66 calibration requests plus 60
different-PDF heldout requests **only after every calibration gate passes**.
At 8,192 input / 2,048 output tokens per request the rounded worst-case
reservation is USD 0.500148 + 0.454680. A proposed USD 1.00 ceiling can be
split into USD 0.52 calibration and USD 0.48 heldout. Other limits remain
30 seconds per call, at least 20 seconds between starts, 60 minutes per
split / 120 minutes total, zero retries and at most two failed cases per
split. The third transport failure or an unreachable quality gate stops
the candidate. Earlier failed-attempt costs remain uncertain and separate.

Even a public pass leaves private transfer approval, matching immutable
runtime policy/migration after `0029`, actual independent private retrieval
and displayed-PDF usefulness, access/revocation, spoken accessibility and
release/rollback evidence outstanding. None of the four open Lane 6 boxes
is closed by this preparation.
