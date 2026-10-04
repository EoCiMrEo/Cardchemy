# Recommendation: anchor-first coverage for source-only Ask

Date: 2026-09-30 (America/Chicago). **Proposal only.** The Lane 6 plan,
ADR-024, runtime and provider caller have not been amended for this candidate.
This note authorizes no download, Gemini request, private Knowledge transfer,
reindexing, DB write or Ask activation.

## Evidence and actual failure mode

The approved public categorical pilot was interrupted after 58/66 valid
calibration responses. Its read-only [aggregate analysis](2026-09-30-categorical-public-pilot-interrupted-and-rejected.md)
found 65/70 displayed cards useful and 0/12 false no-match displays but
missed the frozen multi-page/overflow gates. Of 88 independently reviewed
useful cue-plus-page candidates, 23 were omitted because the judge labeled
20 `TOPIC_ONLY` and three `IRRELEVANT`. No useful page was dropped by the
three-page display cap or issued order. Reclassifying all `TOPIC_ONLY` pages
would add 40 weak pages for only 20 useful ones.

A private-content-free review of the 23 **public** false negatives found
16 supplemental useful pages across 11 questions where another useful page
was already selected, and seven pages from two questions where the needed
explanation is distributed across several individually useful pages and the
judge selected none. These are observable patterns, not proof of the model's
internal reason. Just one missed cue hit the 480-character cap, so simple
truncation is not the dominant observed issue. An instruction that calls a
bridge "necessary" may be too narrow for a page that independently helps
student reading, but rewording alone has no measured assurance.

## One bounded architecture candidate

Retain one current-question query embedding, at most one bounded source-ID
judgment, zero generated answer/verifier calls, zero automatic retry, and
0–3 original-PDF references visibly labeled unverified related reading.
Change **the decision representation**, not the quality threshold:

1. From each current authorized candidate page, deterministically derive a
   small ordered set of page-local, exact **reading anchors**: heading plus
   adjacent bullet, sentence, formula caption or worked step. Every anchor
   has a server-issued opaque ID, exact page offsets and a ≤480-character
   display slice. Do not infer or rewrite a claim. Keep the whole request
   within the existing four-page public and prospective runtime budgets.
2. In one judgment, ask the model to inspect **every issued anchor on every
   page independently**, even when another page is stronger. It returns only
   anchor IDs that concretely help study the question's named relation and
   material conditions; an empty list is allowed. It must not draft an answer,
   invent a quote, compare against a target count or use outside facts.
3. The local parser checks IDs, page/offset containment, no duplicates,
   output/token budgets and exact immutable source binding. Group selected
   anchors by page, then display at most three distinct pages with their
   exact selected slices in deterministic order. Never add a weak page to
   reach two or three. Transport, schema, stale-source and missing-PDF states
   remain separate from a genuine no-match.

An exact anchor pointer proves provenance, **not usefulness**. The candidate
must still meet the unchanged independent 90%-of-**all-displayed** cue+page
usefulness, zero false no-match, positive hit, exact 5/6 selection per
one/two/three-useful stratum, 2/2 four-useful overflow and availability
gates. The 66 exposed public questions are development/calibration material;
the 60 different-PDF heldout remains sealed until a frozen full calibration
pass. The independent private original-PDF release holdout and access,
privacy, browser, spoken accessibility and operational gates remain separate.

## Go/no-go before any paid pilot

First run a **keyless public-only feasibility audit**, with no runtime or
provider change. Use exposed calibration pages to derive anchors before
looking at the current model label for that page; bind every anchor to page
text and a ≤480-character visible slice. Have an independent evaluator
inspect original public PDFs and the exact anchors, including the 23 missed
useful pages and the 40 weak `TOPIC_ONLY` pages. Report coverage by
question form and 0/1/2/3/4 useful-page count, anchor-cue/page fidelity,
how many missed useful pages could be represented, how many weak pages look
deceptively plausible, wire/token bounds and latency. If anchors cannot
represent the gold-useful relations within budget or fail to distinguish
hard negatives, stop before a paid experiment. No retrospective relabeling
of the frozen gold is allowed.

A read-only feasibility baseline over all 66 exposed calibration questions
found 109 independently useful and 155 non-useful cue-plus-page candidates.
Every existing cue is multiline (median about 12 lines in both classes), so
structural segmentation is available but does not itself discriminate the
classes. Simple question-token overlap with a cue is zero for **16/109**
useful candidates and **70/155** non-useful ones. Therefore a lexical-only
anchor prefilter would delete genuine paraphrase positives; the prototype
must preserve a full exact-cue fallback or use semantic/structural units and
measure coverage explicitly. This observation is not model quality evidence.

Only after this feasibility evidence and operator-approved Lane 6/ADR-024
amendment may a separate versioned wire, parser, scorer, one-use ledger and
synthetic controls be implemented. A later public provider run needs a
**fresh exact endpoint/model/price/call/token/time/cost envelope**. The
interrupted categorical approval and stronger-model ledger stay consumed;
partial responses cannot be replayed or promoted. Even a public pass cannot
activate dormant v4, whose model, candidate count, wire and selector differ;
a matching migration/policy and independent private release proof are needed.
