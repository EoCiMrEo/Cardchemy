# Public reading-usefulness audit harness and blinded review admission

Date: 2026-09-28. Branch `main` at `6c02d6c`, with the substantial existing
working tree preserved. The user approved one networkless Mixedbread public
audit under the recorded artifact, CPU, RAM, timing and quality limits. This
record describes preparation only: **no model inference or heldout score**.

`scripts/audit_reading_usefulness.py` implements the fixed pair-logit feature
set, train-only regularized logistic fit, one calibration-only display
threshold, up-to-three distinct page selection and the preregistered heldout
gate. Its default mode verifies frozen inputs without scoring. Inference
requires an external freeze digest, an exclusive parent attempt marker and an
exclusive child claim, a credential-free networkless Linux process and the
approved resource ceilings. A later hardening check requires the actual
cgroup CPU quota to be at most four cores and the memory limit at most 2 GiB,
before consuming the one-shot inference marker; a no-model-run probe passed
inside the exact networkless 4-CPU/2-GiB container. A separate load-only
inspection of the pinned graph declared one output with shape `[batch_size, 1]`,
matching the frozen runner's expected single logit; `session.run` was not
called. It writes the calibration rule before opening
heldout and stops on a failed calibration gate. Synthetic tests include the
one-shot claim and negative gate cases. The script has not been used to score
the public corpus.

Independent author agents prepared two **provisional** OS-Temp drafts:
96 train groups across six PDFs and 48 calibration plus 48 heldout groups
across eight source-disjoint PDFs. Train offsets passed a fresh PDF text
re-extraction check. Calibration/heldout offsets were checked on an earlier
draft; the final draft was regenerated from the pinned inventory after cue
cleanup and still needs an independent full recheck. Author-proposed page/cue
labels are not independent evidence. Final train draft SHA-256 is
`30b96a2ebb5590aee9d890fb81dd6b93933b7d4edb1cd85a25b873089b7044d2`;
final calibration/heldout draft SHA-256 is
`fe9dd50c4927494d88fa148250b97b006cb0c8ff959c940eee37c50f8f1aaaf4`.
Both remain outside Git and cannot be frozen or scored.

`scripts/build_reading_usefulness_blind_review.py` projected those exact
drafts into two OS-Temp review packets that omit all proposed page/cue labels.
Their SHA-256 values are
`7c5170938eb9421d0815d60e65dfda90a5abdcc51b5b6e9eb51d279439f65bc5`
for train and
`9052da0e125f9d7e3eaf83552c3f01fecd00a9e361cbb66880af80269cf54845`
for calibration/heldout. Two independent blinded page/cue reviews and a
separate rights/leakage audit are pending; no reviewer or adjudication row was
manufactured to satisfy the validator. A further validator guard requires
positive cases to be balanced across direct, paraphrase and follow-up forms.

Verification: 46 focused backend tests initially passed, followed by 18/18
runner tests after cgroup guard hardening and 3/3 blind-projection tests;
the keyless disposable rehearsal passed separately. `check_context.py`
passed 37 required files/78 active guides/1391 local links;
`git diff --check` exited zero with line-ending warnings only. Earlier
`npm run check` and guarded PostgreSQL release checks are documented
separately. A public audit pass would still need an independently reviewed
192-group fixture and its own one-shot run, then a separate release holdout;
Ask remains disabled.

## Subsequent admission failure, before any score

An independent rights/leakage audit of the author drafts found a substantive
calibration/heldout duplicate: lec22 p30 and lec25 p11 share 29 normalized
12-token shingles in a selected cue. Train lec11 and heldout lec33 also ask
the same alpha-beta move-ordering relation. Thus the v3 source allocation is
not a valid source-disjoint heldout despite different PDF files. Its fourteen
documents have first-page CC BY 4.0 notices, but 0/14 per-document third-party
rights reviews are complete; some pages contain separately attributed images.
The rights/leakage report is retained only in OS Temp, without private course
content in this log.

The first blind packets hid author labels but their group IDs included the
planned 0/1/2/3 useful-count stratum. Two reviewers completed a diagnostic
384-candidate train review and a third completed calibration/heldout review;
the train comparison found 342 fully agreed, 12 disagreed and 39 with at least
one uncertainty flag. These reviews are **not fully count-blind** and cannot
establish the frozen admission gate. A v2 packet builder now substitutes
random opaque group/candidate IDs, shuffles order, and stores the author ID
mapping separately in OS Temp; its six projection/comparison tests pass.
No new packet from the compromised split will be scored. Source allocation,
rights, reviewer independence and uncertain labels need repair and renewed
review before the single approved one-shot audit can begin.
