"""Passlib-compatible password records using the maintained bcrypt backend.

The wrapper format and prehash are defined by Passlib's bcrypt_sha256 spec:
https://passlib.readthedocs.io/en/stable/lib/passlib.hash.bcrypt_sha256.html
Only v2 records are created. V1 and raw bcrypt are verification-only formats.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import re

import bcrypt


_ALPHABET = "./ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
_COST = r"(?:[4-9]|[12][0-9]|3[01])"
_FIELDS = r"\$(?P<salt>[./A-Za-z0-9]{22})\$(?P<digest>[./A-Za-z0-9]{31})"
_V2 = re.compile(r"\$bcrypt-sha256\$v=2,t=(?P<type>2b),r=(?P<cost>" + _COST + r")" + _FIELDS)
_V1 = re.compile(r"\$bcrypt-sha256\$(?P<type>2[ab]),(?P<cost>" + _COST + r")" + _FIELDS)
_RAW = re.compile(
    r"\$(?P<type>2[aby]?)\$(?P<cost>0[4-9]|[12][0-9]|3[01])\$"
    r"(?P<salt>[./A-Za-z0-9]{22})(?P<digest>[./A-Za-z0-9]{31})"
)


def _prehash(password: bytes, salt: str, *, version: int) -> bytes:
    digest = (hmac.digest(salt.encode("ascii"), password, "sha256")
              if version == 2 else hashlib.sha256(password).digest())
    return base64.b64encode(digest)


def _normalize_padding(value: str, mask: int) -> str:
    # Passlib repaired unused bcrypt64 padding bits before verification. Preserve
    # that behavior for existing records without changing their stored values.
    return value[:-1] + _ALPHABET[_ALPHABET.index(value[-1]) & mask]


def hash_password(password: str) -> str:
    """Generate the existing bcrypt_sha256 v2 format with a random cost-12 salt."""
    encoded = password.encode("utf-8")
    config = bcrypt.gensalt(rounds=12, prefix=b"2b")
    salt = config[7:].decode("ascii")
    result = bcrypt.hashpw(_prehash(encoded, salt, version=2), config).decode("ascii")
    return f"$bcrypt-sha256$v=2,t=2b,r=12${salt}${result[29:]}"


def verify_password(password: str, record: str) -> bool:
    """Verify supported historic records; malformed inputs fail without logging."""
    if not isinstance(password, str) or not isinstance(record, str):
        return False
    try:
        encoded = password.encode("utf-8")
        match = _V2.fullmatch(record)
        version = 2
        if match is None:
            match = _V1.fullmatch(record)
            version = 1
        if match is None:
            match = _RAW.fullmatch(record)
            version = 0
        if match is None:
            return False
        variant, cost = match["type"], int(match["cost"])
        salt = _normalize_padding(match["salt"], 0x30)
        digest = _normalize_padding(match["digest"], 0x3C)
        if version:
            encoded = _prehash(encoded, salt, version=version)
        else:
            # Passlib rejects NUL in raw bcrypt. Bcrypt 5 accepts it; retain the
            # old verifier's behavior, including NUL beyond the truncated prefix.
            if b"\0" in encoded:
                return False
            if variant == "2":
                # Original $2$ repeats a nonempty password rather than adding
                # the terminator introduced by $2a$. Modern bcrypt emulates it.
                if encoded:
                    encoded = encoded * ((71 // len(encoded)) + 1)
                variant = "2b"
            encoded = encoded[:72]
        raw = f"${variant}${cost:02d}${salt}{digest}".encode("ascii")
        return bcrypt.checkpw(encoded, raw)
    except (TypeError, ValueError):
        return False
