# Matching v8 secret and container gate completion

## Scope and starting evidence

Bounded independent continuation of Lane 6 release checks. The shared checkout
is dirty `main` at `6c02d6cf063acf83f4da5c08cfc4a3aa2c94be57`; preserve existing
changes, populated volumes, root configuration, original PDFs and provider
history. Read root guidance, orientation, maps, architecture/ADR ownership,
testing/CI command authority and relevant v8 records before changes.

The prior full security run completed at `2026-10-03T19:25:43.882806+00:00`.
Its metadata names only `git-history-secrets` as failed. Worktree secret and
all three image vulnerability gates were clean. Both Gitleaks findings were
`generic-api-key` at line 61 in the separate v7/v8 private trial planners.
The prospective exported snapshot was
`d308dcf4d31467a1d0c82f707669537f7c3127d9`.

## Finding verification and narrow correction

AST inspection identifies the identical values as a 64-character hexadecimal
SHA-256 pin named `trusted_review_key` within `FROZEN_PINS`. The review scorer
compares this fingerprint with SHA-256 of an Ed25519 **public** review key,
then verifies a signature. These values are public-key fingerprints, not
private signing keys, provider credentials, or authorization tokens.

Add one `generic-api-key` allowlist requiring both one of the two exact planner
paths and the exact unchanged key-name/fingerprint match. No blanket tests/logs/path exclusion,
hash-wide exclusion, scanner suppression or threshold change was introduced.
The previous report SHA is
`140d174d7b9113da540645e6899cd7b2fbada3d070b7ecab412f948b08e92b9b`.
All nine previous report files were copied and SHA-compared before the rerun
under the ignored, newly owned verification directory
`.agent/.verification/security-before-v8-allowlist-20261003T220747Z-c34da837`.
No matched source line or credential value is recorded here.

## Matching identities and verification

The documented command is
`backend\venv\Scripts\python.exe scripts/test_security.py --image-tag 0.1.0`.
Its scanner export excludes operator environment files and ignored/private
artifacts. Only the public advisory database downloads before networkless
source/image scans. Reports, SBOMs and SHA manifests remain in ignored
`artifacts/security`; no provider, retained database or application setting is
read or changed by this task.

Expected immutable image IDs:

- backend: `sha256:7002fd38e80dbe3ac89e4ab64e305944848d4cdd594de2bf41d229237a30af41`
- backend OCR: `sha256:2dde663bb4104b38fc1336d85285e08c20789684f1aae907d51ff52fe1f9284d`
- frontend: `sha256:e672a910c14e69f68fcecd974fac4435c258c0d12fcdbefca2b46889767ef694`

The initial correction used an exact line target, but Gitleaks still reported
the identical two fingerprints. Session `52183` completed with only the
Git-history gate failing; all other gates passed. The final correction uses
Gitleaks' exact finding-match target instead. All nine reports from that attempt
were preserved and SHA-compared in the separately owned ignored directory
`.agent/.verification/security-before-v8-match-repair-f2cd4f5c`; its metadata SHA
is `b26d1b1ac5c4cd3a4a0c42c80481bd9f002efd20e28935b2474ef2d9a3778533`.

One final documented command was already started as session `75158` before the
parent requested no further full-image reruns. It completed with **exit 0**;
no additional broad run was started. Fresh metadata is dated
`2026-10-03T22:12:54.287608+00:00`, with exported snapshot
`dee484eccb26588ce97c3dc06fa5cb0ce22e24f7` and `failed_gates=[]`.

Gitleaks scanned 93 history/export commits (about 15.01 MB) and found zero
secrets. Worktree Trivy secret scanning passed. The backend, OCR backend and
frontend reports each contain zero HIGH/CRITICAL vulnerabilities, and their
immutable IDs match the three expected identities above. Three CycloneDX SBOMs
are retained. All eight files named in `SHA256SUMS` were independently hashed
and matched. The metadata SHA is
`a4bb364670660663fa5d9144de661257a36e04d9567d1258d0e623ed221fb45e`;
the SHA manifest itself is
`6311a28b4b27a0f6ed017f32fc7c7b973ac4ae4e5d68b6208211f543b7e9d2c5`.
The owned scanner export directory was removed by the harness. Preserved prior
failed report directories remain ignored. Tool warnings about the Alpine EOL
table and source-only license detection did not suppress vulnerability scanning
or alter the configured gates.

Local security evidence does not prove hosted CI, protected
merge, private-source quality, Ask activation, or overall Lane 6 completion.
