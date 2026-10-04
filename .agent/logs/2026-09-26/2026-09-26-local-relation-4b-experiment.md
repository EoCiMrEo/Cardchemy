# One approved Qwen3-4B local experiment

## Starting context and authority

- Continue Lane 6 on `main`, HEAD
  `6c02d6cf063acf83f4da5c08cfc4a3aa2c94be57`. Preserve the existing broad
  remediation diff, real root `.env`, populated database and running services.
- Follow root AGENTS, current orientation/source and the preceding
  [public calibration evidence](2026-09-26-local-relation-calibration.md).
  The 0.6B audit completed 48 calibration cases with only seven correct global
  labels; no rule was selected and heldout inference remained closed.
- The owner explicitly approved the concrete single Qwen3-4B proposal before
  this plan extension or implementation. Bounds: 3 GiB artifacts, 4 GiB
  additional peak RSS, 5 GiB total container memory, four CPUs, 30-second hard
  startup, ten-second complete-check p95 and 600-second hard public audit.
  No Gemini calls, private egress, runtime activation or automatic next model.
- Updated the Lane 6 approved extension; seven checkboxes remain 3/7 complete.

## Frozen experiment

- Repository `onnx-community/Qwen3-4B-ONNX`, revision
  `98ddba15d05dede4435afb63f13280abcdbc2a48`, CPU export
  `onnxruntime/cpu_and_mobile/cpu-int4-kld-block-128`.
  Public metadata reports eight files totaling 2,897,393,599 bytes.
- Keep fixture SHA256
  `f87855899d54ce89f11979fe1876f6c5495c2803f94c886e38de293f39b51369`,
  unchanged joint instruction, complete source binding, 512-token ceiling,
  full-vocabulary winner, minimum label mass .50 and global margin .01.
  Select only the strictest passing confidence floor from .80/.65/.50/.25/.10.
  All 48 calibration decisions must be correct and conclusive before the
  frozen rule sees any heldout inference; require all 24 heldout positives and
  24 conclusive negatives, zero false acceptance.
- Validate exact lengths/digests and external-data confinement before ORT
  loading. Check actual graph metadata against the CPU contract; pinned ORT
  compatibility is unproven until measured. No dependency installation is
  authorized by this experiment.
- Add an external supervisor for startup/whole-run deadlines; per-inference
  ORT cancellation does not bound session construction. Reserve time for one
  complete check and cleanup; an incomplete run remains failure.
- Public artifacts stay ignored and outside runtime mounts. Logs/output retain
  only fixed statuses, numerical aggregates and public artifact identities.

## Work and verification

Implementation, download preflight, independent review and measured outcome
will be recorded below as they occur. No success or activation is claimed here.

### Implementation and pre-inference verification

- New `scripts/local_relation_4b_candidate.py`: literal eight-file pins;
  streamed length/digest verification; closed metadata-only ONNX protobuf
  descriptors using existing installed protobuf, not a new dependency.
  Digest-checked small public graph metadata confirms IR10, ONNX21 and
  Microsoft opset1, 74 inputs/73 outputs, 72 float32 KV inputs for 36 layers,
  no position-ID input and full-sequence float32 logits with vocabulary151,936.
  All 834 external tensor ranges reference only pinned adjacent data bytes.
  Validate graph and session contracts before one decision-token observation.
- Exact existing ORT1.30.0 CPU runtime, four inference threads/one inter-op,
  sequential execution, ten-second per-check cancellation; global winner,
  nonlabel competition and full softmax observation remain unchanged.
  Four threads were declared before new-model inference under the approved
  four-CPU ceiling. No old scorer, prompt, model factory or dependency changed.
- New `scripts/calibrate_local_relation_4b.py`: supervised child with hard
  startup30s/whole600s, complete-case absolute deadlines, two-second cleanup
  reserve, bounded aggregate-only pipe and no inherited operator credentials.
  Child settings are disposable process values with loopback port1; no root
  `.env`, app DB or provider credential is used. Conservative memory guard
  counts entire child high-water RSS plus parent growth; it is stricter than
  subtracting a child baseline and the metric is labelled accordingly.
  Unavailable measurements fail closed. Interrupted heldout state is unknown
  unless its fixed start event was observed; never assert untouched after an
  ambiguous supervised stop.
- New `scripts/download_local_relation_4b.py`: no app/settings import; literal
  approved manifest only, task-specific ignored destination, exclusive partial
  files and exact byte/hash validation before finalization. No overwrite or
  retry; aggregate artifact requests exclude possible HTTP CDN redirects.
  Download bounds are 3 GiB/30 minutes, separate from the600s public audit.
