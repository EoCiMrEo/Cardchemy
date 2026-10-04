# Public reading-usefulness v4 repair: rights and split preflight

## Scope and preservation

On 2026-09-28, after the first independently reviewed fixture failed admission,
two author-only replacement drafts and separate blind packets remained in OS
Temp. This pass inspected the public CC BY 4.0 PDF corpus and the revised
questions without inspecting proposed source-usefulness labels or running the
Mixedbread scorer. No private Knowledge, retained database, Gemini endpoint or
indexing path was used. The populated volume, root `.env`, and Ask shutdown
remained intact.

## Exact-source delta

The revised 192 groups still contain 768 candidate rows. Comparing source
document SHA, physical PDF page, extracted-text offsets and exact-window SHA
against the earlier candidate-rights preassessment gives **734 identical
source windows** and **34 new rows representing 12 distinct windows on 12
pages**. All 734 identical windows had all three preliminary rights checks
true. The old group-ID comparison counts 55 changed review candidates; 21 of
those use an unchanged exact source window with a changed question or opaque
review identity. None of the nine previously flagged lecture-32 candidate
rows survive unchanged. This does not carry source-usefulness judgments to
changed questions.

All 12 pages with new exact windows were rendered from the pinned public PDFs
and visually inspected. Their selected windows are lecture text, bullet,
formula or heading material; no selected window copies a raster image, figure
or separately credited media. Two pages have embedded raster resources and
some others have vector diagrams or small icons, so this is a **candidate-text
preflight**, not a blanket declaration about rights in page media. The 14
source PDFs' first-page CC BY 4.0 notices and source attribution were already
checked in the earlier preassessment. The fixture must preserve that
attribution. Final 768-row rights attestation remains pending until the
reviewed fixture and its group hash are frozen.

## Split preflight

The revised sources partition into six train, four calibration and four
heldout PDFs, with no PDF shared across splits. The old three-form heldout
absent-accuracy topic was replaced by a different three-form scalar-label
topic. A read-only review of the 64 representative concept questions and the
top thirty cross-split lexical/sequence-overlap pairs found no apparent
duplicate concept or paraphrased target across splits. The highest string
similarities were generic question stems about different entities (for
example, different acronym expansions), not the same requested fact. This
screen is not the required independent 192-group semantic leakage attestation;
context-bearing follow-ups and exact page-text leakage must still be reviewed
against the final group hash.

A further read-only comparison extracted the **159 selected public PDF pages**
and checked all **8,184 cross-split page pairs** for common five-word
sequences. The maximum containment of the smaller page's five-word set was
0.046 (three adjacent generic phrases); only six pairs shared any five-word
sequence. The shared phrases described generic training/value/probability
language, not a repeated worked example or target fact. This strengthens the
preflight but remains distinct from the final signed semantic attestation.

## Verification boundary and next work

The comparison was read-only over pinned local public files; 12 selected PDF
pages were rendered with Poppler and visually checked. No author label was
promoted, no new blind judgment was made, no model score was computed, and no
Lane 6 checkbox changed. Two independent reviews of the 55 changed public
candidates, adjudication, final rights and semantic receipts, and fixture
admission remain prerequisites for the approved one-shot offline audit. Ask
remains disabled.
