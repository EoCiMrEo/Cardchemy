# bcrypt 5 password compatibility

## Scope and starting context

The operator authorized merging the open dependency PRs and the completed RAG
feature into protected main. PR #10 upgrades bcrypt to 5.0.0, whose stricter
72-byte input limit breaks Passlib 1.7.4's backend initialization. This work was
isolated to the initially clean `dependabot/pip/backend/bcrypt-5.0.0` worktree at
`303daa1`. Normal merge `fff0382` incorporated feature commit `4a5bea7`; normal
merge `01bbdb1` then incorporated protected main `62796df`, including the hosted
database scanner ownership fix. Shared history was preserved.

Read root guidance, canonical orientation/project/module maps, authentication
architecture/operations, ADR 009, dependency/testing/runtime guides, agent
governance and relevant password/phase logs before implementation. Confirmed
the old algorithm against installed Passlib 1.7.4 source and its
[published bcrypt_sha256 specification](https://passlib.readthedocs.io/en/stable/lib/passlib.hash.bcrypt_sha256.html).

## Implementation and preserved contracts

- Added `backend/app/services/passwords.py` and delegated `AuthService` password
  operations and its cost-12 timing hash to the maintained direct bcrypt backend.
- New records retain the exact bcrypt_sha256 v2 wrapper, salt-keyed HMAC-SHA256,
  padded standard base64 and bcrypt cost 12. Full UTF-8 passwords, including NUL
  and suffixes beyond 72 bytes, participate in the prehash.
- Retained v1 SHA256/base64 wrappers, raw 2/2a/2b/2y records, original 2 password
  repetition, raw first-72-byte semantics/NUL rejection and Passlib's unused
  bcrypt64 padding normalization. Malformed/unsupported records fail closed
  without password, hash or exception logging. Existing records need no schema
  migration, bulk rewrite or forced reset.
- Removed Passlib from the direct input and regenerated both hashed locks using
  `backend/scripts/lock_dependencies.ps1` on Windows Python 3.13. The lock keeps
  pgvector 0.5.0 and Windows colorama, strips extras and excludes unconditional
  uvloop introduced by the bot's Linux-generated lock.
- Added independent published vectors and 17 synthetic fixtures generated once
  using the prior Passlib 1.7.4/bcrypt 3.2.2 runtime. Tests exercise v1/v2/raw
  compatibility, UTF-8 byte boundaries, long/full passwords, NUL, original 2,
  padding aliases, random salts, malformed records and incorrect suffixes.
- Extended the real image probe to require Passlib's absence and verify current
  long Unicode/NUL and historic v2 records. Updated auth/architecture/dependency
  guides, maps, changelog and accepted ADR 013 with the compatibility boundary.
- Added the owned password module to the critical coverage budget at 95%, above
  the existing authentication floor of 88%. The offline run measured all 54
  statements and all 16 branches covered (100%). Five percentage points of
  measured headroom allow small future changes while retaining a strong gate
  for security-sensitive compatibility; no existing floor was reduced.

## Verification

| Check | Result |
| --- | --- |
| Hash-locked isolated Windows Python 3.13 installation and `pip check` | Passed; bcrypt 5.0.0 and pgvector 0.5.0 installed, Passlib absent. |
| Password/auth validation/session/token/invitation/authorization targeted contracts | 95 passed in 28.57 seconds. |
| Full backend offline line/branch suite | 678 passed, 82 service/live cases deselected in 205.80 seconds; no provider requests. |
| Coverage floors | Overall line+branch 78.12% >= 73%; lines 81.68% >= 77%; branches 63.00% >= 55%; auth 90.23% >= 88%; password module 100% >= newly added 95%; all other scoped floors passed. |
| Supported Python 3.11 Alpine backend image and isolated native runtime probe | Built and passed, including full-password compatibility. Image configuration `sha256:73c16c8ac9d4ff0f1aa2b77acecb06365248f139164fb027a85c1e7a4a5c8c9f`. |
| Supported Python 3.11 Alpine OCR backend image and isolated native runtime probe | Built and passed, including image-only PDF OCR and full-password compatibility. Image configuration `sha256:41f98b7a3ff3eadf6cfde6eeb67c35c43558179776e109681c856bad057cf93c`. |
| Current-main database diagnostic regressions | 4 passed after incorporating current main. |
| CI structure/context and `git diff --check` | Passed; context initially validated 37 required files, 66 guides and 886 local links before this evidence record. |
| Fresh strict hash-locked Python advisory audit | Passed with no known vulnerabilities; JSON report retained as an ignored artifact. Initial relative report creation failed after scanning; an absolute output path completed successfully with exit 0. |
| Exact backend image security scans | Delegated sequentially to the dependency image-verification agent to avoid concurrent large advisory caches; outcomes pending. |

Reproduce the targeted suite from `backend` with
`python -m pytest tests/test_password_hashes.py tests/test_auth_validation.py tests/test_auth_sessions.py tests/test_auth_tokens.py tests/test_invitations.py tests/test_authorization.py -q`.
The measured offline run used
`python -m pytest -q -m 'not postgres and not mailpit and not smtp_tls and not ai_live' --cov=app --cov-branch --cov-report=json:coverage.json`,
followed by `python scripts/check_coverage.py backend/coverage.json` from root.
The advisory command is
`python -m pip_audit --require-hashes -r backend/requirements-dev.txt --strict`.
The two image probes use `python scripts/check_images.py backend --image cardchemy-backend:pr10-bcrypt5`
and `python scripts/check_images.py backend-ocr --image cardchemy-backend-ocr:pr10-bcrypt5`.

## Limits and cleanup

No operator `.env`, credentials, user records, database data or application
volumes were inspected or modified; all password fixtures are authored synthetic
test inputs. Image probes used generated isolated settings with networking
disabled and removed their own containers. The disposable development venv and
coverage/advisory artifacts remain ignored in this verification worktree.
No paid AI, external SMTP, live password-reset browser or real production
operation ran. The full Windows offline suite and actual Python 3.11 runtime
probes provide distinct evidence; the full Python 3.11 suite and PostgreSQL,
Mailpit/journey/security gates still require current-head hosted CI before merge.
No push or GitHub merge was performed by this subtask.
