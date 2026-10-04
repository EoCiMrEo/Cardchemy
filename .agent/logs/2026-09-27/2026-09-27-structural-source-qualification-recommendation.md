# Structural source qualification after the canonical-page diagnostic

Date: 2026-09-27. Initially recommendation only; the operator subsequently
approved updating Lane 6/ADR-022 and implementing the bounded v7 scope below.
Ask remains disabled; approval is not a quality or release pass.

## Evidence and decision boundary

The approved canonical-page implementation passed backend, disposable
PostgreSQL/migration, image and deterministic journey checks. Its current-image
private diagnostic nevertheless selected only **1/12** independently sufficient
sources despite being supplied the correct page anchor. No span was selected
for the sixteen insufficient controls. All thirteen current pages and their
anchors passed authorization, revision and hash checks twice; context stayed
below 319 estimated tokens. This is conditional source qualification evidence,
not retrieval/display/page-open proof. See the
[implementation evidence](2026-09-27-canonical-page-evidence-implementation.md).

Independent review, without selector source access or rerunning selection,
rendered all thirteen original PDF pages and reaffirmed **12/12 sufficient
windows, 16/16 insufficient controls**, and the sufficiency/source fidelity of
the one actual selected window. Original labels remain immutable. The eleven
missed windows use five heading-owned bullet/list structures, four worked
examples or explicit interpretations, one parenthetical expansion in a
multi-entity list, and one cause/consequence across labeled blocks. Some
sources explain an introductory concept rather than its mathematical
algorithm; qualification must follow the actual question's scope.

The code-level diagnostic identifies three unknown question intents, one
unresolved follow-up and seven relation-qualification misses. Canonical anchor
ownership and budget checks succeeded for every positive. `source_sufficiency.py`
currently recognizes a finite set of interrogative phrases, resolves prior
entities mainly as uppercase acronyms, builds short heading/continuation
windows, and often requires explicit relation verbs. Improving rank alone
cannot recover sources excluded before ranking.

## Recommended bounded v7 implementation

Keep source-only Ask and the existing eight relation families. Replace the
flat verb-cue dependency with a bounded, explicit question/source structure
contract, without treating similarity as proof of sufficiency.

1. **Question roles.** Parse supported interrogative and imperative constructions
   into entity, relation, requested object/domain, condition, polarity and
   numbers. Strip only request scaffolding. Resolve a follow-up from exactly
   one unambiguous entity in bounded prior user context, including ordinary
   noun phrases; preserve the present question's relation and qualifiers.
   Multiple entities, unresolved pronouns and multiple requested relations
   remain explicit no-match/specific-question outcomes.
2. **Source units.** Parse canonical page lines into owning headings, relation
   subheadings, paragraphs, list items, numbered sequences and explicit
   example/interpretation blocks. Preserve original offsets. Allow a relation
   label and its body to express the relation even without a fixed verb:
   an explicit Definition label with a complete defining noun phrase, an
   Applications label with its examples, or Process/Steps with an ordered
   action sequence. Recognize parenthetical expansions at item granularity.
   An example may qualify only for the relation it actually illustrates, with
   the explanatory connection present in the same contiguous window.
3. **Ownership and aliases.** End inherited ownership at another topic heading
   or overt subject. Use only unambiguous acronym/full-name pairs actually
   present in eligible canonical source text; retain their source offsets.
   Normalize matching separately from the displayed verbatim text. Do not infer
   broad synonyms or mathematical relationships from a formula alone. The
   selected window must contain the requested entity or its locally proved
   alias and all context required to understand the relation.
4. **Qualification before rank.** A complete relation, owner and required context
   are mandatory. Generic topic headings, incomplete definitions, benefit
   mentions without the requested causal connection, unordered items offered
   as a process, wrong subjects, missing conditions/numbers and unsupported
   aliases stay partial or unsupported. Scores only order units that survive
   these checks; they are not probabilities of truth.

The source unit remains a single contiguous exact slice of at most 480
characters; no cross-page or noncontiguous synthesis is proposed. Preserve
three references, 20 first-stage candidates, cumulative 30 chunks/12 pages/
8,192 tokens, same-page and ±1/±2 expansion, SQL access/revision/space checks,
one current-question embedding and zero answer/verifier/provider retries.
The parser scans only already admitted canonical page text. No model,
dependency, remote reranker, index representation or embedding-space change
is included. This is explicit source navigation, not universal semantic
verification or answer generation.

Snapshot `hybrid_source_sufficiency_v7`/`source_relation_units_v7`. Preserve v6
references and introduce a new additive migration for the canonical-reference
policy guard before any v7 persisted job can execute; do not rewrite `0024`.
Retain exact page offsets, atomic commits, complete-bundle redaction, source
expiry and current-page highlighting.

## Evaluation and stopping rule

An independent evaluator authors public positive/negative pairs for every
declared structural form before implementation. Include wrong owner/relation,
ambiguous expansion, missing condition/number, negation, topic-only headings,
unordered lists, clipped spans and another entity's example. Keep existing
tests and all released safety/quality thresholds. Do not make private
question-specific exceptions or add lists of lecture terms to runtime rules.

Freeze the v7 candidate before a single private measurement. Preserve the v6
diagnostic as regression evidence; because its outcomes now informed the
recommendation, do not call a subsequent score on those pages an independent
release holdout. Independently discover/review previously unexposed pages
before runtime evaluation, using the operator's delegated-agent instruction.
If the available lectures cannot supply the required independent set, report
that limitation; do not recycle pages or relabel rejected sources to pass.

Keep sufficient displayed/openable hit@3 at least 10/12 and at least 3/4 per
direct/paraphrase/follow-up group, zero false primary on sixteen reviewed
insufficient pairs, the eleven-seed and maintained retrieval gates, source
integrity/access and release requirements. A supplied-anchor diagnostic is a
preflight for these measurements. Real query retrieval still needs its own
fresh paid embedding envelope; do not spend it when qualification fails.

Give this structural implementation one frozen evaluation. If remaining
failures require implicit reasoning beyond the explicit structures, stop
adding isolated patterns and present the measured limitations. A local learned
source-sufficiency component would be a separate architecture/resource/model
proposal, not something silently introduced as a reranker. It must never
restore answer generation or the retired answer verifier.

The recommendation itself changed no plan/ADR, runtime, provider budget or gate.
After explicit approval, Lane 6 and ADR-022 record the extension; implementation
and verification are tracked in the [v7 implementation log](2026-09-27-structural-source-v7-implementation.md).
No private content or IDs are retained in this log. Original and actual-window
review artifacts remain private in OS Temp.
