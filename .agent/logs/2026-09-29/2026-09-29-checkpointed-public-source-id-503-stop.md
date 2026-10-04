# Checkpointed public source-ID pilot stopped after a second HTTP 503

Date: 2026-09-29 (America/Chicago). Scope: the one separately approved,
public-only Gemini 3.6 Lane 6 evaluation. Branch `main`, starting HEAD
`6c02d6c`; pre-existing uncommitted Lane 6 work and the retained local
installation were preserved. This record supersedes the pending-run status in
the [approval record](2026-09-29-resumable-public-source-id-pilot-approval.md),
not its approved limits.

## Frozen checkpoint and preparation

The approved evaluation used authorization identity
`lane6-public-36-resume-20260929-b599f494d4774a198a6a294f92944dd9`.
The frozen runner SHA-256 was
`b57d9f9509d2a6efbeaf155b0ba15481de6a165b6728e16e3ad0b977121690f3`,
the new approval receipt SHA-256 was
`6f52f9460fbffb1fef88ab2a2cc44eef090117b80a146e8c035d1ee540e5963c`,
and the validated prior checkpoint SHA-256 was
`7cf5f983848582a8f4bdf6fee534e2b73af4877094bc6aff6c59ddfc6879103f`.
The earlier accepted response/usage ledgers remained unchanged, with SHA-256
prefixes `18d7d35d` and `3b6f04eb`, respectively. They contain the first
three valid calibration results; no completed group was replayed. A
credential-free, network-free preflight passed under the same permitted command
identity as the live run, admitting 45 unresolved calibration groups and a
conditional 48-group heldout without opening or scoring heldout.
An earlier keyless preflight rejected an output path directly under OS Temp;
placing the fresh output inside its own Temp parent satisfied the path guard.
That rejected preflight made no provider call or approval claim.

## Observed execution

The first physical call for unresolved calibration group four returned HTTP
503. The evaluation-only retry began **20.017 seconds after** that first
response; its call start was **29.639 seconds after** the first call start.
The retry also returned HTTP 503, so the harness stopped under the approved
second-503 rule. It made **two new physical calls**, accepted **zero new
groups**, produced no calibration or heldout quality score, and did not open
heldout. The run and call claims remain consumed; this authorization cannot
be replayed. The selected IDs from the three prior public successes were not
copied into this tracked record or inspected for tuning.

The two new calls reserved **USD 0.039936** at the conservative maximum-token
guard. Neither returned a usage receipt, so their **actual cost is unknown**;
the reservation is not a provider invoice. The three accepted calls in the
prior run had USD 0.007823 conservative guard cost, while its fourth failed
call's actual cost is also unknown. Earlier failed pilots have separate,
unknown actual costs. The failed calls establish a transport-availability stop
for this pilot, **not** a judgment of the model's page-selection quality or a
reason to weaken the frozen usefulness gate.

## Verification and remaining boundary

The checkpointed harness passed **52 focused provider-free tests** after its
authorization identity was frozen. The previously run full backend offline
suite passed **2,417 tests**, with 151 skipped and two live cases deselected,
before this new harness was added; it is not claimed as a full-suite pass for
the checkpointed harness. Read-only inspection of the new ledger confirmed
two call claims, two HTTP 503 outcomes, the second-503 stop, zero new accepted
groups, USD 0.039936 reserved, and `heldout_opened=false`. The prior
checkpoint file's SHA-256 was independently rechecked. No application database
write, private Knowledge transfer, answer generation, runtime-policy change or
Ask enablement occurred.
The root task separately rechecked the retained Docker stack: all eight
configured services were running healthy after this pilot.

The retained application still pins Gemini 3.8 for its dormant v4 path. Ask
remains disabled. Lane 6 remains **3/7**; all four source-quality and release
checklist items remain open. Any further paid pilot needs a **new** explicit
endpoint/model/price/call/token/time/cost envelope and authorization. The
independent original-PDF usefulness, no-match, access, spoken accessibility
and release gates are still unmet.

This factual update was linked from the log index and reconciled with Lane 6,
ADR-024, the ADR index, current state, roadmap, deployment and RAG evaluation
guides. `python scripts/check_context.py` passed with 37 required files, 79
active guides and 1,518 local links. The three focused pilot harness test files
passed **52/52** from the backend virtual environment, and targeted
`git diff --check` exited 0 (with only line-ending conversion notices). An
initial test command used a repository-relative interpreter path while its
working directory was already `backend`; it failed before collection. The
correct backend-relative command then passed. No paid request was made during
this documentation and verification step.
