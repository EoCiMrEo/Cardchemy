# Recommendation after the stronger judge's HTTP 503 stop

Date: 2026-09-30 (America/Chicago). **Proposal only.** The Lane 6 plan,
ADR-024, runtime and provider caller have not been amended for this
candidate. No new Gemini request or private-source transfer is authorized.

## Evidence that guides the choice

The prior Flash-Lite public Boolean pilot completed 65/66 calls, showed
63/63 useful page/cue cards and zero false display across twelve no-useful
groups, yet selected the exact useful set in only 4/17 two-page, 3/16
three-page and 0/2 four-useful groups. Its `requested_relation_present`
Boolean rejected seventeen public pages already marked useful by its other
Boolean. Removing that conjunction offline raised exposed displayed-card
usefulness to 79/83 but still missed the multi-page gates. Thus lowering a
threshold is insufficient.

The approved same-wire `gemini-3.5-flash` comparison stopped after seven
valid responses and three HTTP 503s in its first ten attempts. A read-only
partial diagnostic of those seven **exposed public** groups found six of six
shown cards useful, six of seven exact 0–3-page selections and one useful
page omitted. These seven cases are too few and selected by a stopped run;
they establish neither a calibration pass nor the stronger model's general
quality. Google's [error reference](https://ai.google.dev/gemini-api/docs/api-errors)
maps 503 to temporary unavailability/overload; status alone cannot prove
the specific upstream cause. The stronger pilot's one-use ledger is consumed,
and the 60 different-PDF heldout is unopened.

## One next candidate to approve or reject

Keep **one current-question embedding**, at most **one** source-judge call,
zero answer/verifier calls, zero automatic retry and original-PDF source-only
results. Use the more available `gemini-3.5-flash-lite` public pilot model,
but ask for **one categorical verdict for each of four issued page IDs**:

- `DIRECT_RELATION`: page and shown cue directly contain the named entity,
  requested relationship and material conditions needed for study;
- `USEFUL_BRIDGE`: page and cue explain a necessary step or context that
  concretely helps study that exact relationship, even when another page
  states it more directly;
- `TOPIC_ONLY`: a term, introductory/transition slide or same subject without
  the information or bridge needed for the question;
- `IRRELEVANT`: unrelated to the question.

The prompt asks the judge to inspect **all four IDs** for additional useful
pages before returning exactly four labels, without a target number. The
strict local parser rejects missing, duplicate, foreign or malformed IDs,
labels or extra text. It selects the first at most three IDs labeled
`DIRECT_RELATION` or `USEFUL_BRIDGE` in issued order, with no padding.
Transport/schema failures yield a safe failure, not a fabricated no-match.
The user-visible text remains “related published Knowledge, not verified
answers”; no draft answer or claim verifier returns.

This is a hypothesis about improved multi-page recall, **not** a quality
claim. The broad `USEFUL_BRIDGE` class could admit a weak page. Therefore
freeze an immutable new policy/wire/parser/scorer and one-use ledger before
any score; test synthetic no-useful, same-topic hard negatives and 0/1/2/3/4
useful-page cardinality offline. Preserve every independently reviewed
66-case exposed calibration question and the existing availability, zero
false no-match, useful-hit, exact 5/6-per-stratum cardinality, 2/2 overflow,
and at least 90% usefulness across **all shown cards** gates. Only a full
calibration pass may open the sealed 60 different-PDF heldout once. A miss
stops the candidate. No re-labeling or score-based threshold tuning.

Even a public pass would not enable current dormant v4. Its page presentation,
prompt, response schema, selector, byte cap and hard-pinned `gemini-3.8-flash`
model differ. A matching versioned application policy, new migration after
`0029`, approved private-source transfer and independent original-PDF,
access, spoken accessibility and release measurement remain necessary.

The operator must first approve a Lane 6/ADR-024 amendment and keyless
prototype. A later public provider call needs a **separate exact**
endpoint/model/price/call/token/time/cost envelope, source freeze and
one-use receipt. This proposal does not reactivate or replay either failed
public pilot or allow its partial responses to satisfy a gate.