- Two independent agents reviewed candidate graph/external-data contracts and
  supervisor/calibration gates. Findings fixed before inference: EOF cleanup
  race, 96-case aggregate bounds, required frozen identity on success,
  malformed protocol type handling, interrupted heldout truthfulness,
  conservative memory naming and unavailable measurement handling.
- Root combined targeted check: **148 passed, one Windows symlink-permission
  skip**; mocked root/file/ancestor symlink guards passed. Covers candidate,
  supervisor/download and unchanged small classifier/calibration contracts.
  Context validated **37 required files,76 active guides,1193 local links**.
  Current retained worker independently reports ORT1.30.0, protobuf7.36.2 and
  tokenizers0.22.1. All eight retained app services are healthy.
- Approved public download started once after guards passed. No new-model
  session or inference has occurred at this checkpoint. Full backend offline
  verification is running; final outcome will be appended separately.

### Offline result and download status

- Full backend offline completed **1,257 passed,120 skipped,2 deselected** in
  137.97seconds. The source/test collection preceded three additional supervisor
  robustness cases and the explicit provider-setting name correction; those
  focused contracts subsequently passed37/37 in the delegated check. Root will
  verify final targeted scope before inference. Skips are not live or deployment
  evidence; a Windows real-symlink permission skip retains mocked guard coverage.
- Operator environment/root `.env` remains untouched. The real setting used
  by the inert child is `FLASHCARD_AI_PROVIDER_ENABLED=false`, with Ask also
  disabled; an earlier unused generation flag was corrected before inference.
- Downloader verified the small graph. At the content-free status checkpoint,
  the external-weight partial was still zero bytes despite an active process.
  Do not infer a provider/HTTP cause from this state. Added an external Windows
  watchdog for the exact task processes (PID/start time/command identity checked)
  to stop them at30minutes if a blocked streamed read prevents an internal
  deadline check. No automatic repeat or alternative model follows a stop.
  No new-model session/inference has occurred.

### Correction: Windows listing and bounded public transport recovery

- The prior zero-byte directory-listing observation did **not** mean no bytes
  had been written. A direct read-only open-handle end seek reported
  381,681,664 bytes. Windows exposed stale directory size while the writer was
  open. Correct the inference: the public transfer was progressing; no HTTP
  failure or zero-write claim is supported by the listing alone.
- The self-imposed initial30minute transport bound may not accommodate this
  observed transfer speed. Within the same owner-approved immutable3GiB public
  bundle scope, prepared **one deliberate Range continuation** after the original
  process has exited and closed its handle. It is not an AI/provider attempt,
  audit repetition or another model candidate. An independent read-only agent
  confirmed the same transport scope and reviewed the concrete integrity guards.
- Recovery requires an exact206/Content-Range/remaining byte count, identity
  encoding, regular single-link partial with matching file identity/seeded size,
  seeded incremental SHA plus complete on-disk SHA before finalization, and a
  single-use marker. Default execution never resumes; no second continuation
  or automatic replay follows failure. Public continuation gets a hard120minute
  watchdog, justified by measured local transfer speed. Audit bounds remain
  startup30seconds/600seconds public run and approved memory/CPU ceilings.
- Latest root targeted scope including resume corruption/range/identity and
  unavailable-memory controls: **161 passed, one Windows real-symlink skip**.
  The original transfer is still running; no Range request has been made and
  no new-model session/inference has occurred at this checkpoint.

### First transfer ended; one continuation started

- Initial bounded transfer ended `download_unavailable` after two public
  artifact HTTP requests. The small graph had verified; the incomplete public
  external data file contained **1,201,668,096 bytes** when read through a
  newly opened handle after process exit. Failure cause is not retained by the
  aggregate downloader and must not be guessed. No model session or inference
  ran. The original downloader process count was zero before continuation.
- Independent final read-only review found no blocker in the one-shot Range
  recovery. Root targeted scope after the latest corruption/protocol cases:
  **161 passed, one Windows real-symlink skip**. The continuation was started
  once with a single-use marker and fixed120minute watchdog. Its outcome is
  pending; no additional repeat is authorized by this one-shot mechanism.

### Interrupted continuation and separately approved final transport attempt

