"""Verify real encrypted SMTP and recovery on isolated local capture services.

Use backend development Python. No operator .env, relay, mailbox or provider is
used. TLS keys, SMTP/DB credentials and all captured mail are disposable.
"""
from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import ipaddress
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
from uuid import uuid4

from test_services import (
    ROOT, cleanup_containers, docker, port, run_service_tests, system_environment,
    wait_postgres_ready, wait_ready,
)


def certificates(directory: Path) -> None:
    """Create short-lived private trust material; never install host trust."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

    now = datetime.now(timezone.utc)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Disposable SMTP QA CA")])
    ca = (
        x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name)
        .public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
        .sign(ca_key, hashes.SHA256())
    )
    server_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    server = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Disposable SMTP QA")]))
        .issuer_name(ca.subject).public_key(server_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.KeyUsage(True, False, True, False, False, False, False, False, False), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(server_key.public_key()), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
        .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), critical=False)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .sign(ca_key, hashes.SHA256())
    )
    unrelated_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    unrelated_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Untrusted SMTP QA CA")])
    unrelated_ca = (
        x509.CertificateBuilder().subject_name(unrelated_name).issuer_name(unrelated_name)
        .public_key(unrelated_key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(unrelated_key.public_key()), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(unrelated_key.public_key()), critical=False)
        .sign(unrelated_key, hashes.SHA256())
    )
    contents = {
        "ca.pem": ca.public_bytes(serialization.Encoding.PEM),
        "untrusted-ca.pem": unrelated_ca.public_bytes(serialization.Encoding.PEM),
        "server.pem": server.public_bytes(serialization.Encoding.PEM),
        "server-key.pem": server_key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
    }
    for filename, content in contents.items():
        path = directory / filename
        path.write_bytes(content)
        path.chmod(0o600)


def main() -> int:
    suffix = uuid4().hex[:12]
    names: list[str] = []
    with tempfile.TemporaryDirectory(prefix="cardchemy-smtp-tls-") as temporary:
        directory = Path(temporary)
        tls_directory = directory / "tls"
        tls_directory.mkdir(mode=0o700)
        certificates(tls_directory)
        database_password = secrets.token_urlsafe(36)
        smtp_password = secrets.token_urlsafe(36)
        database_env = directory / "database.env"
        database_env.write_text(
            f"POSTGRES_USER=qa\nPOSTGRES_DB=smtp_tls_test\nPOSTGRES_PASSWORD={database_password}\n",
            encoding="utf-8",
        )
        authentication = tls_directory / "smtp-auth.txt"
        authentication.write_text(f"qa:{smtp_password}\n", encoding="utf-8")
        database_env.chmod(0o600)
        authentication.chmod(0o600)
        try:
            database = f"cardchemy-smtp-tls-db-{suffix}"
            names.append(database)
            docker("run", "--rm", "-d", "--name", database,
                   "--env-file", str(database_env), "-p", "127.0.0.1::5432", "postgres:16")
            tcp_port = port(database, 5432)
            wait_postgres_ready(tcp_port, database_password, "smtp_tls_test")
            database_url = f"postgresql+asyncpg://qa:{database_password}@127.0.0.1:{tcp_port}/smtp_tls_test"
            environment = system_environment() | {
                "ENVIRONMENT": "test", "DATABASE_URL": database_url,
                "POSTGRES_TEST_DATABASE_URL": database_url,
                "SECRET_KEY": secrets.token_urlsafe(48),
                "GENERATION_SOURCE_ENCRYPTION_KEY": base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("="),
                "SMTP_TLS_TEST_PASSWORD": smtp_password,
                "SMTP_TLS_TEST_UNTRUSTED_CA": str(tls_directory / "untrusted-ca.pem"),
                "SSL_CERT_FILE": str(tls_directory / "ca.pem"), "PYTHONUTF8": "1",
            }
            for command in (
                [sys.executable, "-m", "alembic", "upgrade", "head"],
                [sys.executable, "-m", "alembic", "current", "--check-heads"],
                [sys.executable, "-m", "alembic", "check"],
            ):
                subprocess.run(command, cwd=ROOT / "backend", env=environment, check=True)
            for mode in ("starttls", "implicit"):
                service = f"cardchemy-smtp-tls-{mode}-{suffix}"
                names.append(service)
                required_mode = "MP_SMTP_REQUIRE_STARTTLS=true" if mode == "starttls" else "MP_SMTP_REQUIRE_TLS=true"
                docker("run", "--rm", "-d", "--name", service,
                       "-p", "127.0.0.1::8025", "-p", "127.0.0.1::1025",
                       "--mount", f"type=bind,source={tls_directory},target=/tls,readonly",
                       "-e", "MP_SMTP_TLS_CERT=/tls/server.pem",
                       "-e", "MP_SMTP_TLS_KEY=/tls/server-key.pem",
                       "-e", "MP_SMTP_AUTH_FILE=/tls/smtp-auth.txt", "-e", required_mode,
                       "-e", "MP_ENABLE_CHAOS=true", "-e", "MP_DISABLE_VERSION_CHECK=true",
                       "axllent/mailpit:v1.31.1")
                wait_ready(service, ["/mailpit", "readyz"])
                environment[f"SMTP_TLS_TEST_{mode.upper()}_PORT"] = str(port(service, 1025))
                environment[f"SMTP_TLS_TEST_{mode.upper()}_API"] = f"http://127.0.0.1:{port(service, 8025)}"
            return run_service_tests(
                [sys.executable, "-m", "pytest", "-q", "--tb=short", "-m", "smtp_tls", "tests/integration/test_smtp_tls.py"],
                cwd=ROOT / "backend", environment=environment,
            )
        finally:
            cleanup_containers(names)
            print("Disposable TLS SMTP/DB services, keys, credentials and captured synthetic mail cleaned up.")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.CalledProcessError):
        raise SystemExit("Local TLS SMTP verification failed; no credential values were printed.")
