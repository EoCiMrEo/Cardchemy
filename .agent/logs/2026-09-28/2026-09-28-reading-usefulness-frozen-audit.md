# Lane 6 public reading-usefulness audit freeze

Date: 2026-09-28 (America/Chicago). Branch `main` at `6c02d6c` with the
existing working tree preserved. The operator approved one networkless public
Mixedbread audit with four CPUs, at most 2 GiB added RAM, 20-second startup,
five-second p95 per 30 windows and 600-second total bounds. No Gemini call,
private Knowledge, database mutation, new indexing or Ask activation is part
of this audit.

## Pre-score admission and artifact identity

The independently reviewed public fixture passed the host no-score validator:
192 groups, 14 original CC BY 4.0 PDF files, SHA-256
`2180d4124417d5f4c9730134fa4d656957d3d6d92d4848f2f41d96927d8020d8`.
Two blind reviews and adjudication were assembled for train and evaluation,
with final train count strata 24/24/24/24 and calibration and heldout each
12/12/12/12 for zero through three useful cues. Separate candidate-rights
and semantic-split receipts bind all 768 windows and 192 groups. Rights review
applies to selected lecture text, not third-party page media. The validator
checks receipt consistency and exact PDF offsets; it cannot prove a human
judgment correct by itself.

The reviewed fixture's fourteen evidence paths used host Windows absolute
paths. `scripts/stage_reading_usefulness_container_fixture.py` validates it,
copies exactly those fourteen evidence JSON files without changing their
bytes, and rewrites only the fourteen path values to a fixed Linux `/tmp`
mount. Reversing those path changes recovers the original fixture object; the
groups SHA-256 stays
`14bdf0f4e6251d3eb3515b76c29a14cf78b67e6a380e24c439e3aa77be212799`.
The staged fixture SHA-256 is
`7b5cc3c6a0ded1f0fd338562e9d7860501035ca782981c95bd92c32459252219`.
The staging and fixture focused suite passed 43 tests. The final fixture's
literal PDF windows may end in newlines; the validator now allows that exact
span while still enforcing the original source offset and SHA. Its focused
suite passed 45 tests before staging.

The pinned cached Docker image ID is
`sha256:512345a7d0fe69953757f0a0eea429de9167e568ceb2ebcd9187888cc1d6c12c`
(487,244,866 bytes). Docker server is 29.8.0; the image has Python 3.11.16,
pypdf 6.19.0, ONNX Runtime 1.30.0, tokenizers 0.22.1 and NumPy 2.4.1.
The seven-file public model bundle manifest SHA-256 is
`2b7d441b1eb987502a7668355de4cf39f68bee3fd1dacea8d7c2dc1a97278182`.
Its earlier networkless load-only admission called no model inference.

The first combined Docker validator mount failed with `Access is denied`:
the staging script's private Windows ACL denied Docker Desktop access. An
isolated public-only mount copy inherited the parent ACL; all fifteen files
matched the staged hashes byte for byte. A disposable non-root write probe
on separate ledger/output mounts succeeded. The exact networkless image then
validated the mounted fixture, all fourteen PDFs, exact offsets, rights and
review receipts with status `fixture_validated_no_scoring`. The real one-shot
ledger was empty at this point.

Five public audit scripts were copied byte for byte to a dedicated read-only
mount. The runtime manifest SHA-256 is
`d97a204cae0eff3375f43c5363952c9a325bb0360c0904b389e5a254c5cefc0b`.
The scoring harness SHA-256 is
`3f569232861346b5b8f31459b8cfe1601a95d1d16a48c39134b0a46d7f7824a6`;
validator SHA-256 is
`4cdc4c04b90fb2153b5f2acc26c1bbf5e1b02c5beadf0d3e918715662d19b978`.
The remaining import hashes are in the runtime manifest and will be checked
again after the run.

**External freeze pin, recorded before the first model score:**
`c3ff9542e38ffe5c3adbd2e91e906c8171c4244bf940c6922646a6da5ffdea0d`.
The receipt was created with `freeze` inside the same image, network and
resource sandbox; `verify`, default no-score preflight and the one approved
inference attempt still follow. A public pass will not satisfy the separate
retained-course/release gates or enable Ask.

## One approved score and stop

The exact frozen-input `verify` passed in the networkless image. The default
runner also passed with `model_inferences=0`, no provider requests and no
database writes. Immediately before scoring, all five script hashes, fixture,
runtime manifest and externally recorded freeze digest still matched; the
fixed real ledger had zero files and the output leaf did not exist.

The single approved `--execute-approved` attempt then ran in the immutable
image with `--pull never`, `--network none`, four CPUs, a 2 GiB cgroup memory
and swap cap, a read-only root filesystem, dropped capabilities, non-root
UID 10001 and only dedicated public read-only input mounts. The fixed ledger
now contains both exclusive parent-attempt and child-claim markers. Its
terminal result is **`calibration_rejected_no_heldout`**:
`candidate_passed=false`, `heldout_scored=false`, `release_gate_passed=false`,
zero provider requests and zero database writes. The output contains only
`audit-result.json` and matching `supervisor-result.json`; no calibration rule
was selected or heldout grades produced. The result receipt SHA-256 is
`958e7c2600c830f7526b1150ca84da9d163dd6aae577152878c88e0cba1a1291`.

The runner made 20 local model calls on 576 train/calibration pairs, with at
most 241 pair tokens. Startup took 2,120.487 ms, the 30-pair pool p95 was
4,363.068 ms, peak added RAM was 811.168 MiB and total elapsed time was
62,237.328 ms; all resource limits passed. On 48 calibration groups, the
raw pair-logit top three contained a useful cue in all 36 groups with at least
one useful cue, and 68 of 72 available useful cues appeared within those raw
top-three slots. That is a diagnostic ranking observation, **not** a passing
display rule. No global threshold met the preregistered calibration/no-match
display gate, so the reported zero displayed cards is the deliberate sentinel
summary after rejection, not a deployed selection. The heldout remains blind.

After the run, all five staged script hashes, fixture, runtime manifest and
freeze receipt still matched their pre-score pins. The consumed ledger and
receipts are retained in isolated OS Temp. The attempt will not be replayed
or tuned under this approval. The still-disabled Ask policy and the populated
database volume, root `.env`, original PDFs and backups were untouched. A
new reviewed proposal and explicit operator approval are required before a
different scorer/calibration experiment or plan expansion.

The operator subsequently approved a **separate** selective-navigation
candidate and one new offline public audit, documented in
`2026-09-28-selective-source-navigation-recommendation.md`. That approval does
not reset or reuse this consumed ledger. The new candidate has its own
pre-score freeze, distinct one-shot ledger and separate result.

After the Windows-to-Linux public-fixture transport script and its negative
tests were added, the full keyless backend offline suite passed **2,204** tests,
with 147 skipped and two live tests deselected, in 174.93 seconds. The
repository context check passed 37 required files, 78 active guides and
1,405 local links at that point; `git -c core.safecrlf=false diff --check`
exited zero. A read-only Compose inventory still showed all retained local
application services healthy. None of these checks changes the failed public
quality result or completes the independent release gate.
