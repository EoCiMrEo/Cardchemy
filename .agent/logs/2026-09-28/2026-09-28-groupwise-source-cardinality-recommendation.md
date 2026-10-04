# Lane 6 groupwise source-cardinality recommendation

Date: 2026-09-28 (America/Chicago). Status: **proposal only**; not a plan
amendment, runtime policy, paid request or approval for another model run.
Branch `main` at `6c02d6c`; preserve the large existing working tree,
retained `0028` database, root `.env`, backups and three attached original
PDFs. Ask remains disabled.

## Evidence and diagnosis

The approved source-only architecture uses one current-question embedding,
authorized hybrid retrieval and local neighbor inspection, then shows up to
three original-PDF reading links with an explicit unverified label. On eleven
exposed published-source questions, a useful page appeared in the hybrid
displayed top three for 11/11, but only 19/33 displayed cards were useful.
The first one-shot public Mixedbread experiment with a single global display
threshold stopped at calibration. A separately approved second experiment
trained distinct question-null and per-card linear classifiers but also
stopped at `calibration_rejected_no_heldout`: no threshold pair met zero
false displays in 12 no-useful groups, 90% useful displayed cue/page cards,
and 30/36 positive hits together. Its raw pair-logit top three nonetheless
contained a useful source in all 36 positive calibration groups. Its ledger
is consumed; heldout was not scored. A no-model aggregate count found all
72 page-useful calibration candidates also had useful exact cues, so the
combined-label gate was not the reason for this calibration stop.

These observations identify **selection and cardinality** as the next
measured bottleneck on the exposed/public sets. They do not prove perfect
retrieval on the fresh two-PDF holdout or prove that the cached scorer can
separate no-match pages. Multiple query vectors are not justified by these
candidate-present results. The user's proposed 2–3-vector comparison is
conditional on an independent real-query funnel later finding useful pages
absent from the candidate pool. Google's documented `batchEmbedContents`
returns multiple vectors in one HTTP call, but multiple inputs consume more
tokens and Cardchemy's current Ask policy accepts only one query vector.
Any multi-vector policy would need its own cost, latency, authorization and
quality approval.

## One next candidate for operator review

To test an actually different decision architecture rather than retune the
consumed thresholds, propose **one groupwise set selector** on the same
hash-verified public 192-group fixture and cached Mixedbread xsmall model.
For each question's four exact, distinct-page candidate cues, score all four
with the fixed local pair model. Use only the current question, locally
resolved prior referent, exact candidate cue/page structure, lexical/condition
features and bounded pair scores; never use split, document identity,
reviewer ID, usefulness label or source filename as an inference feature.
Train a fixed regularized card-utility head and a four-way `0/1/2/3` useful-
page count head on the 96 train groups. The count head is structurally
different from an independent null threshold: it predicts how many cards
can be justified, including no-match, before choosing the highest-utility
distinct pages. Use a predeclared shallow nonlinear feature transform and
fixed regularization; no model or feature search after observing calibration.
For this public audit, a countable useful card requires **both** an independently
useful original PDF page and an independently useful exact displayed cue;
report page-only usefulness separately. The calibration split has informed two
failed development candidates, so only the never-scored heldout can test
generalization. A predicted count is a ceiling, never a requirement to fill
weak cards.
Calibrate at most one conservative set-risk parameter on 48 calibration
groups. Freeze the complete features, training, tie rules, risk grid,
fixture, scripts, image and bundle before any score. Report a calibration-
only aggregate precision/hit/no-match frontier even on failure, so the next
decision can distinguish inseparable scorer signal from a bad display rule
without pretending a failed candidate displayed zero cards.

Keep the same calibration gate: zero displays in all 12 no-useful groups,
at least 90% useful among every displayed cue-plus-page card, and useful
hit@3 in at least 30/36 positive groups. Only a pass opens the still-blind
48 heldout groups once. Keep the unchanged heldout gate: useful hit@3 at
least 33/36 and 10/12 per form, useful first at least 31/36, at least 90%
useful all displayed cards, at least 60/72 available useful cards shown,
correct displayed count for at least 10/12 in each one/two/three-useful
stratum, and zero displays in all 12 no-useful groups. Counts of uncertain
or failed controls are failures. A public pass authorizes only separate
development assessment, never runtime integration or Ask enablement.

Use a **new** fixed exclusive attempt/child ledger; never clear or reuse
either consumed ledger. Run once in the immutable cached Linux image with
no network, credentials, private mounts, retained DB, Gemini, new indexing
or download. Bound to four CPUs, a 2 GiB memory/swap cap, non-root read-only
container, startup 20 seconds, p95 five seconds per 30 windows, at most
256 pair tokens without truncation and 600 seconds including preflight and
cleanup. At most 768 public question/cue pairs are scored: 384 train, 192
calibration and 192 heldout only if calibration passes; at most 27 model
calls across the separately gated train/calibration and heldout stages at
30 pairs per call maximum. Keyless synthetic tests and a no-score freeze/
verification precede the one authorized inference attempt. Failure stops
without retry, private rescue or heldout tuning. If this distinct groupwise
decision also fails, do not run another calibration variant on the same
cached scorer without a new root-cause review and approval.

The separate release contract is unchanged: a fresh published two-PDF,
12-question, document-separated original-PDF holdout; useful-page hit@3
at least 10/12 overall and 3/4 per question form, exposed regression at
least 10/11, and at least 90% useful original pages among **all displayed**
cards, with no-match, access, revision, publication, PDF-open, spoken
accessibility and operational gates. Its document/query embeddings need a
fresh explicit endpoint/model/price/call/token/time/cost envelope after a
candidate is frozen. No guarantee of a 90% pass is claimed by this proposal.
