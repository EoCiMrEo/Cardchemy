# Activation target fixture and temporary-directory diagnosis

## Scope and preserved evidence

The root requested isolation of the six failure identities from the first
focused activation run. That original run and receipt remain intact:
`.agent/.verification/lane6-activation-focused-tests-20261003.json` recorded
three failures, three errors and 334 passing cases. This follow-up changed only
`backend/tests/test_rag_shutdown.py` in maintained source. Configuration tests,
application source, thresholds, root environment, database and runtime services
were not changed by this reviewer. No provider call or operator credential was
used.

The ignored diagnostic runner captures test output in memory and emits only
exception types, static repository source locations, validation field/type
identities and allowlisted boolean assertions. It injects the system/runtime
allowlist plus `ENVIRONMENT=test`, excludes all provider opt-ins and application
credentials, and writes separate receipts rather than replacing old evidence.

## Causes and minimal correction

1. The three configuration cases failed while pytest prepared `tmp_path`:
   `PermissionError` originated from `_pytest/pathlib.py::find_prefixed` and
   `getbasetemp`. The configuration assertions were not the cause. A new
   contained temporary parent and initially absent `--basetemp` child resolved
   this without editing any configuration test or application setting. The
   root owns the corresponding verification-wrapper correction.
2. The shutdown fixture created a Subject without an active embedding space.
   Three role/pricing-negative parameters correctly returned a profile with
   `ask_enabled=False`, but the new test compared it directly with effective
   installation settings, which were true for those parameters. Profile
   availability intentionally also includes the Subject-space condition.
   The fixture now creates the configured synthetic `RagEmbeddingSpace`, sets
   the synthetic Subject's active space and explicitly asserts a space match.
   All five existing Ask-off/judge-off/embedding-off/zero-price/retired-fence
   parameters, history reads, mutation/retry rejection and no-worker-claim
   assertions remain. Separate Subject-space mismatch tests remain unchanged.

The ignored runner's first attempt exited during setup because its child did
not have the backend import path. A second default-sandbox attempt reached its
240-second cap without a usable result. Both were diagnostic harness failures,
not test passes. The approved keyless follow-up obtained the permission cause;
the fresh isolated-base run then identified the three exact boolean failures.
No raw captured test body or exception text was saved into these receipts.

## Verification and freeze

The same bounded target set consists of three configuration cases, five
shutdown parameters and the disabled-worker pulse case. With the corrected
synthetic fixture and fresh base it returned exit 0, no failure records, in
5.755 seconds. This is targeted offline evidence; the root still owns the
repaired focused activation and fresh complete backend runs.

- Permission diagnosis:
  `.agent/.verification/lane6-activation-config-diagnosis-v3-20261004.json`.
- Exact pre-correction failures:
  `.agent/.verification/lane6-activation-target-diagnosis-v4-20261004.json`,
  SHA `c54ba7f239edace31e1eb9c253cabe064e73251f74ab649e5ed80b1bb0d753a2`.
- Passing corrected targets:
  `.agent/.verification/lane6-activation-target-diagnosis-v5-20261004.json`,
  SHA `c7c7fd10a46031171299c57fbc512faa9dad2fecfdf3664a0e987584e89d8ec1`.
- Corrected shutdown test SHA:
  `0b24fabed7de295c97007cb498f9912ba753d27b6d623ba4cc754edebb09e987`.

All backend Python inputs are frozen on this reviewer's side for the root's
current-policy verification runs. The conditional documentation patch remains
unapplied. The root owns index updates, actual enablement proof and closure.
