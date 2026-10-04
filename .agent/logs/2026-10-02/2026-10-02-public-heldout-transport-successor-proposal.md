# Narrow public heldout transport successor proposal

## Evidence and purpose

The [approved independent v1 trial](2026-10-02-visual-public-heldout-terminal-result.md)
stopped after six requests: three valid, two provider timeouts at the configured
60-second deadline and one HTTP503. Independent review verified all 26 code
hashes, six receipt/claim pairs and three run/launch/execute claims, exact
request bindings, four CPU/two GiB, minimum spacing 20.136 seconds and elapsed
250.692 seconds. No retry occurred. Two successful displayed cards are useful,
but are not an independent quality pass; the >=58/60 availability gate became
mathematically unreachable at the third failure.

The stop does not establish a quota cause, model inadequacy or source-selection
regression. Three successes cannot estimate a reliable latency percentile.
Repeated unchanged trials would provide weak information and risk extra charges.
The original failed result, labels, caller and consumed approval stay immutable.

## Prospective narrow repair

Prepare a separately versioned, **not live-authorized** transport successor:

- Same model, HIGH thinking, frozen prompt/schema, text/cues, faithful full-page
  PNGs, all sixty cases and conservative source qualifications; no ranking or
  label change. Keep all original heldout scoring thresholds, including 80%
  of every displayed card, >=40/48 hits, >=14/16 per form, >=58/60 valid,
  <=2 failed groups, >=10/12 conclusive no-match and zero selected unknown or
  invalid-source violations.
- Inherit only the three valid, exact bound replies Q001/Q002/Q005. They were
  valid under the same unchanged wire/parser and finished within the shorter
  deadline. Preserve all six physical v1 attempts, including its three failures
  and charges, separately. V1 never becomes a pass.
- At most **57 fresh calls**: the 54 never-called questions and explicit,
  separately approved manual fresh attempts for Q003/Q004/Q006. No automatic
  same-question retry, no missing question or failure disappears from history.
- Change only response deadline to **120 seconds** and minimum between-request
  spacing to **30 seconds**. After a service-unavailable response, wait at least
  **120 seconds before a different next question**. This is an unproven scheduling
  hypothesis; it does not claim to repair Google service capacity.
- Fresh durable approval/ledger and resource-fenced caller, with at most 150
  minutes, four CPU/two GiB, 32,768 input/4,096 thinking-inclusive output tokens
  per call; all response/verdict/request/image ceilings remain unchanged.
- Full-query scoring still has sixty distinct cases with the original gates.
  First v1 availability/failure counts remain independently visible; successor
  counts and any manual reattempt are identified as a different transport trial.

Preparation follows standing aligned technical authority and involves synthetic
tests/preflight only. It does not increase the installed application deadline,
rewrite used migrations, send a private lecture or enable Ask. A successful
public transport result would still need a separately versioned application
contract if that deadline were adopted, plus private and release gates.

## Exact proposed future provider envelope

This section is a proposal, **not approval**:

POST `https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent`,
Gemini 3.5 Flash-Lite, HIGH thinking, store=false; only current public questions
plus text/cues and at most four bounded PNGs from the same cached four CC BY4.0
PDFs, only issued ID/category output. Maximum 57 POSTs, zero retries, >=30s
spacing and the between-question service-unavailable cooldown above; <=120s
per call, <=150 minutes, four CPU/two GiB. No embedding, countTokens, File API,
download, private Knowledge, history, identity, labels, PDF bytes, DB write or
Ask activation. Input/output totals <=1,867,776/233,472 tokens; request <=6MiB,
image <=1,600px/2MP/1MiB, HTTP <=64KiB and verdict <=2KiB.

Free tier listed price is zero with public product-improvement use. Paid guard
USD0.30 input/USD2.50 output per million tokens; maximum per-call rounded
reservation USD1.144047, proposed new cap **USD1.25**. Prior known guard cost
USD0.432600 (calibration USD0.418156 + heldout USD0.014444) remains separate;
three new failed-request charges and older failures remain unknown. No request
may occur before a fresh explicit reply to this exact envelope and final pinned
code/input/resource preflight. A configured key is not authorization.

## Completed offline preparation

Added the inert [v2 caller](../../../scripts/run_visual_public_heldout_v2.py),
[resource supervisor](../../../scripts/launch_visual_public_heldout_v2.py)
and [synthetic contracts](../../../backend/tests/test_visual_public_heldout_v2_caller.py).
**19 synthetic tests passed**. Actual keyless admission bound three old valid
replies, all six old receipt/physical-claim pairs and the unchanged failed
score; it prepared exactly 57 distinct fresh requests with no credential or
network access. Roster SHA:
`de624cb08aaa3c59f8f7adf815a19f0c9f5e2dc180e26cf2b4bdf9e505109e9d`;
checkpoint SHA:
`03287d2d7bce4ea181844f218b4a94afc77c221914d4b3415e81263fe7070199`.

Independent review confirmed unchanged wire/scorer/denominator gates and
fresh approval/resource/ledger checks before the key. It found one reporting
ambiguity, now fixed and retested: a complete successor has **60 evaluated
questions and 63 historical-plus-new physical requests**, not sixty physical
calls. Its field names now distinguish those counts. Caller SHA after repair:
`145acf3764de7fa37da4d0768913726a681d04c5fa4007036256d75e201ad928`;
launcher SHA:
`918047a4f97d4594a7b2a4c52f375075623bcc42961fbb2111534d8d0367d3f3`.

The final limited independent review confirmed that correction. Compilation
and scoped whitespace checks passed. `LIVE_AUTHORIZED` remains false; no
fresh approval/attempt/credential/network/private transfer/DB write/runtime
change occurred. A concise exact-envelope question has been presented; no
answer is inferred from generic prior authority. This is preparation only,
with Ask still off and Lane 6 still 3/7.
