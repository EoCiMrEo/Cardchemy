# Lane 6 selective-navigation public audit freeze

Date: 2026-09-28 (America/Chicago). Branch `main` at `6c02d6c` with the
existing working tree preserved. The operator approved one new public-only,
offline selective-navigation audit after the prior Mixedbread calibration
stop. This is a separate candidate and ledger; it does not replay the old
attempt, call Gemini, read private Knowledge, write the retained database,
integrate a runtime policy or enable Ask.

## Admission before scoring

The new harness implements distinct question-level no-match and per-card
qualification decisions. An independent code review found and resolved
confusion-count, score-validation and calibration/heldout protocol issues.
Its keyless synthetic suite passed 24/24 tests. The public fixture remains
192 independently reviewed groups from fourteen CC BY 4.0 PDFs. The exact
Docker fixture validation passed with 192 groups and fourteen documents,
without inference. Source-only input mounts contain public PDFs, review
receipts, the pinned model and six scripts; no retained volume, `.env`,
credentials or private Knowledge are mounted.

The cached immutable Docker image ID is
`sha256:512345a7d0fe69953757f0a0eea429de9167e568ceb2ebcd9187888cc1d6c12c`
(487,244,866 bytes). The reviewed staged fixture SHA-256 is
`7b5cc3c6a0ded1f0fd338562e9d7860501035ca782981c95bd92c32459252219`;
the seven-file model-bundle manifest is
`2b7d441b1eb987502a7668355de4cf39f68bee3fd1dacea8d7c2dc1a97278182`.
The new selective harness SHA-256 is
`607a817182c4f417389241b2c4b5808e53066864a92e39593274af1ed3a2eca0`;
the validator SHA-256 is
`4cdc4c04b90fb2153b5f2acc26c1bbf5e1b02c5beadf0d3e918715662d19b978`.
The other four helper pins and runtime limits are in the new runtime manifest,
SHA-256 `09a004cbbb4e72c5271828762cc68bba3b06b9b3d8fae4febc8a011fd24e7f9e`.

**External freeze pin recorded before any selective model score:**
`ebbe812315231b497b9772024921294e656d66e3a88e40a5764bdae16639707b`.
The freeze receipt was created exclusively inside the networkless, bounded
cached image. The new fixed ledger and output leaf were empty before this
freeze. Verify and default no-score preflight must still pass before the
single `--execute-approved` run. The intended container limits are no network,
four CPUs, 2 GiB memory and swap cap, 20-second startup, p95 five seconds per
30 windows, 256 pair tokens without truncation and 600 seconds total including
preflight and cleanup. The result, resource measurements, checks and stop
condition are recorded below.

The same bounded container independently verified the recorded freeze digest.
The new harness's default preflight reported zero model inferences, provider
requests and database writes. A disposable, separate pair of Windows mounts
passed non-root container write and mountpoint checks without touching the
real ledger. The host one-shot launcher, SHA-256
`6256593c887186c57e6f95cca4e450cc4e0b2785a1715e96671453379bdaae73`,
passed its no-score pin/empty-ledger preflight. It starts at most one immutable
Docker container and enforces a stricter 575-second execution budget to leave
time for termination and cleanup within the approved 600-second total.

## One approved score and stop

The single `--execute-approved` attempt completed in the immutable cached
image under the specified non-root, read-only, networkless Docker limits.
The host wall time was 105.291 seconds. The fixed new ledger contains exactly
one parent attempt marker and one child claim; the old audit ledger was not
used. The output leaf contains only `audit-result.json` and an identical
`supervisor-result.json`, each SHA-256
`1b3f64553e46516428b9695eaeb8d3668ea4a9db951ee42e3802d0e1aacaec59`.

The terminal status is **`calibration_rejected_no_heldout`**:
`candidate_passed=false`, `heldout_scored=false`,
`release_gate_passed=false`, zero provider requests and zero database writes.
There is no calibration-rule receipt and no heldout grade. The raw pair-logit
top three contained at least one independently useful cue/page in all 36
positive calibration groups, with 72 useful cues/pages available in the
calibration pool. This ranking observation does not prove a safe display
decision. The fixed train-only separate null/card classifiers found **no
calibration threshold pair** that simultaneously met zero displays in the
twelve no-useful groups, at least 90% useful displayed cue-and-page cards and
at least 30/36 positive useful hits. The result has no selected display
count or threshold frontier; zero displayed cards must not be interpreted as
a successful abstention policy. Do not infer heldout or retained-course
quality from this stop.

The runner scored 576 train/calibration pairs in 20 local model calls, with
at most 241 pair tokens. Startup was 2,196.096 ms, the full thirty-pair pool
p95 was 4,199.574 ms, peak added RAM was 812.242 MiB and child elapsed time
was 69,201.519 ms. All stated resource checks passed. The harness, runtime
manifest and freeze hashes still matched their pre-score pins after the run.
The one-shot approval and ledger are consumed. The public candidate is not
integrated, the independent original-PDF release test remains unopened, and
Ask remains disabled. Another scorer, calibration or model run requires a
separately reviewed proposal and operator approval.

## Interpretation and next decision boundary

The operator proposed retaining one current-question embedding, separately
deciding whether the question has any useful page and qualifying each exact
page/cue, showing zero to three without weak filler and asking for a clearer
referent on unresolved follow-ups. The failed audit tested one concrete
implementation of those two decisions; it does not invalidate the product
architecture or demonstrate adequate source selection. The independent
published hybrid diagnostic found a useful original PDF page in the displayed
top three for 11/11 exposed questions but only 19/33 displayed cards useful.
Together with the public raw top-three 36/36 observation, the available
evidence favors investigating the display/no-match rule before adding query
vectors. Neither set establishes candidate recall on the fresh two-PDF
release holdout.

A provider-free, calibration-only label count after the stop found 72 useful
original pages and 72 useful exact cues across the 48 calibration groups;
all 72 page-useful candidates also had a useful cue. Thus the failed public
calibration cannot be explained by a stricter combined cue/page label than
the owner's original-page usefulness target on that split. No heldout labels,
candidate text or model score was opened for this count.

The operator's 2–3-vector idea is conditional on a future independent
real-query measurement showing that the useful page is absent from the
candidate pool. The Gemini `batchEmbedContents` endpoint can return more
than one vector in one HTTP request, but multiple embedded inputs still need
token and cost accounting, and Cardchemy's current Ask policy accepts one
current-question vector. No extra vector, provider request or policy change
is authorized by this record. Any further offline model/rule audit likewise
needs a new frozen proposal and approval. No 90% useful-card claim or Lane 6
checkbox follows from the two failed calibration audits.

## Verification and preservation after the stop

The new harness's 24 focused synthetic tests passed before the freeze. After
the one-shot run and documentation update, the full backend offline suite
passed **2,228 tests**, with 147 skipped and two live cases deselected in
203.26 seconds. `scripts/check_context.py` passed 37 required files, 78
active guides and 1,419 local links; `scripts/check_ci.py`,
`scripts/check_release.py --version 0.1.0` and
`git -c core.safecrlf=false diff --check` exited zero. These checks do not
turn the failed public quality gate into a pass. No paid AI call or new
indexing was made. The retained populated volume, root `.env`, backups and
three attached original PDFs were not changed by the audit; the source-only
Ask gate stays disabled. No heldout score was read or created.
