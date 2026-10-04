# Reading-usefulness model load-only preflight

Date: 2026-09-28. Scope: operator-approved, public Mixedbread audit admission
only. Branch `main`, HEAD `6c02d6c` at startup. Existing working-tree changes,
the populated local database, root `.env`, original PDFs and Ask-off state were
preserved. No private Knowledge, Gemini, database, runtime policy or app image
was used.

## Artifact and ledger checks

The existing OS-Temp `cardchemy-reading-utility-20260928/bundle` was inspected
without any new GET. Its same-approval ledger reports `verified`, ten GETs and
95,960,919 received bytes, which includes metadata. The seven artifact files
total 95,958,700 bytes. Independent host-side SHA-256 calculations matched
all seven manifest entries; the graph matched pinned SHA-256
`15ef19a6de90be7d52b627f2c784107bd806e64826450f41fb75fa4f0179ab30`.
The manifest SHA-256 is
`2b7d441b1eb987502a7668355de4cf39f68bee3fd1dacea8d7c2dc1a97278182`.
The pinned source revision is `d1ba0a474aeed7c9fa96c3f57b128277580c5fae`;
the Apache 2.0 license and model-card declaration were checked by the loader.
This verifies the local artifact bytes against the acquisition manifest, not
the usefulness of its output.

## Isolated compatibility check

The tested `preflight.py` was copied byte-for-byte into
`scripts/preflight_reading_usefulness_bundle.py` for repeatability. A disposable
`cardchemy-answer-worker:0.1.0` container used `--pull never`, `--network none`,
`--cpus 4`, `--memory 2g`, read-only filesystem and public-bundle/script mounts,
non-root UID, dropped capabilities and no application credentials or retained
data mounts. The preflight verifies hashes/license, loads the tokenizer and
ONNX CPU session and examines declared input/output names. It never calls
`InferenceSession.run` and sends no request. The result was
`load_only_ready`: 7 files, 17 synthetic pair tokens, `input_ids` and
`attention_mask`, one output, zero model-run calls and zero network requests.
Measured loader startup was 4,811.69 ms, outer Docker command 6,362.568 ms,
and process high-water RSS 532,893,696 bytes, within the approved 20-second,
4-CPU and 2-GiB load bounds. ONNX Runtime emitted a harmless warning that it
could not persist its telemetry device identifier on the read-only filesystem;
the script succeeded and reported only aggregate metadata.

`backend/venv/Scripts/python.exe -m pytest -q
tests/test_reading_usefulness_preflight.py tests/test_reading_usefulness_download.py`
passed **11/11**. The new admission tests check every manifest hash, reject an
unapproved file, and use a fake ONNX session that raises if scoring is attempted.
`git -c core.safecrlf=false diff --check` passed. No model quality test was run.

## Stop boundary

The separately preregistered Illinois public PDF corpus acquisition stopped
after its schedule GET because at least one selected lecture PDF was not linked
from the official index; see [its receipt](2026-09-28-reading-usefulness-public-corpus-acquisition.md).
It has zero acquired PDFs, no independently reviewed 192-group fixture, and
therefore no training, calibration or heldout scoring is authorized yet.
The Mixedbread artifact is compatible with the local offline loader, but its
reading-usefulness quality remains unknown. The prior GTE candidate remains
stopped. Ask stays disabled. Correcting the public PDF list requires a fresh
preregistration and explicit bounded acquisition decision.
