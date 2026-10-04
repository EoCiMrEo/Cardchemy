# High-thinking v2 public pilot: startup recovery

Date: 2026-10-01 (America/Chicago). This is a progress snapshot, not a
terminal pilot result. It follows the [approved one-use public envelope](2026-10-01-high-thinking-transport-pilot-approved-scope.md)
and preserves the old v1 [three-request stop](../2026-09-30/2026-09-30-full-cue-high-thinking-public-stop.md).
The approved envelope, frozen code and public source packet did not change.
There is no private Knowledge transfer, DB write, new indexing or Ask
activation. Ask remains disabled and Lane 6 remains **3/7**.

## Frozen authorization and preflight

The distinct v2 approval receipt SHA is
`a4ba03fb2051c07e006e264a1ff0cf355f74e776657e41c8e6e7f60f4be03c22`.
Host keyless, key-availability and write-location preflights passed without
a provider call. The authorization identity is
`20261001_public_full_cue_high_thinking_transport_v2_once`; it binds the
frozen public caller, candidate and limits. The old consumed v1 ledger and
source files remain intact. No key value, prompt, PDF text or raw response
was printed or stored in this record.

## Initial launch and diagnosis

The initial detached process (PID 26116) exited before any split or group
claim. At inspection, the real ledger had **zero entries**, no output
directory had been created, and no matching child process remained. The
caller writes and fsyncs the split and group claim before it can issue a
provider POST; therefore this launch did not reach a physical API attempt.
The precise process-exit cause is unconfirmed. Preserve the original launch
claim and process evidence; do not erase or reinterpret them as provider
failure or model no-match.

No-network checks then passed for the main execute guard at its boundary,
construction of the exact sanitized client, and the actual public admission
path with a fake ledger. A harmless detached-process probe (PID 19500)
survived 25 seconds and completed. Frozen executable/source hashes remained
unchanged. A local diagnostic first encountered a syntax error, and an
initial test invocation used the wrong working directory; both were
corrected locally without a network request or source change. An
independent review agreed that one guarded startup recovery remained
within the **unused physical** request budget of the existing approval.

## Single supervised recovery in progress

An ignored local recovery helper checks the frozen receipt, source hashes,
real ledger and lack of a matching child, then writes an exclusive separate
recovery claim. It does not reset a consumed claim or authorize a second
recovery. One supervised recovery started as PID 9644 in terminal session
44347. At the time of this snapshot it was running; there was **no result
or quality score to report**. Root task monitors the same ledger for a
terminal record. No provider-call retry was performed here.

The 66 exposed public calibration groups still precede any conditional
60-case different-PDF heldout. The transport bound remains 64 KiB for the
whole HTTP response, 2 KiB for visible verdict JSON, with the same model,
request, scorer, no-retry policy, token/time/cost guards and frozen quality
gates. A completed calibration and all separate private/PDF/accessibility/
release checks are still required before Ask can be enabled.
