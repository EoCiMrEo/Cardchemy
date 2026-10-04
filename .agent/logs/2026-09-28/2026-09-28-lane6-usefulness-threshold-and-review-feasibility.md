# Lane 6 usefulness target and repaired public-review feasibility

Date: 2026-09-28. Branch `main` at `6c02d6c`. The extensive existing
working tree, retained database volume, root `.env` and original PDF archive
were preserved. Ask remains disabled. This record covers a documented product
threshold and a read-only public-fixture check; no model score, provider call,
new indexing or retained-data mutation was made.

## Operator decision

The operator clarified that Ask source navigation may pass with measured
usefulness below perfection and selected **at least 90% useful across all
displayed citation cards** on the independent release set. The plan and
ADR-023 now specify the numerator/denominator and treat uncertain usefulness
as failure. Question-level hit@3 and no-match coverage remain separate, so a
system that suppresses every card does not pass. Fabricated, unauthorized,
private, stale or wrong-page references, unsupported answer claims and extra
provider requests retain zero-tolerance gates. This does not turn the
unverified related-reading label into an answer-sufficiency assertion or
authorize enabling Ask.

The public roadmap had still described ADR-022 as the current viewer policy,
the retained local containers as not cut over, and schema `0021`. It was
corrected against the documented `0028` retained cutover, three exact
original-PDF attachments, the enrolled-browser PDF repair and the still-closed
Ask release fence. The active Subject Knowledge flow also named the old
navigation-v2 admission policy; it now names the current v3 policy. An
independent docs audit found additional present-tense v2/v8 and `0027`
claims in provider/configuration, data model, Knowledge flow and deployment
guides. Those active descriptions now identify v3/v9 and `0028`, while
explicitly historical v2/v8 explanations remain. The Subject Knowledge flow
also clarifies that current Ask needs query embeddings only and makes no
answer-model call. No milestone was marked complete.

## Repaired public-review feasibility

Before asking independent reviewers to inspect 55 newly blinded candidates,
the pinned bridge maps were checked against only the two prior independent
reviews and their adjudications. The bridge admits unchanged judgments only
when question/context/template and exact source/page/offset/window identity
match; newly changed candidates were treated as unknown, never inferred from
author-proposed labels. All 96 train groups and both 48-group evaluation
splits still have four candidate slots; no carried group has more than three
known useful cues.

Train fixed known-count groups are 15/18/18/17 for counts 0/1/2/3, with 28
unknown changed candidates. Calibration has 12/12/9/12 fixed groups, with
three unknowns. Heldout has 6/9/12/12 fixed groups, with 24 unknowns. A
read-only bipartite group-to-stratum assignment found a mathematically
feasible 24-per-count train partition and 12-per-count calibration and heldout
partitions. This is **only an upper-bound feasibility check**: independent
PDF labels can still make the actual repaired fixture fail the preregistered
count balance. No reviewer decision or model output was written by the
calculation.

Two independent agents began blind review of the train delta, and another
began the evaluation delta, using original public PDFs only. A second
evaluation reviewer, adjudication, complete review bridge, per-document
rights and semantic receipts, fixture validation and the one approved
networkless public model audit remain pending. The stopped GTE audit is
unchanged. The owner-requested Ask release gate is still open.

## Independent delta review and first merge

Both train reviewers completed 28/28 changed candidates against ten rendered
public PDF pages. Both marked zero pages and zero exact cues useful; reviewer C
marked six cases uncertain and reviewer D marked three, with a union of six
requiring independent adjudication. A third reviewer resolved all six against
the original pages as not useful, with a separately checked adjudication
receipt. The bridge carried 356 unchanged judgments and 28 newly reviewed
ones into two complete train reviews, preserving 42 adjudicated rows. The
final train distribution is 24/24/24/24 groups with zero through three useful
exact cues; its bridge receipt SHA-256 is
`74503ffb012bdcf59df0f5a2b68a909a6a33ea16424e81ca27190f15b00b950e`.

Both evaluation reviewers independently completed 27/27 changed candidates
against nine distinct original pages and agreed on zero page/cue usefulness,
with zero uncertainty. A zero-row adjudication record was validated against
both complete review sets; it does not manufacture judgments. The provenance
bridge then carried 357 unchanged prior judgments and 27 new judgments into
two 384-row composite evaluation reviews, preserving 21 old adjudications.
The resulting calibration and heldout count distributions are each exactly
12/12/12/12 for zero through three useful cues. The composite review receipt
SHA-256 is
`22b6eaf14e112d5875e46d6f33e7a2c35e80f10293d9a346ecaf116bfec47372`.
These are review and fixture-admission facts, **not** Mixedbread quality
measurements. Final per-document rights and cross-split semantic
attestations, the 768-row candidate-rights receipt, validated fixture and
frozen hashes are still required before any inference.

## Source-only negative regression

An independent backend audit found a missing malformed-query-vector boundary
test and added only
`backend/tests/test_rag_source_only_negative_gate.py`. Five parameterized
provider outputs (empty, multiple, short, non-finite and zero vectors) now
exercise the real v3 worker/retriever path. Each must fail terminally after
one physical request with no lexical fallback, partial references or
assistant message. The focused suite passed 69 tests. The full keyless backend
offline suite passed **2,193**, with 147 skipped and two live cases
deselected. Existing tests cover the other owner/enrollment, publication,
revision/space, whole-bundle, stage-cap and PDF-range boundaries. These
technical tests do not prove usefulness, browser spoken accessibility or
live-provider behavior.

## Verification and limits

The read-only check consumed the existing 28/27-candidate bridge maps and
prior adjudicated review rows; it printed aggregate counts and a feasible
assignment result for train, calibration and heldout, without public lecture
text or private Knowledge. `backend/venv/Scripts/python.exe
scripts/check_context.py` passed (37 required files, 78 active guides,
1,404 local links after the roadmap and flow corrections). `git -c
core.safecrlf=false diff --check` exited zero. The new independent labels
determine the next step; no inference may run solely on this feasibility
result.
