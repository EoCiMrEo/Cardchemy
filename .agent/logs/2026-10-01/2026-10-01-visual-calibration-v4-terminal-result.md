# Public visual calibration v4: terminal result

Date: 2026-10-01 (America/Chicago). Branch main, HEAD `6c02d6c`; the
pre-existing shared work and retained data/configuration were preserved.

## Authority and outcome

The explicit 62-request envelope was approved through
`call_Kbljn2IjxYkfVQHCoQ0woUaK`. Its exclusive ledger is consumed. The trial
made **18 new physical requests**, with **15 valid responses**, three unfinished
content responses and **zero timeouts**. It stopped at `quality_unreachable`.
With five prior valid receipts, the complete 67-group denominator contains
20 valid, three failed and 44 unattempted groups. It cannot establish a full
quality pass. There was no retry, heldout opening, private source transfer,
database write or Ask enablement.

The partial displayed result is **21/24 useful (87.5%)**, with three nonuseful
cards and zero unknown cards displayed. Positive hits are 14 (direct 6,
paraphrase 5, follow-up 3). Six controls returned valid clear empty selections;
one attempted no-match control returned a page. The frozen 12/12 no-match
requirement is consequently unreachable. Three failed groups also make the
65/67 availability and two-error requirements unreachable.

Q003/Q007/Q014 failed `provider_finish_invalid` after 11.366/19.561/16.771
seconds and 2,034/2,032/2,029 reported output tokens respectively. These
near-2,048 unfinished responses are consistent with an insufficient output
budget; the exact provider finish reason was not retained, so `MAX_TOKENS`
is not an observed fact. No raw response or thought text is retained here.

## Cost and immutable evidence

New known usage under the authorized guard totals **USD 0.106457**; combined
known guard cost is **USD 0.130870**, including USD 0.024413 from earlier
valid calls. Three earlier timeout charges and older failed-call charges remain
unknown. These estimates are not provider billing receipts.

Approval SHA-256:
`6fdd878e41dd04f56275377c9cc68868d0d98b6be534619bbb657ec2ccd75aed`.
Result SHA-256:
`18e5053cbf38e6ef0b25c1048a3d4eb680ca83dd3498c143dd7c566ee865d2a8`.
The aggregate result remains in the private OS Temp trial directory; executable
and input bindings, per-call exclusive claims and receipts are retained.

The supervisor completion receipt reports exit 0 with resume prohibited.
Both recorded worker and supervisor process handles were independently checked
absent after completion. Terminal success of the supervisor means its stop was
recorded successfully; it does not mean model-quality success. No process was
restarted, and the old executable/prompt/scorer/result were not edited.

## Next action

See the [prospective completion repair](2026-10-01-visual-source-completion-repair.md).
The old trial remains failed under its frozen gates. Lane 6 stays **3/7**;
Ask remains disabled and independent heldout/private/release evidence remains
required.
