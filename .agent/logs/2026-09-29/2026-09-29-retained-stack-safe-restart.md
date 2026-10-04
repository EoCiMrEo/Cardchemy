# Retained local stack restart after Docker stopped

Date: 2026-09-29 (America/Chicago). During independent Lane 6 holdout
preparation, read-only metadata access failed because the existing database,
API, workers and Mailpit containers were stopped with exit code 0. The
frontend container alone was healthy after its separately documented rebuild.
There was no evidence of a database crash or schema failure from this state.

I started the **existing** database container and waited for its healthcheck,
then started the existing API, generation/index/answer/email workers and
Mailpit with the documented development Compose override. Compose also ran
the already configured migration dependency; it exited successfully.
No `down`, volume removal, image rebuild for backend, root `.env` edit, or
data reset occurred. All eight long-running services reached healthy state.
The restarted backend reported `20260928_0029 (head)`, and `alembic check`
reported no new upgrade operations. Validated settings reported
`rag_ask_effective_enabled=False` and `rag_source_only_available=False`.
Thus the dormant v4 Ask path remains closed. The populated database volume,
encrypted originals and backup were preserved.

The prior authenticated in-app tab was no longer available. A new local tab
redirected to `/login`; no credentials or retained account state were read or
changed to regain access. Therefore the post-restart original-PDF browser
check remains limited to the frontend test and the independent exact-byte
disposable replay recorded separately.
