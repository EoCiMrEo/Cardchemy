# Navigation listwise ranking feasibility recommendation

Date: 2026-09-27. Scope: proposal only; no model inference, runtime change,
provider call, database write or Ask activation was authorized by this record.

## Starting evidence

ADR-023 directs learners to explicitly unverified original-PDF pages and
prefers one or none to weak filler. Its current v8 selector promotes any
bounded displayed cue with at least one question-term hit, then fills up to
three distinct pages. An independently reviewed, offline lexical-proxy run
on eleven exposed published-source questions found a useful page within three
for 11/11, but only 19/33 displayed cards useful and top one useful for 6/11.
A frozen twelve-question roster from three previously unseen original PDFs
had useful-page hit@3 11/12, but only 18/36 displayed cards useful. Neither
run proves actual SQL/vector candidate recall, access nor PDF opening.

The preceding v7 deterministic relation grammar failed its independent
source-quality gate. Reapplying that grammar or tuning a global lexical/topic
score cutoff would repeat a measured failure: useful and weak cards overlap
in score and even within-question lexical/title hit tuples. Approved card
question/source provenance is also unsuitable as a shortcut because card
editing can change the front while preserving its old source snippet/page.

The earlier pinned GTE ModernBERT INT8 audit tested a **global absolute
sufficiency threshold**, calibrated to reject all insufficient passages.
That threshold selected 0/32 positive heldout passages and stopped. It did
not report whether a useful passage outranks same-question weak passages;
therefore relative ranking remains an unanswered, narrower feasibility
question. The hash-verified public bundle remains local and ignored. Its
measured resource profile was 1.72 s startup, 2.77 s p95 per 30 windows and
614 MiB added RSS, within the prior experimental envelope. Those measurements
do not establish quality or authorize another audit.

## Proposed one-shot offline experiment requiring owner approval

Reuse the **same already hash-verified bundle**; no download, provider or
application database access. Independently author and review a public,
question-centric packet with at least 32 question groups across eight relation
families, each with one useful and three natural same-topic but unhelpful
displayed windows, plus separate no-useful-source groups. Freeze question,
source/template-family split, labels, harness and hashes before scoring.
Select one deterministic relative-rank/cardinality rule using calibration
groups only. Then evaluate untouched, source/template-separated heldout groups
once. Report top-one, useful-page hit@3, all-card useful precision, weak
primary and no-match false promotion by group; unknowns count as failures.
Do not reinterpret a cross-encoder score as proof of evidence sufficiency or
show an AI answer. A public pass needs at least 14/16 useful top-one, at least
14/16 useful hit@3, at least 90% useful displayed cards and zero weak primary
in the no-useful groups. These are experiment admission gates, not lowered
ADR-023 release gates. If any fails, stop without private rescue or runtime
integration. Only a public pass justifies an owner-independent development
corpus assessment and a **new** document-separated original-PDF holdout; the
earlier twelve-question frozen roster has already been opened for diagnosis.

Run networkless in an isolated Docker container, no app credentials or mounts
to retained data, at most four CPU, 2 GiB added RAM, 20 s startup, p95 5 s
for 30 windows and 600 s total. Verify bundle/fixture hashes, complete input
and actual resource use; stop on any bound. This trial is finite and does not
relax the one-query-embedding/zero-answer Ask contract. A result that ranks
well but cannot stop before weak filler is **not** a pass. Plan/ADR update,
implementation, any paid embedding/indexing and Ask activation remain separate
decisions; request approval before amending the Lane 6 plan for this audit.

## Approval and preparation checkpoint

The operator approved adding this single offline experiment to Lane 6 and
ADR-023. Those documents were amended without changing runtime policy. A
public, invented 48-group/192-window fixture and one-shot calibration/heldout
harness were prepared. An independent semantic review found the initial labels
consistent but caught structural label leakage in a first heldout version; the
builder was revised so every candidate in each heldout group receives the same
topic-specific heading and `Entry` shell. The public fixture's current SHA-256
is `6dcadb3776d19c381a1151fd3f820c2deef8140991752f25e50091ad7239c40a`;
the current harness SHA-256 is
`b6d330dad408a3ccbcfb521d4dc292c751e6eb8c351082a428a205000c51d477`.
The supervisor now also re-verifies the pinned bundle after a completed
inference before allowing a pass; this edit preceded any model execution.
No-inference tests passed 16/16 and the hash-pinned public bundle preflight
passed at 154,478,394 bytes; **zero model inferences** were run. The packet
intentionally measures at most one displayed page per question and cannot
establish 2–3-page navigation, follow-up resolution, SQL recall or PDF fidelity.
The one-shot Docker run has not started because command escalation was blocked
by automatic approval review's account usage limit after the retained database
migration. Do not run it in an unbounded local process to evade that review.

## Approved offline audit outcome after approval review resumed

- The first isolated container used the plain backend image. Hash/fixture
  preflight passed, but its attempted supervisor ended before model loading:
  `onnxruntime`, `numpy` and `tokenizers` were absent. No model score or rule
  file existed. The no-inference failure artifact was retained under ignored
  `artifacts/source-ranker-audit-20260927/listwise-setup-failure/`, and that
  container was removed. This was a runtime preparation error, not a quality
  observation or a second scored audit.
- The cached answer-worker image was checked for all three offline packages.
  A corrected, networkless container with the approved 4 CPU/2 GiB/no-mount/
  no-credential limits passed the same exact bundle/fixture preflight. The
  frozen script and fixture SHA values above were unchanged. One scored
  calibration/heldout audit then ran; no provider call, application DB write,
  private Knowledge read, or runtime-policy change occurred.
- Raw relative ranking on public calibration put the useful page first in
  **14/16** positive groups and within three in **16/16**. On heldout, raw
  useful top-one was **15/16**, and raw hit@3 was **15/16**. However the
  calibration-frozen top-two-margin rule, chosen to exclude all eight
  no-useful calibration groups, selected **zero** pages on both splits.
  Heldout displayed useful top-one/hit@3 was **0/16**, displayed cards **0**,
  and no-useful false primary **0/8**. Status `public_quality_rejected`,
  `candidate_passed=false`, `release_gate_passed=false`. The model ranks many
  useful windows well but this score cannot safely decide whether to show one
  under the pre-registered no-filler rule; no threshold was retuned.
- Technical bounds passed: startup **1,962.169 ms**, 30-window p95
  **2,286.167 ms**, peak RSS increase **508.836 MiB**, maximum input
  **53 tokens**, and scoring **31,794.992 ms**. The rule SHA was verified after
  copying aggregate artifacts to ignored
  `artifacts/source-ranker-audit-20260927/listwise-results/`.
  The corrected audit container was removed. These public invented examples
  do not measure the real PDF/SQL path; per the approved stop rule no private
  rescue, learned-ranker integration, Ask activation or further scoring follows
  this failed public gate.
