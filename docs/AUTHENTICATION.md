# Authentication operations

## Secrets

Set `SECRET_KEY` to at least 32 high-entropy characters. Generate it into a
temporary shell variable so it is not printed to the terminal or copied into
shell history:

```powershell
$generatedSigningKey = python -c "import secrets; print(secrets.token_urlsafe(48))"
# Pass $generatedSigningKey directly to your deployment secret manager here.
Remove-Variable generatedSigningKey
```

Do not use `Write-Output` for the variable or paste generated secrets into
issues, logs, shell history, or Git. To
rotate the signing key, schedule a maintenance window, replace it in the secret
store, restart every API instance, and require all users to sign in again.
Production startup rejects known sample secrets, debug mode, insecure refresh
cookies, localhost CORS origins, and a non-HTTPS frontend base URL. The
separate email worker validates its SMTP delivery configuration without making
SMTP credentials available to the migration or API processes.

## Instructor bootstrap

After the database is initialized, create the first instructor from the backend
directory. The command prompts for the password without placing it in argv:

```powershell
python -m app.cli create-instructor --email instructor@example.com
```

The command refuses to create another instructor unless the operator makes the
explicit choice to pass `--allow-additional`. There is no public instructor
registration code or endpoint.

## Browser sessions

Access JWTs last 15 minutes and live only in browser memory. Refresh JWTs are
rotated, stored only in an HttpOnly SameSite cookie, and linked to a server-side
session with a 30-day absolute lifetime. Reusing an older refresh token revokes
that session. Logout and password reset also revoke server-side sessions.

## Password recovery

Password recovery queues a single-use, 30-minute link in the transactional
email outbox. Responses do not reveal whether an email is registered. A
successful password change consumes the token, revokes every existing session,
and queues a security notification that contains no reset token or other
secret. Account email verification is not a supported workflow.

See [Transactional email delivery](EMAIL_DELIVERY.md) for local Mailpit usage,
production SMTP security modes, retry and retention behavior, and sender-domain
responsibilities.

Authorized operators use [privacy controls](PRIVACY.md) for exclusive private
account exports and explicit deletion after stopping/draining writers. Expired
auth metadata cleanup is bounded and preserves linked email history.
