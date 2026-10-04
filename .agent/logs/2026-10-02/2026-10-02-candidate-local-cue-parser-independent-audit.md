# Independent audit of candidate-local cue conflict handling

## Scope and authority

Root requested a bounded read-only audit after public heldout v10 stopped at
Q056 with the repeated finite diagnostic `cue_without_useful_page`. No key,
provider, network, private Knowledge, database or runtime operation occurred.
The audit changed no existing source, receipt, claim, failure or frozen input.
The prospective module reviewed is
`backend/app/ai/source_judgment_visual_v4.py`; it is not runtime integration or
Ask enablement. This aggregate record was subsequently requested by root.

## Cause and conservative repair

Application v2/v3 delegate verdict parsing to immutable v1; the public v2
prototype likewise delegates to its v1 parser. The old cross-field guard
rejects the entire response when a known nonqualifying page has a positive cue
flag. Positive selection already independently requires a qualifying category
AND a true cue flag. V4 locally sets only that contradictory negative-page cue
flag to false and then revalidates the entire object through strict v3.

The review found no blocking issue. Unknown fields/IDs/labels, duplicate keys,
wrong types, malformed/oversize JSON and contradictory clarification remain
whole-response failures. Later malformed rows cannot be hidden by an earlier
cue conflict. `needs_clarification` with any qualifying category still fails,
even when its cue flag is false. Direct-before-context ordering and the
maximum of three issued IDs remain unchanged. Request construction and usage
validation are the exact existing v3 functions.

## Checks actually performed

- In-memory AST clones of the original application/public parsers removed only
  the precise cue cross-field rejection. This changed no source file.
- Application enumeration covered 22,220 combinations: every one-to-four-page
  roster, five labels, two Boolean cue flags and both question statuses. All
  2,920 legacy-valid results were identical; 9,744 additional accepted results
  selected no nonqualifying page. Clarification contradictions stayed rejected.
- Public fixed-four-page enumeration covered 20,000 combinations. All 2,482
  legacy-valid results were identical; 8,814 additional accepted results
  selected no nonqualifying page.
- Thirty malformed inputs and seven invalid issued rosters per original parser
  retained their rejection behavior. Only the intended cue conflict differed;
  subsequent clarification contradictions remained failures.
- The actual prospective production v4 was independently enumerated over the
  same 22,220 application combinations: 2,920 old-valid exact equivalents,
  9,744 newly accepted conservative outputs and 9,556 clarification rejections.
  Its request/usage aliases were checked by Python object identity.
- Sanitized successful receipts from calibration v2-v5 and heldout v1-v10 were
  checked against their claim/request SHA bindings. All 118 successful verdicts
  (65 calibration, 53 heldout) preserved exact selected IDs, question status and
  page judgments under v4, with `excluded_cue_conflicts=0`. Receipt and claim
  bytes were unchanged before/after inspection. Frozen legacy caller hashes and
  the existing v10 observer SHA matched.
- All 20 physical failed receipts in those two lineages stayed failed and
  unreconstructed. No raw-response recovery or retrospective credit occurred.

These are offline equivalence/safety observations, not new provider results or
independent model-quality success. Existing v10 still has 53 valid active
outcomes, 81/86 useful displayed cards, four untouched questions and a failed
availability/completeness gate. The recorded public lineage guard cost remains
USD0.746052 plus uncertain historical charges; no spending occurred here.

## Reuse and remaining gate

Existing strict-valid results can be carried unchanged with explicit mixed
parser lineage and this equivalence proof. Failed results cannot be reconstructed
or credited because their raw responses were never retained. A prospective
parser trial needs fresh exact authority and actual Q056/Q057-Q060 outcomes.
No exception may be converted into a valid empty/no-match result. A structurally
valid clear result with zero eligible pages means only no selected reference in
the supplied candidate set, not corpus-wide absence. Existing no-match labels,
fixed denominator, usefulness/hit/availability gates and historical physical
failure reporting remain applicable. Ask remains off.
