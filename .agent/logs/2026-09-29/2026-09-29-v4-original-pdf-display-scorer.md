# Dormant v4 original-PDF displayed-card release scorer

Date: 2026-09-29 (America/Chicago). Branch `main` at `6c02d6c`. This is a
keyless, content-free evaluation-contract slice under accepted
[ADR-024](../../../docs/decisions/ADR-024-gemini-source-id-judge.md). The
existing working tree, populated volume, root `.env`, original PDFs and Ask-off
release fence were preserved. No provider call, database read/write, private
lecture read, holdout opening or model score occurred.

The public two-PDF scorer already counts every selected cue and original page
on its frozen public roster. The historical private
`scripts/score_source_first_display.py` instead uses the v3 displayed-window
contract and does not distinguish v4 source-judgment calls or require a frozen
independent usefulness label for every exact page/cue pair in the judge slate.
The new `scripts/score_source_judgment_display_v4.py` supplies a separate
**dormant private release scorer**, without changing either existing scorer or
the Ask runtime.

The v4 scorer requires four OS-Temp-only input artifacts with externally
supplied byte hashes **for each separate component**: an exact pre-judge
case/candidate roster, independent original-PDF page **and exact cue** labels
for every issued candidate, an Ed25519-signed freeze receipt over their hashes,
stage-1 question/gold-packet hash and runtime identity using a separately
pinned trusted reviewer public-key digest, and the later ordered runtime
display observation. It checks freeze timestamps. The `exposed_seed` component
has eleven historical positives, N12/U01 and at least two no-match controls;
the `private_holdout` component has twelve independently prepared positives,
four per question form. A component alone can **never** report release pass.
`score_release` requires both separately signed components, the same runtime
identity, distinct stage-1 packets and no gold-page overlap, then checks
the aggregate 90% threshold. It can report `display_quality_gate_passed`,
but always leaves `release_gate_passed=false` because accessibility,
operational safety and publication gates are separate. A
selected card must exactly match an issued page/cue identity. `Unsure` counts
as non-useful, as does a failed exact-cue, page-association, current-access,
revision, Subject or opened-original-PDF check. Every displayed card enters
the same denominator. The content-free result reports 10/11 exposed and 10/12
holdout hit gates, at least 3/4 per holdout form, at least 90% useful among all
shown cards, explicit no-match numerator/denominator, control weaknesses,
fabricated/wrong-page and unauthorized/stale/cross-Subject counts, actual
physical-call counts against v4 limits, and a release-gate boolean. Its default
CLI is a no-input preflight; executing it later needs explicit Temp paths and
hashes. This is a local scorer, never a source-ID judge or answer generator.

Focused synthetic tests in
`backend/tests/test_source_judgment_display_v4_score.py` passed **15/15**.
They cover the exact positive/no-match aggregate, Unsure, extra weak cards in
the denominator, negative display, provider failure, incomplete labels,
unissued/duplicate cards, excessive judge calls, PDF-open failure, changed
freeze/runtime identity, untrusted/invalid signatures, separate-component
release aggregation, gold-page overlap rejection, exact Temp-byte CLI
admission and default preflight.

No real v4 observation was scored. The first-stage fresh private question/gold
packet is being frozen independently; its exact schema/bytes have not yet been
bound into the later slate scorer. A signature and frozen hashes establish
input immutability under a separately trusted reviewer key; they cannot prove
reviewer independence, semantic usefulness, actual browser rendering or the
producer's truthfulness by themselves. The release procedure must independently
verify those facts, original-PDF provenance and the producer's exact runtime
identity before treating a later passing aggregate as evidence. Public source-ID
pilot availability and private Knowledge transfer gates remain separate. Ask
stays disabled and Lane 6 remains **3/7**.
