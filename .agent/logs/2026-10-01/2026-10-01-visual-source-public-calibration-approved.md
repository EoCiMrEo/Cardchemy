# Approved calibration-only public visual-source pilot

Date: 2026-10-01 (America/Chicago). The owner explicitly approved the
[bounded recommendation](2026-10-01-visual-source-public-calibration-recommendation.md).
This permits a Lane 6/ADR-024 amendment, a separately versioned caller/scorer,
keyless testing and freeze/preflight, then exactly one public calibration
pilot. It records authorization, not preparation completion, provider
execution, a measured pass or permission to enable Ask.

Starting state: dirty `main`, HEAD `6c02d6c`, Lane 6 **3/7**, Ask disabled.
The [completed offline reconciliation](2026-10-01-visual-source-semantic-control-result.md)
preserves all old results and shows conservative input ceilings can support
the existing gates. Its 251 synthetic tests and 67 frozen inert inputs are
not selector accuracy. Never reopen a consumed ledger or tune from observed
pilot scores.

## Frozen inputs and unchanged conservative gates

Use all 66 original public calibration questions plus the one independently
reviewed four-page control: **67 groups**, each containing four issued exact
text/cue/full-page PNG inputs from the same four cached CC BY 4.0 PDFs.
No source, label or download is added. Bind the full caller/scorer, approval,
inputs and guards by SHA before credential access or network dispatch.

| Parent artifact | SHA-256 |
| --- | --- |
| Summary / 67 input bindings | `09b1f1abd79c6a79a3d5a50f4d5ae4d3c08dc377f9c757caeb7b552ca5c0d3b3` |
| `public_visual_page_source_v2` prototype | `f6541e0fc854bdb5f4279a385d6f2c116916a03ccf2d4b5f20ad328c61e44415` |
| Conservative gate verification | `6dc1b51d66101072c8695777d7b448518508dd902c76e23257c947c69fe1a813` |

Keep historical positive obligations and the **108 Yes / 151 No / 5 Unsure**
qualification overlay. P146 remains a miss; uncertain/conflicting selections
earn no useful-card credit. Every displayed card and all 67 requests/errors
remain in their denominators. The original unresolved group receives no
binary no-match/exact-set credit and still counts toward availability.

Calibration requires all of:

- At least **45/54** positive hits and **15/18** per direct/paraphrase/follow-up
  form, preserving the stronger public `ceil(5*positive_form/6)` rule.
- Exact useful-set success **15/17** one-page, **18/21** two-page, **12/14**
  three-page and **2/2** capped-three four-useful overflow.
- All **12** conclusive no-match responses valid and empty.
- At least **65/67** valid responses, at most two errors; errors are misses,
  never successful no-match.
- At least **90%** usefulness over every displayed card, including unknown
  selections in the denominator, plus the existing source/privacy gates.

Return issued IDs, closed usefulness/cue judgments and question status only.
Strict local parsing displays 0–3 unverified PDF page references, with no
generated answer, explanation, quote or weak padding. Images are input only.

## Exact one-use live envelope

| Guard | Approved scope |
| --- | --- |
| Endpoint | POST `https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent` |
| Model / configuration | `gemini-3.5-flash-lite`, HIGH thinking, `store=false`, one ID-only judgment per group |
| Requests | At most **67 POST**, zero automatic or manual retry; no embedding, countTokens, File API or tool calls |
| Data | Current public question plus four exact text/cue inputs and four faithful public PNGs; no private Knowledge, identity, chat history, gold labels or PDF bytes |
| Images / complete wire | At most four images, each ≤1,600 px long side / 2 MP / 1 MiB; full request ≤6 MiB; frozen observed maximum 3,395,977 bytes |
| Tokens | ≤32,768 input including images and ≤2,048 output including thinking per call; ≤2,195,456 input / 137,216 output total |
| Rate / time | At least 20 seconds between attempts, ≤30 seconds per HTTP request, ≤90 minutes for the whole calibration |
| Process / preflight | One fenced hidden process, 4 CPU / 2 GiB resource bounds; frozen keyless preflight before credential/network access |
| Response | ≤64 KiB HTTP body; strict source-verdict JSON ≤2 KiB; never retain raw responses or thoughts |
| Price / new cost | Paid guard USD 0.30 per million input and USD 2.50 per million output tokens; maximum estimate USD 1.0016768, **new ceiling USD 1.05** |

The selected project is Free tier, currently listed at zero; Google may use
public inputs for product improvement. The paid guard covers a tier change.
This is not an invoice; earlier failed-request charges remain uncertain.
Images consume tokens, so byte caps are not exact token or cost counts.
Reserve each physical attempt conservatively before dispatch and validate
actual usage. Missing/oversized usage, permanent/budget/identity failures or
unreachable frozen quality gates stop the pilot; retain uncertain execution
and spend rather than reporting zero. Stop if errors exceed two. Do not tune,
retry or proceed to heldout after failure.

## Separate release and preservation gates

This scope permits no download, embedding/countTokens request, File API,
private Knowledge transfer, heldout opening, database/runtime-policy change,
root `.env` edit or Ask activation. Keep the populated installation, exact
private original PDFs, root environment, ignored backups, old labels,
receipts/freezes and source-only policy. A public calibration pass alone
does not authorize independent different-PDF visual holdout review, its
provider calls, private transfer, production renderer/dependencies or any
release/enablement work. Those retain separate explicit gates/envelopes.

The remediation plan, ADR-024/index, current state and log index record this
approval. Lane 6 remains **3/7**, all four quality/release items open, Ask off.

Documentation checks passed: context validation and scoped whitespace
validation. These checks establish active-link/documentation integrity, not
the caller's offline contract tests, a provider execution or release quality.
