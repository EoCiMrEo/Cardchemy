# Free-tier Batch diagnosis: model-specific correction

Date: 2026-09-29 (America/Chicago). This record explicitly corrects the
overbroad "stop using Batch" recommendation in the earlier
[eligibility note](2026-09-29-free-tier-batch-eligibility-recommendation.md).
No provider call, private-data transfer, database write, architecture change,
plan expansion or Ask activation occurred in this correction.

The operator confirmed that the local Gemini API project is on Free tier and
chose a **public-only synchronous pilot** next. Google's
[current pricing table](https://ai.google.dev/gemini-api/docs/pricing) lists
Batch as **Not available** on Free tier for the exact attempted model,
`gemini-3.6-flash`. That is a strong account-eligibility explanation for the
one HTTP 400, but the response body was deliberately not retained, so the
server's actual rejection reason is still unknown. The same table lists
Free-tier Batch tokens for `gemini-3.5-flash-lite`, while its top-level tier
summary describes Batch as a Paid feature. This conflict does not establish
that a Free-tier 3.5 Flash-Lite Batch job would be admitted; the approved
direction is synchronous and does not need that experiment.

The pricing table lists Free-tier synchronous Standard use for both
`gemini-3.6-flash` and `gemini-3.5-flash-lite`. It also says Free-tier
submitted content may be used to improve Google's products. Any evaluation
under the owner's choice must use only the independently frozen public PDFs;
it does not authorize a private lecture transfer. A new provider attempt
requires an exact endpoint/model/price/call/token/time/cost envelope and a
fresh one-use ledger. The consumed Batch and earlier synchronous claims are
preserved. Ask remains disabled, Lane 6 remains 3/7, and no public or private
quality score follows from this pricing clarification.

The ROADMAP, current-state and Lane 6 plan references to the older 503 stop
were also made chronological. `git diff --check` passed; `python
scripts/check_context.py` validated 37 required files, 79 active guides and
1,535 local links. These checks validate documentation shape and whitespace,
not provider admission or source usefulness.
