"""Smoke-test a built runtime image without mounts, credentials, or networking.

Run with the host Python: python scripts/check_images.py backend --image REF.
The image must already exist locally; Docker is never allowed to pull it.
"""
from __future__ import annotations

import argparse
import base64
import re
import secrets
import subprocess
from uuid import uuid4

from test_services import system_environment


BACKEND_PROBE = r'''
import importlib.util
import os
from io import BytesIO
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from datetime import timedelta
from uuid import uuid4

assert os.getuid() == 10001, "Backend runtime must run as UID 10001"
assert not Path("/.env").exists() and not Path("/app/.env").exists()
assert "Apache License" in Path("/app/legal/LICENSE").read_text()
assert "Copyright 2026 EoCiMrEo" in Path("/app/legal/NOTICE").read_text()
assert "does not cover" in Path("/app/legal/BRANDING.md").read_text()
for name in ("pip", "setuptools", "wheel"):
    assert importlib.util.find_spec(name) is None, "Unexpected runtime build package: " + name
for name in ("gcc", "cc", "g++", "clang"):
    assert shutil.which(name) is None, "Unexpected runtime compiler: " + name

# These imports load the native extensions used by the actual musl runtime.
import asyncpg
import bcrypt
import cryptography.hazmat.bindings._rust
import pydantic_core
import jwt
from fastapi import HTTPException
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, NumberObject
from app.main import app
from app.services.auth import AuthService
from app.services.pdf_processor import PDFProcessor
from app.services.source_storage import SourceStorage, SourceStorageError
from app.time_utils import utcnow
from app.workers.email import EmailWorker
from app.workers.generation import GenerationWorker

assert "/auth/login" in app.openapi()["paths"]
assert app.openapi()["info"]["title"] == "Cardchemy"
assert "/health/live" in app.openapi()["paths"]
assert GenerationWorker().settings.ai_provider_enabled is False
assert EmailWorker().settings.smtp_host == "127.0.0.1"

password = "Generated runtime compatibility password"
hashed = AuthService.hash_password(password)
assert AuthService.verify_password(password, hashed)
assert not AuthService.verify_password(password + "!", hashed)
user_id, session_id = uuid4(), uuid4()
token = AuthService._encode_token(token_type="access", subject=user_id,
    session_id=session_id, expires_at=utcnow() + timedelta(minutes=1))
assert jwt.get_unverified_header(token)["alg"] == "HS256"
claims = AuthService.verify_access_token(token)
assert claims.sub == user_id and claims.session_id == session_id
try:
    AuthService.verify_refresh_token(token)
except HTTPException as error:
    assert error.status_code == 401
else:
    raise AssertionError("Access token incorrectly accepted as refresh token")

source, fingerprint = b"runtime source encryption probe", "a" * 64
nonce, encrypted = SourceStorage.encrypt(source, fingerprint)
assert encrypted != source
assert SourceStorage.decrypt(nonce, encrypted, fingerprint) == source
try:
    SourceStorage.decrypt(nonce, encrypted, "b" * 64)
except SourceStorageError:
    pass
else:
    raise AssertionError("Source encryption failed to authenticate its fingerprint")

def text_pdf():
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"):
        DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 26 Tf 72 650 Td (Alpine OCR runtime works) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()

pdf = text_pdf()
document = PDFProcessor.extract_text_from_bytes(pdf, max_pages=1, max_extracted_chars=1000)
assert document.text == "Alpine OCR runtime works"

if os.environ["RUNTIME_PROBE_OCR"] == "true":
    assert shutil.which("pdftoppm") and shutil.which("tesseract")
    languages = subprocess.run(["tesseract", "--list-langs"], check=True,
        capture_output=True, text=True, timeout=10).stdout.splitlines()
    assert "eng" in languages, "English OCR language data is missing"
    with tempfile.TemporaryDirectory(prefix="runtime-ocr-") as directory:
        source_path = Path(directory) / "text.pdf"
        prefix = Path(directory) / "page"
        source_path.write_bytes(pdf)
        render = subprocess.run(["pdftoppm", "-singlefile", "-r", "100", str(source_path),
            str(prefix)], check=True, capture_output=True, timeout=30)
        pixels = prefix.with_suffix(".ppm").read_bytes()
        header = re.match(rb"P6\s+(\d+)\s+(\d+)\s+255\s", pixels)
        assert header, "Unexpected Poppler raster format"
        width, height = map(int, header.groups())
        image_bytes = pixels[header.end():]
        assert len(image_bytes) == width * height * 3
        assert any(channel < 240 for channel in image_bytes), (
            "Poppler produced a blank raster; inspect OCR image fonts: " +
            render.stderr.decode("utf-8", errors="replace"))
        writer = PdfWriter()
        page = writer.add_blank_page(width=612, height=792)
        image = DecodedStreamObject()
        image.set_data(image_bytes)
        image.update({NameObject("/Type"): NameObject("/XObject"),
            NameObject("/Subtype"): NameObject("/Image"),
            NameObject("/Width"): NumberObject(width),
            NameObject("/Height"): NumberObject(height),
            NameObject("/ColorSpace"): NameObject("/DeviceRGB"),
            NameObject("/BitsPerComponent"): NumberObject(8)})
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/XObject"):
            DictionaryObject({NameObject("/Im1"): writer._add_object(image.flate_encode())})})
        stream = DecodedStreamObject()
        stream.set_data(b"q 612 0 0 792 0 0 cm /Im1 Do Q")
        page[NameObject("/Contents")] = writer._add_object(stream)
        output = BytesIO()
        writer.write(output)
        scanned = output.getvalue()
        result = PDFProcessor.extract_text_from_bytes(scanned, max_pages=1,
            max_extracted_chars=1000, ocr_enabled=True, ocr_dpi=200,
            ocr_page_timeout_seconds=30)
        assert "alpine ocr runtime works" in result.text.lower(), "OCR did not recover the generated English text"
else:
    assert shutil.which("pdftoppm") is None and shutil.which("tesseract") is None

print("Backend runtime smoke passed: native dependencies, API/workers, bcrypt, HS256/purpose, AES-GCM, PDF" +
    (", image-only PDF OCR/eng data" if os.environ["RUNTIME_PROBE_OCR"] == "true" else ", OCR absent"))
'''


