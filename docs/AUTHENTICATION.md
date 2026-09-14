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
cookies, localhost CORS origins, and missing SMTP delivery configuration.

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

## Password recovery and email verification

Password recovery sends a single-use, 30-minute link through configured SMTP.
Configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM_EMAIL`, and credentials when the
relay requires them. Responses do not reveal whether an email is registered.

Email verification is intentionally **not required** for the current self-hosted
deployment model. This decision is explicit in `EMAIL_VERIFICATION_REQUIRED=false`;
changing it requires implementing and testing a separate verification lifecycle.