- A later turn interruption stopped the Range downloader. Authoritative
  process inspection found **zero** task downloader processes. A new read-only
  handle measured **1,886,627,030 of 2,885,434,880 bytes** in the task partial.
  The first continuation's single-use marker remains. We do not know whether
  the turn interruption or a transport failure ended the process; its final
  aggregate output was not observed. No session/inference ran.
- The owner explicitly approved **one more** bounded Range continuation for
  the exact same pinned public export. No Gemini call or private data transfer.
  This modifies only transport authorization, not the 3 GiB artifact, 4 GiB
  additional RSS, 5 GiB container, 4 CPU, startup30s, complete-check10s or
  public-audit600s experiment limits.
- Added a *separate* process-only approval value and
  `.range-continuation-2-used` exclusive marker; preserved the first marker
  instead of deleting it. The original public downloader process is gone.
  The same exact206/range/identity/whole-file SHA and120minute watchdog remain.
  Keyless second-continuation authorization/single-use contracts pass **19/19**.
  This is the final authorized transfer attempt; its result is pending.

### Final approved transfer outcome

- The second Range continuation returned `download_unavailable` after one
  public artifact request. Its only verified complete file remains the pinned
  519,634-byte ONNX graph; the external-data partial stayed at **2,636,841,394
  of 2,885,434,880 bytes (91.38%)**. A fresh handle observed the same length
  after process exit. Both one-use continuation markers remain, and the task
  downloader process count is zero.
- The aggregate deliberately omits the exception and any signed CDN URL. It
  does not distinguish a transport interruption from a response or filesystem
  failure, so no cause is asserted. The remaining six public files were not
  requested. No model session or inference ran; provider requests, private
  cases evaluated and database writes were zero for this transfer.
- The approved one-use transport envelope is exhausted. Do not erase a marker,
  resume or infer from a partial export. Public model calibration and all
  downstream private/maintained quality gates remain unrun. The currently
  selected Ask policy and release limits remain unchanged.

### Separately approved segmented continuation and offline finalization

- The owner approved one additional **public-only**, frozen-state transfer:
  at most ten 64 MiB Range requests, 260,032,571 additional bytes, 120 minutes,
  zero retry, exact `206`/range/length/identity checks and full pinned hashes.
  The one-use segmented marker was created; no Gemini, private corpus or model
  execution occurred.
- Four Range requests received the remaining **248,593,486 bytes** of the large
  external-data file. The downloader then reported `download_unavailable` at
  `failure_stage=finalize`, with four artifact requests. The finalization
  failure cause was not exposed and is not inferred. It did not request the six
  remaining small files.
- After the process exited, an independent read-only host hash measured the
  complete **2,885,434,880-byte** `model.onnx.data.part` at the literal pinned
  SHA-256 `d6003acd70841b99a44ce4c21d13dc42244e3ec3b7c12d70919f9b55440bbc45`.
  The exact source and absent same-directory target were checked, then a single
  local `Move-Item` finalized `model.onnx.data` without network access. The
  graph and data are now complete; the other six files and whole-bundle
  verification remain pending. All three one-use markers are preserved.
- No model session/inference, provider call or database write occurred. A new
  network request for the six files requires a new explicit owner decision;
  no remaining-request allowance is inferred from the failed one-shot process.

### Approved six-file completion ended with one public file missing

- The owner approved one frozen-state transfer of the six remaining public
  metadata/tokenizer files: at most six `200` requests and 11,439,085 bytes,
  no network retry, ten-minute per-file and thirty-minute total hard bounds.
  Both complete large files were rehashed before any HTTP request, and the
  exclusive fourth marker was retained.
- Five files passed incremental and on-disk SHA checks and local finalization:
  tokenizer, model/config and chat-template assets. The sixth request for the
  pinned 519-byte public `README.md` ended at safe stage `transport_open` before
  receiving bytes. The one-shot run made six requests and transferred
  11,438,566 bytes. The exact connection cause was not retained and is not
  inferred. No model session/inference, Gemini request or DB write occurred.
- The seven finalized files remain in the ignored task-owned artifact directory
  with all four historical markers. The eighth file and whole-bundle integrity
  check remain open. No additional GET is inferred from the failed six-request
  envelope; a new explicit owner decision is required for any final request.

### One-file attempt exposed an artifact-path bug

- The owner approved one more `README.md` GET under a 519-byte/one-request,
  no-retry envelope. That request again stopped at `transport_open`, with zero
  bytes transferred and no model/provider/database execution. Its exclusive
  marker remains; the exact HTTP status was not retained.
