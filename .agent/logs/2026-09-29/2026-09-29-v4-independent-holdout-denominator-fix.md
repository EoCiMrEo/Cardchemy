# V4 independent-holdout display denominator correction

Date: 2026-09-29. The v4 offline release scorer was dormant; Ask was disabled.
No provider call, Knowledge read, database write or runtime policy change was
made in this correction.

Review found that the scorer enforced the owner-approved ≥90% usefulness
threshold only after combining exposed seed and independent holdout cards.
That could hide a weak independent holdout behind a strong exposed set. The
private holdout component now must itself have a nonempty display denominator
and ≥90% of **all its displayed exact cue-plus-original-page cards** useful.
The combined all-card threshold remains. Zero weak no-match displays, per-form
hit gates and every source/call integrity guard remain unchanged. The output
now exposes the independent holdout's displayed numerator, denominator and
gate boolean.

A synthetic regression with 12/12 holdout useful hits but two additional weak
cards proves the difference: the combined ratio is 24/26 (>90%), while the
independent holdout is 12/14 (<90%) and release quality fails. All 16 focused
scorer tests pass. The earlier 15-test dormant-scorer record is historical;
this correction supersedes its interpretation of the usefulness gate. No real
v4 selection or private display score exists yet.
