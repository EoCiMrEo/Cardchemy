# Current v7 review and source-display bridge

## Scope and unchanged authority

Continue the approved automatic, before-outcome source evaluation on the exact
[current read-only hybrid inputs](2026-10-02-private-v7-hybrid-input-verification.md).
No private provider transfer, key read, database mutation or runtime activation.
All questions, source text, cues, page images, review keys and identifiers stay
in owner-private OS Temp. Existing signed reviews and source snapshots remain
immutable. Subagent usage became unavailable before the four-slot review;
the root performed it before reading any new source-ID result.

## Current-source review

The first bridge correctly refused because **four of 48 current source slots**
differed from the old packet. Forty-four slots, including exact text/image
source parts and reviewed UUID/page identities, remained identical. Prepare a
blinded four-slot packet from the SHA-bound current snapshot and actual
authenticated-PDF renderer PNGs. Review each excerpt and original page against
the fixed current question and strictly preceding user question before model
selection: two slots were useful; two were not. No question or label was tuned
from model output. Compose a new distinct review using exactly 44 inherited
signed labels and four new decisions; pin a new reviewer public key before
labels and sign the complete new roster. The old key/seal/labels are unchanged.

The inherited v6 roster/label **schemas** are internal scorer compatibility
inputs; this is a new v7 source review, not a v6 execution receipt. The actual
runtime and request bridge bind v7, visual-v3 and retained head 0032 separately.

## Scorer repairs and verification

Independent review exposed a forged raw-clarity route. The scorer now computes
`navigation_query_v4(question, ())` from the exact SHA-pinned production
functions, without importing Settings/database dependencies, and compares the
result before binding context. Clear-as-unresolved and unresolved-as-clear
forgeries fail. Historical review request hashes used ASCII JSON; current HTTP
uses UTF-8 JSON. Both identities remain explicit and independently bound;
Unicode regression coverage preserves identical decoded evidence.

The real packet then exposed an additional harness mismatch: provider document
IDs are privacy aliases, while signed review page keys use local UUIDs. The
scorer now verifies the separately pinned local document/content-revision/page
mapping, reproduces first-seen server aliases and matches alias/PDF/page to the
signed cue and page identity. Missing, changed UUID/page/revision/alias bindings
refuse. This changes only evaluation tooling, not runtime retrieval or scoring
thresholds. **52 targeted preparer/visual/scorer tests passed** after repair.

The new exact twelve-case bridge froze successfully: ten raw-only question
wires and two bounded literal-subject wires. All 48 source slots are reviewed
before outcomes. The post-review timestamp is a **pure context-identity check**;
it does not claim a fresh SQL authorization observation. Any eventual provider
dispatcher must freshly verify current authorization/revision/PDF bindings.
Diagnostic message identities are simulations of frozen cases, not persisted
Ask jobs; real admission/ordering remains covered by current PostgreSQL tests.

Bridge SHA: `44206ac0bd34e596e260093b5156a155de438c7360ca86d205443cb771c845b5`.
Request packet SHA: `5dbb1a26489312874c7b248805c3db0c6b6f1eb569364751aac7b929c4ee1547`.
Runtime manifest SHA: `9afa97d6fab3ba8a226d03ca468a67d866ba9c717d4534aca4dcbfeaff87d95e`.
This is **preparation, not displayed-source accuracy or release evidence**.
No provider call or DB write occurred. Ask stays disabled; Lane 6 **3/7**.
