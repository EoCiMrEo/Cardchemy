# Recommendation after the failed per-page verdict pilot

Date: 2026-09-30 (America/Chicago). This is a **prospective, unapproved**
Lane 6/ADR-024 amendment. No new provider call is authorized by this note.
The completed [public calibration](2026-09-30-per-page-verdict-calibration-result.md)
failed its multi-page/cardinality gate. The 60 different-PDF heldout groups
remain unopened, and Ask remains disabled.

## Diagnosis that changes the next action

The four-verdict contract eliminated false no-match displays and returned
63/63 independently useful shown pages, but selected too few pages when two
or three useful pages existed. Across completed public groups, 80/106
gold-useful candidates received the model's `useful_reading_page=true`;
only 63/106 also received `requested_relation_present=true`. The second
Boolean was a strict subset of the first. Removing it **offline** increased
displayed usefulness to 79/83 (95.2%) and kept no-match at zero on these
known development cases, yet selected the exact useful set in only 10/17
two-page, 5/16 three-page and 1/2 overflow groups. A threshold change or
dropping the second Boolean alone cannot meet the approved multi-page
behavior. Reusing the consumed v3 authorization would misstate provenance.

## One isolating candidate

Keep the **same frozen four-candidate prompt, schema, strict parser, local
decision, 66 public calibration questions and all quality gates**, but compare
one stronger source judge: `gemini-3.5-flash` instead of
`gemini-3.5-flash-lite`. This isolates model capacity from prompt/selector
changes. Prepare a prospectively versioned caller, independent code hashes,
exclusive one-use ledger and keyless tests. Score all 66 calibration cases;
only if availability, zero false no-match, at least 90% usefulness across
every shown card, 5/6 exact cardinality in each one/two/three-useful stratum
and 2/2 overflow pass may the 60 different-PDF heldout be opened once.
The exposed 66 cases are development data; heldout is still independent.
Google's current [model catalog](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash)
lists this stable model and structured output support. Its current
[standard-token prices](https://ai.google.dev/gemini-api/docs/pricing) are
Free-tier USD 0 or Paid-tier USD 1.50 input/USD 9.00 output per million;
future live authorization must recalculate the guard then. At the existing
8,192/1,024 token cap, the Paid-tier worst case is USD 1.419264 for 66
calibration calls and USD 1.290240 for 60 heldout calls, before adding a
conservative operational ceiling. These calculations are not a provider bill
or approval to spend.

This comparison is **not** a claim that a larger model will solve the problem.
The prior Gemini 3.6 calls encountered HTTP 503 and no private-source
quality proof exists. The same-wire test provides a clean answer about model
capacity and availability. If it fails, stop before heldout and propose a
different source-selection architecture based on the failure type. Keep one
query embedding, at most one source-judge call, zero generated-answer or
verifier calls, exact current original-PDF references and Ask disabled.

The operator must approve the plan/ADR amendment and offline prototype
first. A subsequent public Gemini call requires its **own** exact
endpoint/model/price/call/token/time/cost envelope and credential-safe
one-use receipt under `AGENTS.md`. The currently configured key and the
earlier broad authorization are not that envelope. Separate private-source
transfer, matching versioned runtime, access, accessibility and release
gates remain even if public calibration and heldout pass.
