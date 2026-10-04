# Ask evaluation guides aligned after the Flash-Lite timeout

Date: 2026-09-29 (America/Chicago). Branch `main`, starting HEAD `6c02d6c`.
Scope: correct two active operator guides after the separately approved public
Gemini 3.5 Flash-Lite source-ID pilot stopped. No runtime, database, provider
claim, root configuration, PDF, or private content was changed by this edit.

## Starting evidence and correction

The retained local schema is at `20260928_0029`; v4 source-only code exists but
Ask admission remains fenced and the prospective runtime source judge remains
pinned to Gemini 3.8 Flash. The public Flash-Lite pilot made 11 physical
calibration calls: ten accepted ID/usage receipts, then one 30.006-second
`provider_timeout`. It stopped without retry or a complete 48-case score; the
heldout was not opened. The timed-out call's actual cost is unknown. See the
[pilot stop](2026-09-29-flash-lite-public-calibration-timeout-stop.md).

`docs/AI_EVALUATION.md` still described v4 as needing its first immutable
policy and called v3 the current runtime. `docs/ASK_AI_SHUTDOWN.md` described
only the earliest one-call public stop. Those statements were superseded by
the retained 0029 cutover and the later pilot. The guides now distinguish the
dormant implemented v4 path from release activation, record the latest pilot
stop, and require a fresh exact provider envelope before any new evaluation.
The source-only product boundary, private-content decision and independent
original-PDF usefulness gate remain open.

## Verification and preservation

The edit is documentation-only. `python scripts/check_context.py` and
`git diff --check` verify active local links and patch shape; their exact
results are reported in the task handoff. Neither check demonstrates a
quality pass, accessibility pass, private transfer authorization or Ask
availability. The populated volume, original PDFs, root `.env`, public
receipts and one-use claims were preserved. Ask remains disabled, and Lane 6
remains 3/7.