FRONTEND_PROBE = r'''
set -eu
test "$(id -u)" = 101
for tool in gcc cc pip; do
    if command -v "$tool" >/dev/null 2>&1; then
        echo "Unexpected runtime build tool: $tool" >&2
        exit 1
    fi
done
nginx -t
nginx >/tmp/probe-edge-log 2>&1
trap 'nginx -s quit >/dev/null 2>&1 || true' EXIT
attempt=0
until wget -q -O /tmp/probe-health http://127.0.0.1:8080/healthz; do
    attempt=$((attempt + 1))
    test "$attempt" -lt 20
    sleep 0.1
done
test "$(cat /tmp/probe-health)" = ok
wget -S -O /tmp/probe-index http://127.0.0.1:8080/index.html 2>/tmp/probe-headers
grep -q 'type="module"' /tmp/probe-index
grep -qi 'Content-Security-Policy:' /tmp/probe-headers
grep -qi 'X-Frame-Options: DENY' /tmp/probe-headers
grep -qi 'X-Content-Type-Options: nosniff' /tmp/probe-headers
grep -qi 'Referrer-Policy: strict-origin-when-cross-origin' /tmp/probe-headers
grep -qi 'Permissions-Policy:' /tmp/probe-headers
grep -q '<title>Cardchemy</title>' /tmp/probe-index
grep -q 'href="/favicon.ico"' /tmp/probe-index
wget -q -O /tmp/probe-license http://127.0.0.1:8080/legal/LICENSE
grep -q 'Apache License' /tmp/probe-license
wget -q -O /tmp/probe-brand-terms http://127.0.0.1:8080/legal/BRANDING.md
grep -q 'does not cover' /tmp/probe-brand-terms
wget -S -O /tmp/probe-wordmark http://127.0.0.1:8080/brand/cardchemy-wordmark.png 2>/tmp/probe-wordmark-headers
grep -qi 'Content-Type: image/png' /tmp/probe-wordmark-headers
test "$(od -An -tx1 -N8 /tmp/probe-wordmark | tr -d ' \n')" = 89504e470d0a1a0a
wget -S -O /tmp/probe-icon http://127.0.0.1:8080/favicon.ico 2>/tmp/probe-icon-headers
grep -qi 'Content-Type: image/x-icon' /tmp/probe-icon-headers
test "$(od -An -tx1 -N4 /tmp/probe-icon | tr -d ' \n')" = 00000100
if wget -S -O /tmp/probe-missing-brand http://127.0.0.1:8080/brand/missing.png 2>/tmp/probe-missing-brand-headers; then
    echo 'Missing brand unexpectedly returned success' >&2
    exit 1
fi
grep -q '404 Not Found' /tmp/probe-missing-brand-headers
asset=$(sed -n 's/.*src="\(\/assets\/[^" ]*\.js\)".*/\1/p' /tmp/probe-index | head -n 1)
test -n "$asset"
wget -S -O /tmp/probe-asset "http://127.0.0.1:8080$asset" 2>/tmp/probe-asset-headers
test -s /tmp/probe-asset
grep -qi 'Cache-Control: public, max-age=31536000, immutable' /tmp/probe-asset-headers
grep -qi 'Content-Security-Policy:' /tmp/probe-asset-headers
wget -q -O /tmp/probe-private-query 'http://127.0.0.1:8080/index.html?token=phase10-private-query-sentinel'
if wget -q --post-data='phase10-private-body-sentinel' -O /tmp/probe-private-error 'http://127.0.0.1:8080/index.html?token=phase10-private-query-sentinel'; then
    echo 'Static POST unexpectedly succeeded' >&2
    exit 1
fi
grep -q '"event":"edge_request","status":200' /tmp/probe-edge-log
grep -q '"event":"edge_request","status":405' /tmp/probe-edge-log
if grep -q 'phase10-private-' /tmp/probe-edge-log; then
    echo 'Private request target leaked into edge logs' >&2
    exit 1
fi
echo 'Frontend runtime smoke passed: UID 101, nginx config, health/index/asset, PNG/ICO and missing-brand 404, security/cache headers, private target redaction'
'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("variant", choices=("backend", "backend-ocr", "frontend"))
    parser.add_argument("--image", help="Already-built local image reference; defaults to cardchemy-VARIANT:ci")
    arguments = parser.parse_args()
    image = arguments.image or f"cardchemy-{arguments.variant}:ci"
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9./_:@-]*", image):
        parser.error("Invalid local image reference")
    name = f"cardchemy-image-smoke-{uuid4().hex}"
    environment = system_environment()
    command = ["docker", "run", "--rm", "--pull", "never", "--network", "none",
               "--name", name, "-i"]
    if arguments.variant == "frontend":
        command += ["--entrypoint", "sh", image, "-s"]
        probe = FRONTEND_PROBE
    else:
        settings = {
            "ENVIRONMENT": "test",
            "DATABASE_URL": "postgresql+asyncpg://probe:probe@127.0.0.1:5432/runtime_probe_test",
            "SECRET_KEY": secrets.token_urlsafe(48),
            "GENERATION_SOURCE_ENCRYPTION_KEY": base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii"),
            "AI_PROVIDER_ENABLED": "false",
            "SMTP_HOST": "127.0.0.1",
            "SMTP_PORT": "1025",
            "SMTP_FROM_EMAIL": "runtime-probe@example.com",
            "RUNTIME_PROBE_OCR": str(arguments.variant == "backend-ocr").lower(),
        }
        for key, value in settings.items():
            command += ["-e", f"{key}={value}"]
        command += ["--entrypoint", "python", image, "-"]
        probe = BACKEND_PROBE
    # Preserve LF bytes for the Linux shell even when the host is Windows.
    try:
        result = subprocess.run(command, input=probe.encode("utf-8"), capture_output=True,
                                env=environment, timeout=120)
    finally:
        # Docker normally removes the container itself. Remove only our exact,
        # generated name as well if the client times out or is interrupted.
        subprocess.run(["docker", "rm", "-f", name], capture_output=True,
                       env=environment, timeout=20)
    if result.stdout:
        print(result.stdout.decode("utf-8", errors="replace").rstrip())
    if result.returncode:
        # Output contains only generated probes; command arguments are not printed.
        if result.stderr:
            print(result.stderr.decode("utf-8", errors="replace").rstrip())
        raise RuntimeError(f"{arguments.variant} runtime smoke failed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        raise SystemExit(str(error) if isinstance(error, RuntimeError) else "Runtime smoke could not complete")
