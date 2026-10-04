# Recommendation: source-navigation release metrics

Date: 2026-10-01 (America/Chicago). **Proposed only.** No scorer, label, prompt,
gate, runtime or provider authorization is changed by this document.

The [visual trial](2026-10-01-visual-source-public-calibration-result.md) stopped
after four valid calls: complete two-page selection can reach only 17/21 against
18/21 required. One group adds a weak page, another omits a useful page. Partial
precision is 4/5; full 90% usefulness remains unmeasured. Do not relabel these
errors or claim that a changed gate would already pass.

## Contract decision

The owner's product contract is **0–3 useful unverified original-PDF reading
references**, no weak padding or generated/complete answer. A useful page may
teach one concrete learning step. The owner set **at least 90% useful over all
displayed cards**. The additional exact-set gate requires selecting every useful
page in most multi-page slates, making a missing second useful page a release
failure even when the returned page is useful. Whether that completeness belongs
in this navigation product requires an explicit decision.

## Proposed narrow amendment and offline preparation

1. Keep architecture, one embedding maximum, at most one source-ID judgment,
   zero retries, exact current authorized source/PDF identities, no answer,
   no weak padding, and all privacy/security/resource/cost boundaries.
2. Keep public calibration **45/54 positive hits, 15/18 per form, 65/67 valid,
   at most two errors, all 12 clear no-match groups valid and empty, and at
   least 90% useful across every displayed card**. All 67 groups, hard cases,
   original labels and unknowns remain; uncertain selections get zero credit.
   Independent release still needs hit 10/12 and 3/4 per form, 90% usefulness,
   original-page-open, access and all release gates.
3. Record exact-set/cardinality, omitted pages, second/third useful-page recall
   and weak selection as **separate diagnostics**, instead of requiring exact
   selection of every useful page to release source-only navigation. Full
   calibration and independent different-PDF holdout remain mandatory.
4. Prepare a separately versioned scorer and checkpoint admission **offline**.
   Preserve the stopped result/ledger and unchanged prompt. SHA-bind the four
   existing valid receipts to their original inputs and retain them only as
   calibration data. Never resend those four groups. The other 63 requests
   stay unattempted until a fresh explicit provider envelope is approved.
5. No new Gemini call, download, private source read, heldout opening, runtime
   change or Ask activation in this offline amendment. Do not tune prompt/labels
   from the partial run. If exact-set completeness is still required, retain
   the gate and propose a different selector under a separate approval.

The original task requires approval before plan changes. This changes an
approved quality obligation; generic continuation or unused stopped-pilot
budget cannot authorize it. The proposal preserves the owner's 90% target,
all difficult cases, clear no-match/availability/privacy/security boundaries.
It is not a measured pass, a claim of complete remediation or permission to
enable Ask. Future public/private/heldout calls need specific cost envelopes.
