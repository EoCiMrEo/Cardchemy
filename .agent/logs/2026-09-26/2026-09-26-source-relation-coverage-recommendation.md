# Source-only relation coverage recommendation

Date: 2026-09-26. Status: owner approved supplementation and implementation.

The owner approved the proposal below after review. Lane 6 and ADR-022 now
record the two additional families and sixteen-pair gate. Implementation is
versioned as `hybrid_source_sufficiency_v3`/`source_relation_units_v3`; approval
does not establish quality or enable Ask.

## Verified context

The accepted Lane 6 path is source-only: one current-question embedding at
most, no draft answer, no answer model or answer verifier. Its six declared
relation families are acronym expansion, definition, mechanism, measurement,
reason and process. Ask remains disabled behind the independent release fence.

The existing eleven owner-reviewed seed questions include information-loss or
limitation questions and domain-application questions. Their source labels are
positive, but those intents are outside the declared families. The current
descriptor either returns unknown or parses an application request as a
definition of a longer noun phrase. The corresponding paraphrases remain
unrecognized. This is a coverage defect, not proof that the published corpus
lacks the requested evidence. The seed gate of ten useful hits out of eleven
cannot be claimed from six-family synthetic tests.

The latest independent review packet is also not a quality pass: three
positive candidates were excerpt/page Yes, six No and one had no reported
label; five insufficient pairs were No. Source-fidelity labels were omitted.
All supplied labels are retained only in the owner-private Temp packet. A
local comparison of the six rejected positive excerpts matched each to one
original lecture PDF page. Visual inspection showed recap/transition pages,
another metric's definition, or source material without the requested
definition/process. Thus source identity and semantic sufficiency are
different checks. No private text or filename is retained here.

Source discovery also imposed an unnecessary two-positive-per-relation
sampling rule. The approved gate requires four direct, four paraphrase and
four follow-up positives, plus at least two insufficient pairs per declared
relation with sufficient controls. It does not require exactly two positive
holdout questions per relation. That builder constraint is being repaired
without changing the approved thresholds or promoting labels.

## Recommended amendment

Add two explicit question/source relation families within the same source-only
architecture:

1. **Property or limitation:** preserve the requested property, polarity,
   conditions and comparison. A complete entity-bound unit must state the
   requested loss, retention, sensitivity or limitation. A topic mention or
   another entity's property cannot qualify. Negative wording can be the
   requested evidence; it must not be rejected merely for containing `not`.
2. **Application or example:** require the requested entity and an explicit
   application/example/domain association in one current exact source unit.
   Generic application headings or other entities' examples cannot qualify.

Where the canonical chunk already contains the needed context, inspect an
exact contiguous heading-plus-bullet/continuation unit, at most 480 characters.
Retain owning-heading boundaries so a neighboring bullet for another entity
cannot inherit the relation. This is local source selection, not generated
text. Only propose versioned chunking/reindexing if the necessary context is
actually absent from the indexed canonical chunk.

Keep top-twenty first-stage retrieval, the cumulative 30-chunk/12-page/8,192-
token inspection bounds, at most three exact references, current source-read
authorization, zero automatic retries and no answer/verifier calls.
Version the changed selection semantics before execution.

## Evaluation and limits

Retain seed hit@3 at least 10/11, independent holdout sufficient/openable hit@3
at least 10/12 and at least 3/4 per question group, all existing first-window,
irrelevant-window, retrieval and access gates. Increase the independently
reviewed insufficient-pair minimum from twelve to **sixteen**, at least two
for each of the eight relation families with sufficient controls. Include
wrong entity, wrong relation, missing condition, reversed polarity, another
domain's example and topic-only recap controls. Freeze rules before a new
independent private evaluation; exposed reviews become development examples.

Public rules and synthetic passes still do not prove semantic sufficiency.
Keep Ask off if reviewed evidence does not pass. This proposal adds no model,
dependency, provider call, remote reranker, reindex spending, schema change or
automatic activation. User approval is required before amending Lane 6/ADR-022
and implementing the two additional families, because the current task asks
for approval before plan expansion.
