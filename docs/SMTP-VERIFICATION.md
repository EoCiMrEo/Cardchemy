# Self-hosted encrypted SMTP verification

Self-hosted deployments can use an operator-owned local or LAN SMTP relay;
an online SMTP provider is not required. Production still requires STARTTLS
or implicit TLS, certificate validation and an HTTPS frontend origin. Local
does not mean that credentials or reset/invitation links can travel in plain
text. Configure the operator relay using [email delivery](EMAIL_DELIVERY.md).
Mailpit remains a disposable test capture service, not a production relay.

Run the maintained local transport and recovery gate from the repository root,
using the backend development Python and a running Docker engine:

```powershell
backend\venv\Scripts\python.exe scripts/test_smtp_tls.py
```

On Linux with the backend development environment activated:

```sh
python scripts/test_smtp_tls.py
```

The harness creates a uniquely named PostgreSQL database and two pinned
Mailpit containers bound to random host loopback ports. One capture server
requires STARTTLS, and one requires implicit TLS. Both require generated
SMTP authentication. An ephemeral CA issues a one-day certificate for
`127.0.0.1`; only the test subprocess trusts it through `SSL_CERT_FILE`.
The harness does not install host certificates, change operator configuration,
read root `.env`, use an external relay, or send mail to an external mailbox.
Database credentials are not mounted into the SMTP containers.

The opt-in PostgreSQL integration tests exercise the actual application
`SmtpTransport`, `EmailWorker` and transactional outbox with validated
production settings. For each transport mode they verify:

1. Authenticated, certificate-validated encrypted delivery is captured once
   and committed as `sent`, with its lease cleared.
2. An untrusted CA and a wrong certificate hostname each produce a terminal
   `smtp_tls_failed` failure; neither sends mail or silently disables trust.
3. A real SMTP 451 rejection persists a bounded retry on the same event and
   stable `Message-ID`; restoring the capture server yields one delivery on
   the second attempt.
4. A real SMTP authentication rejection is terminal. Correcting credentials
   and using the operator retry command restores delivery on the same event.
5. SMTP accepts a message over TLS, then an interrupted worker's lease expires
   before its success transaction commits. Recovery records
   `smtp_delivery_ambiguous`, performs no automatic resend, and the operator
   retry command refuses to proceed without explicit ambiguity acknowledgement.

The fifth case controls the expired lease to rehearse a worker interruption;
it does not claim to reproduce every possible remote SMTP acknowledgement
loss. The existing [offline and Mailpit suites](TESTING.md) cover further
transport classifications and transactional request/password/invitation
contracts. Captured recipients and message content are synthetic and are
never written to repository evidence.

The harness checks the connected test database identity, current Alembic head
and schema drift before running tests. It removes its own temporary containers,
database, TLS keys, credential files and captured mail on success or failure.
These checks prove supported local encrypted transport and recovery. Each
deployment operator must still verify its own relay's certificates, routing,
mailbox delivery and retention policy. External sender DNS/provider controls
apply only when that relay sends mail outside the local installation.

Mailpit's documented [SMTP TLS/authentication modes](https://mailpit.axllent.org/docs/configuration/smtp/)
and [password-file format](https://mailpit.axllent.org/docs/configuration/passwords/)
define the disposable server configuration.
