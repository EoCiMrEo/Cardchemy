# Public heldout v4 terminal result

## Scope and preservation

The separately approved Q022–Q060 public trial used twelve of its maximum
thirty-nine physical requests, then stopped. The original 60-question corpus,
labels, earlier outcomes/claims and consumed approvals are unchanged. No private
Knowledge, database write, runtime activation or automatic retry occurred.
Starting checkout remains dirty `main` at `6c02d6c`.

## Independently reconciled result

- Terminal SHA: `dbfa571a803156e62b48f44058e4c5de673bd52ecf8789eb5328073252335039`.
- Aggregate reconciliation SHA:
  `543078711a0d08657d2aa5483a2f6c599f4a5a0d63d04c98b102ca12616a2e97`.
- Q022–Q032 returned eleven valid responses. Q033 failed strict verdict
  admission with `provider_verdict_invalid`; its exact parser subcode is
  unknown because raw output was intentionally not retained.
- Across all thirty-three observed questions: thirty valid replies and three
  failures (inherited Q013/Q014 HTTP503 and new Q033 invalid verdict).
- Every displayed card counts: **42/43 useful (97.67%)**, one reviewer-Unsure
  card receiving zero credit, and zero unissued selected IDs.
- Twenty-seven questions remain untouched. Even perfect remaining replies
  could produce only 57 valid responses, below the frozen 58/60 availability
  gate. The caller stopped with `quality_unreachable`.

This is a partial usefulness result, **not a complete heldout or release pass**.
The original trial remains stopped; its consumed authority cannot resume it.

## Spending and process evidence

The twelve calls reported 80,652 input /16,258 output tokens and USD0.064846
under the frozen Paid-price guard. Q033 reported known usage and USD0.004921.
Combined heldout known guard cost is USD0.177512 across all thirty-six physical
attempts; five older attempt costs remain unknown. Including complete
calibration, known public guard cost is USD0.595668. These are estimates,
not provider invoices.

The independent reconciliation checked receipt/claim, request/code/checkpoint
hashes, spacing, usage and scorer/early-stop math. Four CPU/two GiB/9,000-second
kill-tree resource and successful supervisor completion receipts are bound.
All recorded processes are absent. No process was restarted.

## Next boundary

An inert successor may propose one explicitly manual new Q033 attempt and
twenty-seven untouched requests, preserving Q033's failed history and cost.
It must keep the same prompt, parser acceptance, corpus, labels and scorer,
retain only a finite safe parser subcode if a future verdict fails, pass mocks
and keyless preflight, and obtain a **new exact human provider envelope**.
It cannot retroactively pass v4. Ask remains disabled; Lane 6 remains **3/7**.
