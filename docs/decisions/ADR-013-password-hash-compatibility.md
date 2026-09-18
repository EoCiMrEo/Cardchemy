# ADR-013: Preserve password records with direct bcrypt

## Status

Accepted 2026-09-18 for the authorized bcrypt 5 dependency pull request.

## Context

Passlib 1.7.4's bcrypt backend initialization fails with bcrypt 5's rejection
of input exceeding 72 bytes. Existing accounts use Passlib bcrypt_sha256 v2,
and the verifier previously also accepted v1 wrappers and raw bcrypt records.
Dependency upgrades must preserve sign-in and the full-password contract.

## Decision

Use the maintained direct bcrypt backend. New records keep the exact
`$bcrypt-sha256$v=2,t=2b,r=12$salt$digest` encoding, UTF-8 input,
salt-keyed HMAC-SHA256 and padded standard-base64 prehash. Retain verification
of v1 SHA256/base64 wrappers, including 2a/2b variants, and raw 2/2a/2b/2y
records. Preserve Passlib's raw-byte truncation, NUL rejection, original 2
password repetition and unused bcrypt64 padding normalization. Unsupported
formats and malformed records fail closed without logging sensitive content.

## Rationale

This removes the incompatible wrapper dependency while retaining the
[published Passlib algorithm](https://passlib.readthedocs.io/en/stable/lib/passlib.hash.bcrypt_sha256.html).
The wrapper prehash is always 44 bytes, so bcrypt 5's stricter length rule
does not truncate current passwords. Historic test records and published
known vectors prove compatibility independently of a new-code round trip.

## Consequences

No schema migration, bulk password rewrite or forced reset is needed.
Raw legacy hashes still ignore bytes after 72; resets create full-password
v2 records. This compatibility module is security-sensitive and requires
historic-vector, Unicode/NUL, malformed-record and wrong-suffix regressions
when changed. It does not introduce a new hash algorithm or work-factor policy.

## Related Areas

[Password implementation](../../backend/app/services/passwords.py),
[contract tests](../../backend/tests/test_password_hashes.py),
[authentication operations](../AUTHENTICATION.md),
[auth flow](../architecture/AUTH-FLOW.md), [ADR index](ADR-000-INDEX.md).