- Independent inspection of the pinned public repository tree showed that the
  **519-byte `README.md` is at the repository root**, whereas the seven CPU
  export files are under `onnxruntime/cpu_and_mobile/cpu-int4-kld-block-128`.
  The downloader had unconditionally prepended that export directory to every
  filename, so its README URL was wrong. This is a concrete artifact-path bug,
  but it does not prove which HTTP error the suppressed `transport_open` saw.
  See the [public repository root](https://huggingface.co/onnx-community/Qwen3-4B-ONNX/tree/98ddba15d05dede4435afb63f13280abcdbc2a48)
  and [CPU export directory](https://huggingface.co/onnx-community/Qwen3-4B-ONNX/tree/98ddba15d05dede4435afb63f13280abcdbc2a48/onnxruntime/cpu_and_mobile/cpu-int4-kld-block-128).
- A central URL correction and offline contracts are being prepared before a
  new request is considered. The first four one-use markers plus the README
  attempt marker are preserved, and the bundle remains unverified/inactive.

### Corrected root README request did not complete

- The downloader now resolves the pinned `README.md` at repository root and
  rejects unknown artifact names; the seven export URLs remain under the CPU
  ONNX directory. Offline downloader contracts passed **170 tests**, with one
  Windows symlink test skipped, and context validation passed 37 required
  files, 76 guides and 1,202 local links. No network was used for this fix.
- The owner separately approved one corrected-root GET for the final public
  519-byte file. The exact URL was
  `https://huggingface.co/onnx-community/Qwen3-4B-ONNX/resolve/98ddba15d05dede4435afb63f13280abcdbc2a48/README.md`.
  The call returned the safe aggregate `download_unavailable` at
  `transport_open`: **one request, zero received bytes**, seven runtime files
  still hash-verified, no model load, no Gemini and no DB write. The HTTP or
  transport cause was intentionally not retained and is unknown.
- The separate `.corrected-readme-used` marker is retained with the five older
  one-use markers. `README.md` is still absent; the eight-file integrity gate
  and public calibration have not run. Do not retry that approval or treat a
  seven-file runtime as the complete approved artifact bundle. Any changed
  experiment precondition requires a new explicit owner decision.

### Prepared offline seven-file diagnostic, not yet executed

- Inspection found that `README.md` is not read by the scorer, tokenizer,
  ONNX session, fixture or prompt. The seven actual runtime files are pinned
  and digest checked. A separate `--runtime-only-diagnostic` option now requires
  that README be absent, validates those seven artifacts and graph/config, and
  keeps the default eight-file gate unchanged. The supervisor carries the
  literal incomplete-bundle label and forces `candidate_passed=false` even if
  every public case were correct. This cannot activate any runtime policy or
  satisfy Lane 6 release quality.
- Keyless targeted candidate/calibration/downloader checks passed **182**, with
  one Windows symlink skip. Context validation passed 37 required files, 76
  guides and 1,206 local links. No network, model inference, provider or DB
  action ran for this preparation. The owner was asked separately whether to
  permit one seven-file public CPU diagnostic within the prior resource caps.

### Owner-approved seven-file public CPU diagnostic outcome

- The owner explicitly approved one offline diagnostic with the seven pinned
  runtime files, despite the missing model card. The default eight-file audit
  and release gate remained unchanged. The local Docker daemon reported about
  7.64 GiB available, the expected answer-worker image ID matched, and the
  eight normal app services were healthy before the run.
- One disposable Docker container ran with `--network none`, read-only root
  and file mounts, no capabilities, user `10001`, four CPUs and a 5 GiB memory
  cap. It used the frozen 96-case public fixture and the explicit diagnostic
  flag. The supervised result was `supervisor_startup_timeout` at **30,026.9
  ms**, before a validated startup event or any case result. Peak child plus
  parent growth was **94.34 MiB**. The report retained
  `incomplete_bundle_diagnostic=seven_runtime_files_verified_readme_missing`,
  `candidate_passed=false`, zero provider calls, zero DB writes and zero
  private cases. It conservatively marked heldout execution `null` because a
  killed child cannot prove that it remained unopened.
- This is a startup/resource-budget failure, **not a semantic model-quality
  measurement**. It cannot establish that a larger model would answer better
  or worse, or that the model is unrelated to the Ask failures. No retry,
  timeout increase, artifact download or new candidate follows from this run.
  The audit container exited; the eight normal app services remained healthy.
  The active Ask policy, plan checkboxes and runtime resource limits did not
  change.
