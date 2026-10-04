# Lane 6 groupwise public audit freeze and result

Date: 2026-09-28 (America/Chicago). Branch `main` at `6c02d6c` with the
existing working tree, retained `0028` database, root `.env`, backups and
three attached original PDFs preserved. Ask remains disabled.

## Approved scope and admission

The owner approved one distinct groupwise public-only source-cardinality
audit and the corresponding Lane 6/ADR-023 amendment. An initial approval
question misstated 26 local model calls; the owner separately authorized
30–50. This fixed audit caps itself at **27**: 20 train/calibration calls
and seven heldout calls only after calibration passes. Its four-way count
prediction caps rather than fills displayed cards, and a fixed per-card
utility floor may show fewer. The public label requires both a useful exact
cue and useful original page. Original-page usefulness is also reported
separately; the retained-course release gate is independent.

The new harness is
[`scripts/audit_reading_usefulness_groupwise.py`](../../../scripts/audit_reading_usefulness_groupwise.py)
and its synthetic contracts are
[`backend/tests/test_reading_usefulness_groupwise_audit.py`](../../../backend/tests/test_reading_usefulness_groupwise_audit.py).
Independent design/code review identified and resolved source-identity
tie-breaking, container swap/UID/rootfs validation and successful
calibration-to-heldout protocol coverage before freeze. The focused suite
passed **37/37** tests; `py_compile` and `git diff --check` passed. No model
inference, provider call or database write was used for admission.

The pre-score networkless Docker freeze validated 192 independently reviewed
public groups across fourteen CC BY 4.0 PDFs, the separate public review
receipts and exact source spans. The staged fixture SHA-256 is
`7b5cc3c6a0ded1f0fd338562e9d7860501035ca782981c95bd92c32459252219`;
the seven-file cached model manifest SHA-256 is
`2b7d441b1eb987502a7668355de4cf39f68bee3fd1dacea8d7c2dc1a97278182`.
The immutable cached Docker image is
`sha256:512345a7d0fe69953757f0a0eea429de9167e568ceb2ebcd9187888cc1d6c12c`
(487,244,866 bytes). The staged groupwise harness SHA-256 is
`35dead0b1f6246878874ebf7806700e9eb8d9056e4f315abf645d7afd491de24`;
the five-helper runtime manifest SHA-256 is
`3c80fff6c4c1f533761f389478254562ed8d795ec5c1dd04dc32cebf451baaac`.

**External freeze pin recorded before any groupwise model score:**
`5dc84f017833695483a9d78d802fb496f873b288d526b858970fc5bd4454f655`.
The same bounded container separately verified the external freeze pin, then
the groupwise harness default preflight reported zero model inferences,
provider requests and database writes. The staged bundle size is 95,958,700
bytes. A new host one-shot launcher in OS Temp, SHA-256
`5405d0cde573d3c8ca21dbcf454e9247abf525b2677ca901b31ec1e99b697887`,
passed its no-score pin/empty-ledger preflight. It contains nine explicit
mounts: public corpus/fixture/review receipts, staged scripts/runtime, cached
public bundle, freeze receipt, new ledger and new output. It mounts no root
`.env`, credential, retained database or private Knowledge path and uses an
immutable image with `--network none`, four CPUs, 2 GiB RAM and no swap,
non-root/read-only Docker flags. Its stricter 575-second host timeout leaves
room for cleanup inside the approved 600-second envelope.

The new fixed ledger and output leaf remain empty before scoring. The two prior
Mixedbread one-shot ledgers remain consumed and untouched. The single approved
inference attempt must remain networkless,
keyless and public-only, with four CPUs, 2 GiB RAM/no swap, non-root/read-only
container, 20-second startup, p95 five seconds per 30 windows, 256 complete
pair tokens and 600 seconds total. Calibration must pass its unchanged gates
before the 48-group heldout may be scored. Neither public success nor this
freeze activates Ask or closes the original-PDF release gate.

## One-shot result and stop

