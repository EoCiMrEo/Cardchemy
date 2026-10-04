# Public digest secret-scan provenance and narrow repair

Date: 2026-10-01 (America/Chicago). The new isolated working-tree snapshot
produced four `generic-api-key` findings; the earlier report contained none.
The snapshot commit was temporary verification history, not a commit on main.
No credential value, scanner match or private content is copied here.

Independent review identified three digest-only findings. Root verified the
September 30 log launcher digest against SHA256 of
`scripts/launch_fresh_public_source_id_v2_augmented.py` (equal). The October 1
image-access mapping log and feasibility fixture contain the same frozen
public mapping digest used by the summarizer; they are integrity bindings,
not authentication material. Historical log bodies and pins remain unchanged.

`.gitleaks.toml` adds exactly three generic-api-key exceptions, each combining
an exact file path AND anchored exact digest-bearing source content. There is
no file-wide, directory-wide or rule-wide suppression. The privacy guide's
prose match was clarified from a slash-separated encryption phrase to explicit
archive/file/decryption exclusions; export behavior is unchanged and that
file receives no scanner exception.

A subagent stopped at its account usage limit before writing the config; root
completed the narrow repair. The old failing report was retained at
`artifacts/security-failed-before-repair-20261001`. The identical complete
security harness is running after the patched frontend image. Results will
be appended only once authoritative reports are complete. No Git history,
root .env, populated volume, PDF source or provider key was modified.

## Exact-pattern verification and complete gate

The first draft full scan still flagged the three hashes because anchored
whole-line patterns did not match the scanner fragment and Windows line
endings. The exceptions were repaired to exact scanner-match literals, still
AND-bound to the exact file, with only LF/CRLF tolerance for the two-line
public digest. The pinned [Gitleaks configuration](https://github.com/gitleaks/gitleaks/blob/v8.24.2/README.md#configuration)
and [detector source](https://github.com/gitleaks/gitleaks/blob/v8.24.2/detect/detect.go)
were checked. A public-only three-file scan passed. Two synthetic controls
then changed the digest in the same file and put the original digest in a
different file; both remained detected. The scratch was removed.

The identical full security harness then passed Git-history/worktree secret
scans and HIGH/CRITICAL vulnerability checks for backend, OCR backend and
patched frontend images. Reports, three SBOMs and verified SHA256SUMS remain
at `artifacts/security`; temporary scanner source/history/image archives
were removed. The temporary snapshot commit is
`7ea24e2cf148b235963660c744d9b06807429146`; real main/HEAD is unchanged.
Earlier failures remain in archived report directories. This local scan does
not establish hosted CI or future changed-image security.
