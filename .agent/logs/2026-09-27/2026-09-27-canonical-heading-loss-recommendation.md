# Canonical heading loss: source-unit recommendation

Date: 2026-09-27. Scope: provider-free investigation of Lane 6 source
sufficiency, after the operator delegated future evaluation to engineering
agents. This is a concrete recommendation awaiting the operator's required
architecture/plan approval, not implemented runtime behavior.

## Starting context and authority

The source-only Ask policy, eight relation families and existing quality and
resource gates remain approved. Ask is disabled; no answer model or answer
verifier may return. The operator requested no further source review packets.
An independent agent inspected original PDFs without reading the runtime
selector and froze twelve sufficient cases (four in each question group,
twelve new pages, three documents) and sixteen insufficient controls (two per
relation). Existing owner labels were preserved. Exact private content and
review artifacts remain in OS Temp, outside tracked fixtures and logs.

## Measured defect

Two current authorized read-only snapshots found all **28/28** reviewed spans
on their canonical extracted pages. Only **1/12 sufficient** and **2/16
insufficient** spans occurred wholly in current indexed chunk content.
Independent comparison established **25/28 owning-heading omissions**, with
every remaining body intact in one chunk, **zero split cases** and **zero
body-loss cases**. All thirteen involved pages have one current chunk.

`backend/app/ai/chunking.py::_page_units` removes a recognized first-line
heading from chunk text and retains it only as section metadata. The approved
v4/v5 source-unit rule requires the owning heading and predicate in the same
actual chunk. It therefore cannot select many useful title/body excerpts even
when the complete original evidence survives on the canonical page. This is a
verified representation/source-window defect, not evidence about model quality.

A separate offline heading-retention prototype, at the current 1,200-token
chunk/120-token overlap budgets, restored exact contiguous coverage for
**12/12 sufficient** and **16/16 insufficient** spans. All rebuilt chunks fit
the budget. This measured source coverage only: the selector was not run on
these new cases, no index or runtime changed, and no retrieval/display/page-open
quality gate passed. The earlier development set still produced only **2/9**
useful-source selections on v5, so heading restoration alone does not establish
adequate qualification or ranking.

## Recommended amendment: exact canonical-page evidence units

Retain current vector/FTS retrieval as candidate discovery. For an authorized
retrieved chunk, load its current canonical extracted page through the same
Subject/publication/revision/space predicates. Qualify a contiguous exact
owning-heading/body span from that page only after proving the chunk body and
section belong to the page. Do not concatenate section metadata and body into
pretend source text. Keep entity, explicit relation, all qualifiers, exact
480-character spans, three references, and cumulative 30-chunk/12-page/
8,192-token inspection limits, counting inspected page units in that budget.
Insufficient/partial evidence still cannot be primary.

Add a versioned source-unit policy and an additive Alembic reference contract
with an explicit `canonical_page` source kind and exact page offsets; preserve
historical chunk-offset references under their old source kind. Retain the
eligible chunk as a discovery anchor, not a false quote container. At commit
and every read, reauthorize the anchor and page/revision, validate exact offsets
and expiry, and hide the entire bundle on drift. Page-open highlighting must
use those exact page offsets. No copied source text is stored in references.

This avoids changing indexed representation or making paid reindex calls to
recover evidence already present locally. A structured, versioned chunker and
staged reindex remain a later option if retrieval itself misses owning context;
that requires its own reviewed cutover and paid envelope. No new remote model,
reranker, answer/verifier call, retry, or embedding-space change is proposed.

## Verification and limits

Before activation, compare current versus new source coverage, qualification
and displayed windows on the frozen twelve-positive/sixteen-insufficient set;
have the independent reviewer label every actually selected span separately.
Retain all existing seed, holdout, access, no-fabrication, page-open, maintained
retrieval and release thresholds. Add transaction/source-kind migration,
stale-read, wrong-heading/neighbor, cross-Subject/unpublished, budget and expiry
controls. Keep Ask off until all required gates pass. Any later paid query
embedding evaluation needs a fresh endpoint/model/token/time/cost envelope.

No provider requests or database writes occurred during this investigation.
The temporary binding harness first lacked the application import path; it
failed before SQL and was rerun with an explicit `/app` path. Two snapshots
then agreed. The new source roster remains independent of runtime tuning.
The current user instruction requires approval before changing the plan's
source representation; this recommendation does not silently broaden it.

## Independent registration and cleanup

The aggregate scorer now has explicit independent-review v2 schemas. It binds
original artifact bytes/hash, exact question/page/relation/quote identity,
reviewer identity and freeze/measurement/review ordering; owner flags remain
false. Original lowercase labels are accepted only as the exact all-Yes
meaning, with mixed/No/unknown/boolean controls rejected. **90 scorer/display
compatibility tests** passed; the combined scorer/display/selector/source-only/
telemetry run passed **232 tests**. Legacy owner-review support and all gates
remain intact.

The twelve original-reviewed PAGE gold cases were registered before runtime
measurements with 4/4/4 groups. Prior artifact bytes independently prove
61 earlier exposed pages; five additional seed exclusions were reauthorized
in the canonical binding, bringing source-discovery exclusions to 66. Only
one gold source has current full chunk coverage. Registration explicitly
claims neither runtime evaluation nor a quality pass; the complete sixteen
original-reviewed controls are retained but not executed as chunk controls.
The first registration refused an original lowercase-label mismatch before
freezing; the corrected strict verifier preserved original bytes and passed.

Private binding/snapshot/review/prototype/preregistration evidence remains
under owner-private OS Temp for continued evaluation. The owned container
diagnostic directory was removed after those artifacts were copied. Context
validation passed (37 required files, 77 guides, 1,288 links) and normal
`git diff --check` passed. An attempted line-ending override for that check
misclassified existing CRLF files; no files were changed by it and the normal
repository configuration was used for the passing check. No new provider
spending, root settings changes or data/volume reset occurred.
