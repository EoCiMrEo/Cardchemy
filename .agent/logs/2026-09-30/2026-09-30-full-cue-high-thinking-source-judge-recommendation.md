# Recommendation: one full-cue, higher-thinking source-judge comparison

Date: 2026-09-30 (America/Chicago). **Proposal only.** This record does not
amend Lane 6 or ADR-024, approve a Gemini request, change the runtime, open
heldout/private data, reindex, write the database or enable Ask.

## Evidence that narrows the next variable

The completed [anchor feasibility audit](2026-09-30-anchor-first-public-pdf-feasibility-result.md)
rejected concise page-local snippets before paid testing: only 14/23
previously missed useful pages had a useful short anchor, while 32/40 weak
same-topic pages still looked plausibly relevant. The exact old full cue was
independently helpful for 19/23 of those misses. Two other useful relations
were graphical and absent from its extracted text. The current categorical
source judge had labeled 20 of 23 missed useful pages `TOPIC_ONLY` and three
`IRRELEVANT` while selecting 65/70 actually useful displayed cards in its
58 observed public calibration groups. This points primarily to a **page
relation decision gap** on the exposed data, with a smaller representation
gap; it does not prove the model's internal cause.

A read-only sensitivity check of those same frozen receipts showed that
relaxing exact useful-ID selection alone is insufficient: even a hypothetical
requirement of two useful pages when two or more exist would be met in only
13/16 two-useful, 5/10 three-useful and 1/2 four-useful groups. Retain the
approved gates and do not pad the student display with weak sources.

## One bounded candidate

Keep the four **full exact public page cues**, the same question, candidate
order, categorical labels and strict local selection rule; retain at most
one current-question embedding, at most one source-ID judgment and zero
answer/verifier calls or automatic retries. The only model-behavior change
to test is `gemini-3.5-flash-lite` with `thinkingLevel=high` rather than
the failed low-thinking pilot. Its permitted output cap may rise from
1,024 to 2,048 **including thinking tokens** so a valid four-label JSON
result can finish; this is a predeclared compute-budget change, so the
comparison cannot isolate thinking from output-cap effects. Source text
is never rewritten or converted to an answer. The app remains source-only,
showing 0–3 current authorized original-PDF pages visibly labeled as
unverified related reading, with no weak padding.

Google's current [thinking guide](https://ai.google.dev/gemini-api/docs/thinking)
lists `high` for Gemini 3.5 Flash-Lite. Its [pricing page](https://ai.google.dev/gemini-api/docs/pricing)
lists Free-tier standard input/output at no charge and Paid-tier rates of
USD 0.30/2.50 per million input/output tokens; Free-tier submissions may
be used to improve Google products. Model availability and actual cost
must be rechecked immediately before any separately authorized live pilot.
The earlier Gemini 3.5 Flash pilot returned three HTTP 503 responses in ten
calls; this candidate must also pass the unchanged availability gate.

## Order and stopping rules

1. With owner approval for a **plan/ADR amendment and keyless preparation
   only**, version a distinct high-thinking public wire and failure-inclusive
   scorer. Freeze exact code/packet/labels, one-use ledger and pricing guard;
   test four-page source binding, foreign/duplicate IDs, malformed/unfinished
   output, empty versus transport failure, zero/one/two/three/four useful
   cases, no weak padding and no answer text. Preflight all 66 exposed
   calibration requests without a provider or private transfer. Make the
   caller durable across tool-session interruption without replaying a
   consumed request. The old categorical ledger remains consumed.
2. **Only after a separate exact endpoint/model/price/call/token/time/cost
   approval**, run one public-only calibration. Keep all 66 original frozen
   questions and labels. Stop early if the old release gates become
   mathematically unreachable or the allowed transport failures are
   exceeded. Timeout/503 counts as a failed case, not no-match; no retry.
   Score useful displayed page+cue among **all** shown cards, positive hit,
   zero false no-match, exact 5/6 per one/two/three-useful stratum, 2/2
   four-useful overflow and availability. Disclose numerators/denominators,
   latency, usage and uncertain cost. Do not tune on this result.
3. Open the 60 different-PDF public heldout **once** only if all frozen
   calibration gates pass. A public pass still cannot activate the current
   `gemini-3.8-flash` v4 application: model/thinking/wire policy must be
   versioned in a new migration after `0029`, separately approved private
   content transfer and independent original-PDF usefulness, access,
   spoken accessibility, release and rollback checks must pass. A public
   failure ends this candidate; it does not authorize weaker gates or
   further prompt variants.

This is the smallest available controlled test of whether more reasoning
can recover useful full-cue pages without admitting weak pages. It is an
unproven candidate, not a promised solution. If it fails, reassess the
automatic source-selection architecture with the full failure record rather
than continuing unbounded prompt tweaks. Lane 6 remains **3/7** and Ask
remains disabled.
