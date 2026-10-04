# Existing generation: independent teaching review

## Scope and authority

Continue the approved Lane 6 evaluation using the existing twenty-card result
prepared by the [read-only export](../2026-10-02/2026-10-02-existing-generation-review-preparation.md).
The owner requested autonomous evaluation instead of more human page-review
packets. This review made no provider request, database write, instructor
approval, or change to a stored card, source PDF, root configuration or volume.

Starting checkout: dirty `main`, HEAD
`6c02d6cf063acf83f4da5c08cfc4a3aa2c94be57`. Read root operating guidance,
orientation/maps, the AI generation architecture and ADR-006, relevant Lane 6
requirements and dated generation evidence. Used the PDF skill's local
render-and-inspect workflow. Existing changes were preserved.

## Exact sample and method

Verified the owner-private packet SHA-256:
`288c8a2736ac20b7872eca38c0f7459128b03b99acd071da6b62d2c857d77a19`.
All twenty cards belong to one historical completed twenty-card job. The
exact source PDF was found locally by its full SHA-256, rather than trusting
filename metadata. It has thirty-two physical pages; the sample uses nineteen
distinct pages. All twenty stored cards remain unapproved.

Rendered every referenced original page with local Poppler and inspected all
twenty review panels, each displaying the question, canonical answer, four
options and stored snippet adjacent to the complete original PDF page.
Checked source association, question/answer scope, sound answer selection,
learning usefulness and semantic duplication. Separate deterministic checks
validated canonical shape, exact answer-option matching, normalized snippet
containment in both the stored canonical page and original PDF text, and
answer containment in the snippet. Text containment was not treated as proof
of teaching quality or mathematical fidelity.

Finite per-card labels, source bindings and render hashes remain in private
Temp. No question, answer, option, snippet, document title or private identifier
is included in tracked evidence.

## Observed aggregate results

| Criterion | Pass | Revision needed |
| --- | ---: | ---: |
| Canonical four-option format and answer matching | 20/20 | 0 |
| Exact original-source hash and physical page | 20/20 | 0 |
| Quote location/association | 20/20 | 0 |
| Canonical answer faithful to original visual PDF | 19/20 | 1 |
| Question/answer scope and sound correct option | 18/20 | 2 |
| Useful learning task | 18/20 | 2 |
| Semantically distinct learning task | 19/20 | 1 |
| Useful and semantically distinct task together | 17/20 (85%) | 3 |

There were no exact normalized duplicate question strings. Semantic review
nevertheless found one pair that tests substantially the same learning fact;
only one member is credited as distinct. The two revision-needed teaching
tasks comprise one example-specific answer attached to a broader question
and one extraction-damaged mathematical expression copied into the answer.
One very short quote also requires its original page context; its page
does support the question. No label is `Unsure` in this sample.

This is an independent agent review, not an instructor approval action.
The three flagged cards were not edited, removed, approved or published.
The findings illustrate why structural grounding remains necessary while
instructor review still owns editorial approval under
[ADR-006](../../../docs/decisions/ADR-006-grounded-generation-validation.md).

Private independent-label SHA-256:
`ebbf35262aee520ff121429e6ba1e29373898c561f98abbd45b978a4ccf58a1f`.
Private machine-check SHA-256:
`495b443f63603c421835d92790b66fba216a75bdd544fd03e87ff3c99ea8f7b5`.
The original packet remained byte-for-byte unchanged after review.

## Historical job snapshot and limits

The exported result records `gemini-3.5-flash-lite`, twenty requested and
twenty generated cards, three `card_generation` physical requests, 12,534
input tokens, 2,873 output tokens, and USD 0.010943 recorded cost.
`usage_estimated=false` describes the stored usage snapshot; that flag and
the cost field do not constitute a provider invoice or account-wide ledger.
The attempt-quality list is empty, so raw/rejected/refill-stage yield cannot
be reconstructed from this packet. Its export does not contain the historical
prompt/catalog/grounding-policy versions needed to claim a version-matched
run of today's pipeline.

This retained thirty-two-page, three-request result is distinct from the
September 25 diagnostic that used forty-two pages, four requests and twenty
RAM-only cards without persistence. No old RAM-only card content was
reconstructed. Selecting one already completed job does not establish a
generation success rate or a representative attempts denominator.

No new live yield, current-policy generator success, genuinely sparse
published whole-source result, or release pass is claimed. Existing
deterministic sparse/partial-choice evidence retains its own narrower scope.
Ask enablement and the remaining Lane 6 gates belong to the root task.

## Preservation and verification

- Twenty card panels and all nineteen referenced original pages inspected.
- All six deterministic checks passed for every card; teaching labels above
  were derived separately from visual source comparison.
- Zero network/provider calls, new AI spend, database writes or approval changes.
- Packet, original PDF and existing application data preserved.
- Private review artifacts retained for root audit; no temporary database or
  container was created by this review.
- Documentation-only evidence added; no runtime source or test behavior changed.

