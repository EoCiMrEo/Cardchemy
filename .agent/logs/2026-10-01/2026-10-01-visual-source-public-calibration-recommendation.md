# Recommendation: one public visual-source calibration

Date: 2026-10-01 (America/Chicago). **Proposed, not approved or executed.**
The [narrow offline reconciliation](2026-10-01-visual-source-semantic-control-result.md)
is complete. Actual source inputs now include faithful page images, explicit
discovery/clarification semantics and a reviewed no-match control. Conservative
input ceilings can meet the existing gates despite known misses/conflicts;
they do not establish selector accuracy. No old provider ledger is reopened.

Recommend plan/ADR-024 amendment and a separately frozen, keylessly tested
caller/scorer, then exactly **one calibration-only public trial** of the
prepared `public_visual_page_source_v2` wire. Do not change the prompt from
observed scores, retry or open heldout in this authorization. A failed
calibration stops; a pass still requires independent different-PDF visual
holdout review and separately approved heldout/private/runtime/release work.

## Concrete data and unchanged gates

- All 66 original public calibration questions plus one reviewed four-page
  control: 67 groups. Each has four issued exact text/cue/full-page PNG inputs
  from the same four cached CC BY 4.0 PDFs; no new source, label or download.
- Exact prepared inputs are bound by summary SHA
  `09b1f1abd79c6a79a3d5a50f4d5ae4d3c08dc377f9c757caeb7b552ca5c0d3b3`
  and prototype SHA
  `f6541e0fc854bdb5f4279a385d6f2c116916a03ccf2d4b5f20ad328c61e44415`.
  Conservative gate verification SHA:
  `6dc1b51d66101072c8695777d7b448518508dd902c76e23257c947c69fe1a813`.
- Keep original positive obligations and 108 Yes/151 No/5 Unsure qualification
  overlay. P146 remains a miss; conflicting fresh positives and all unknown
  selections get no useful-card credit. Keep all 67 request/error and every
  displayed-card denominators, including uncertain selections.
- Calibration requires at least 45/54 positive hits and 15/18 per form,
  exact useful-set ≥15/17 one-page, ≥18/21 two-page, ≥12/14 three-page and
  2/2 capped-three overflow, all 12 conclusive no-match responses valid and
  empty, ≥65/67 valid responses and ≥90% usefulness over all displayed cards.
  The original unresolved group is no-match/quality-uncredited, still part
  of availability. Retain full receipts and every known error/miss.
- Only issued IDs, closed usefulness/cue judgments and question status can
  be returned. Local strict parsing displays 0–3 unverified page references,
  no answers/explanations/quotes and no weak padding. Public PDF images are
  input only, never generated output.

## Proposed exact live envelope

| Guard | Proposed scope |
| --- | --- |
| Endpoint | POST `https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent` |
| Model / configuration | `gemini-3.5-flash-lite`, HIGH thinking, `store=false`, one ID-only judgment/group |
| Requests | At most 67 POST, zero automatic/manual retry; no embedding/countTokens/File API/tool calls |
| Data | Current public question + four exact page cues/texts + four faithful public PNGs; no private Knowledge, user identity/history or PDF bytes |
| Images / body | ≤1,600 px / 2 MP / 1 MiB each, four at most; complete wire ≤6 MiB, observed maximum 3,395,977 bytes |
| Input / output | Guard ≤32,768 input tokens including images and ≤2,048 output including thinking/call; ≤2,195,456 / 137,216 total |
| Rate / time | ≥20 seconds between attempts, ≤30 seconds/HTTP, ≤90 minutes whole calibration |
| Process | Bounded 4 CPU / 2 GiB, one fenced hidden process; frozen preflight before credential/network access |
| Response | ≤64 KiB HTTP envelope; closed source verdict JSON ≤2 KiB; never retain raw responses/thoughts |
| Price / new cost | Paid guard USD0.30/1M input and USD2.50/1M output; maximum estimate USD1.0016768, ceiling USD1.05 |

The official [model page](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite)
supports images, structured output and thinking. The checked
[pricing](https://ai.google.dev/gemini-api/docs/pricing) lists Free tier at
zero, with product-improvement use, and the Paid rates used above. Free tier
is the operator's selected project; the paid guard protects a tier change.
This estimate is not an invoice, and costs from earlier failed requests
remain uncertain.

[Token documentation](https://ai.google.dev/gemini-api/docs/tokens) states
that images are tokenized. Full wire bytes are not tokens. Offline UTF-8
text/schema upper estimates plus a conservative 3×3×258-token allowance for
each image reach 17,814 tokens before protocol reserve; the proposed 32,768
input guard accommodates that estimate. The caller must also validate actual
usage and reserve each physical attempt conservatively before dispatch;
oversized/missing usage or permanent/budget/identity failures stop the trial,
with cost uncertainty retained. No exact token-count request is presumed.

Stop if the frozen quality gates become unreachable or errors exceed two.
Errors count as misses; no failed request is successful no-match. Do not tune,
rerun or consume heldout after failure. A public pass does not grant private
transfer, production renderer/dependency approval, database or `.env` change,
runtime-policy selection or Ask activation. Lane 6 remains 3/7 and Ask off
until independent usefulness and all release gates actually pass.