The one approved `--execute-approved` attempt completed in the pinned,
networkless, non-root, read-only Docker image in 98.327 seconds of host wall
time. The new fixed ledger contains exactly one parent attempt marker and
one child claim. The output leaf contains only `audit-result.json` and an
identical `supervisor-result.json`, each SHA-256
`f99abc1d72ccde3e443152f6f44c31041f67511d9632e648368b1bfe284a1d7f`.
There is no calibration-rule receipt or heldout score; prior audit ledgers
remain untouched. Docker stderr was empty.

Terminal status is **`calibration_rejected_no_heldout`** with
`candidate_passed=false`, `heldout_scored=false`,
`release_gate_passed=false`, zero provider requests and zero database writes.
The raw pair-logit top three contained at least one reviewed useful cue/page
in **36/36 positive calibration groups**, and the pool had 72 useful
original pages with 72 useful exact cues. The useful candidates were present
in this public pool; the tested groupwise decision could not safely select
them at the required displayed-card/no-match recall tradeoff.

The frozen calibration frontier makes the failure explicit. At risk `0.0`,
the selector displayed 37 cards, 30 useful (81.1%), triggered a display in
five of twelve no-useful groups, and hit 21/36 positive groups. At risk
`1.75`, it displayed twelve cards, eleven useful (91.7%), but still displayed
in one no-useful group and hit 10/36. At risk `4.0`, all seven displayed
cards were useful and no no-useful group displayed a card, but positive hit
fell to 7/36. No predeclared risk met **all** of zero no-useful displays,
at least 90% useful displayed cue-plus-page cards, and at least 30/36
positive hits. Frontier points are aggregate calibration diagnostics only;
they are not passing policies, heldout scores or a safe zero-card outcome.

The runner scored only the 576 train/calibration pairs in **20 local model
calls** (the seven heldout calls were not used). Maximum pair length was
241 tokens; startup 2,523.645 ms, full 30-pair p95 4,282.246 ms, peak
additional RAM 812.258 MiB and child elapsed 70,220.894 ms. All approved
resource bounds passed. The one-shot approval and ledger are consumed.
Do not rerun, retune this consumed candidate or open heldout under the same
approval. Keep Ask disabled and the four Lane 6 quality/release boxes open.

An independent read-only receipt audit rechecked the freeze, staged harness
and launcher hashes, both one-shot markers, byte-identical result/supervisor
receipts, absence of a rule/heldout artifact and the aggregate resource/
quality figures; it found no protocol anomaly. The live local Compose
containers remained healthy after the isolated audit. Validated settings
inside both the running API and answer worker reported only the nonsecret
`rag_ask_effective_enabled=false` value.

## Interpretation and remaining work

This failure is a **calibration-stage selection failure for this specific
public scorer/feature/count rule**. It does not show that the cached model
can never rank useful pages, that independent retained-course retrieval
always has a useful candidate, or that 2–3 query vectors would help. The
exposed retained-course 11-question hybrid pool was 11/11 useful-page
hit@3 but only 19/33 displayed cards useful; the public raw top-three
was 36/36 while all three bounded public display candidates failed their
calibration gates. On these measured sets, extra query vectors do not target
the observed card-selection/no-match error. The public fixture has four
distinct pages from one PDF per question; the real Ask pool can span more
pages/documents. No runtime integration, paid request, DB change or Ask
activation follows. A new root-cause review and separate approval are
needed for any further model/rule audit. The fresh two-PDF original-page
release holdout, operational/accessibility gates and flashcard sparse-source
yield remain open as documented in Lane 6.

## Verification and preservation

After this audit, the focused groupwise synthetic suite passed **37/37** and
the complete backend offline suite passed **2,265** tests with 147 skipped
and two live tests deselected in 217.06 seconds. `scripts/check_context.py`
passed 37 required files, 78 active guides and 1,424 links after the plan/
ADR/current-state/evaluation-guide updates. `git -c core.safecrlf=false diff
--check` passed. No frontend behavior, database migration, root `.env`,
retained volume, original PDF attachment, production image or Ask runtime
policy was changed by this public audit. The previously passing frontend
check was not repeated in this audit-only change.
