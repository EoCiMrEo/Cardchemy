# Private v8 startup pin-cache independent review

## Bounded scope

Independently review the startup-only `_validate_bound` optimization in
`scripts/run_private_visual_trial_v8.py` and its direct caller/host/guard
consumers. No provider request, private packet/source read, database access,
credential lookup, operator environment inspection, runtime edit, gate/budget
change or repeated broad scan/test was performed by this reviewer.

The root reported an old keyless stage validation of 40.09 seconds against its
unchanged 30-second startup cap. That observation motivates deduplicating code
file hashing; it is not a measured result for the repaired code. Prior approved
provider authority remains consumed and cannot be restored by this review.

## Initial findings and repair observed

The local cache is keyed by guard SHA plus the complete sorted code map and is
created afresh inside each `_validate_bound` invocation. Every request,
admission, context, candidate source identity and cue offset is still checked
per case. Render, after-quota dispatch, receipt and post-selection checks retain
their own current code/SQL/PDF verification. No cached authorization or source
grant is reused.

The initial optimization also skipped the structural validations performed by
`guard.verify_code_pins` for subsequent equal maps. A later `GuardPins` carrying
a list of the same path/hash pairs could be converted by `dict()` into the
cached identity while violating the required Mapping type. Startup would
previously reject this complete bound trial; deferring rejection to a later
fresh dispatch guard could permit earlier valid cases to consume requests.
This was a bounded startup strictness regression, not a demonstrated transfer
or access-control bypass.

The root repaired it with cheap **per-case** checks before cache lookup: exact
`GuardPins` type, Mapping, required paths and size bound, plain-string SHA
fields and plain-string path/SHA entries. The actual code/file hashing remains
once per distinct valid map. This preserves structural rejection without
reintroducing duplicate file I/O.

The original distinct-map test changed a path already bound by prepared pins,
so it failed before exercising the new cache branch. The observed test repair
instead adds a permitted extra source path: two valid distinct maps require two
verifications, and a stale extra hash must fail `runtime_code_changed`.
The shared-map test also proves a new invocation re-verifies code rather than
using a persistent cache. A late equal-map malformed-Mapping regression was
requested from the root; this reviewer did not execute or repeat tests.

Reviewed repaired caller SHA-256:
`a798e8faba880c989d38877157b8aac432babfca2a9c1078220a8afc97ba4d71`.

## Remaining startup limits

The cache does not persist between host binding and inner approval validation.
The entry's 30-second startup window still includes stage/code/image validation,
approval/host-claim validation and keyless setup; the inner executor separately
includes approval/bound/runtime setup in its 30-second window. The 5-second
fresh guard, 30-second render, SQL/lock limits, 120-second call limit and hard
1,800-second process limit remain unchanged.

There is no remaining code-level blocker in the reviewed repaired cache.
Before fresh provider execution, finish its focused malformed-shape regression,
regenerate the stage against the final code hash and measure actual keyless
startup on that stage. A source inspection or old test count cannot establish
that the new stage fits either startup window. Fresh provider approval and
matching private displayed-source/browser/release evidence remain root-owned.

## Final scoped supplement

Re-read the final late-equal-map/list regression: it demonstrates the malformed
container produces the same binding identity, yet fails `binding_code_invalid`
before reaching a second file-verification call. The root reports all three
startup regression tests passed; this reviewer did not rerun them.

The host `validate_stage` now retains bytes read and verified in that invocation
and supplies them directly to the unchanged pure `preparation.prepare` function.
Input manifest pins, bounded/symlink-safe reads of both staged and current code,
watchdog checks, exact required prepare-path subset, signed review, runtime/code
hashes, image-source closure, image hash checks and final bound identity remain
enforced. The pure preparation repeats its own artifact/code integrity checks.
The replacement does not skip the old Temp/path fence: host `path_check` and
`stage_location` already enforce it before any read. No process-global cache or
authority is introduced; fresh dispatch/selection guards and all budgets remain
unchanged. Holding verified bytes increases transient local memory only within
the existing hard two-GiB container fence; no memory cap was changed.

No additional code-level blocker was found in these final two changes. Actual
keyless startup timing of the final regenerated stage remains root-owned.
Final reviewed caller SHA is unchanged; host SHA-256:
`276d39ffce59b605856a350bac383abd18d0903d88f6184d5cc29942e4659d95`.
Caller regression file SHA-256:
`5998587eceb85a775a723d6e62491f37d682cd0b3699892619119f4ab592304e`.
