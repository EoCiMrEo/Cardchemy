"""Authenticated encryption for short-lived PDF job payloads."""

import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import get_settings


class SourceStorageError(RuntimeError):
    """Raised when a queued source payload cannot be decrypted safely."""


class SourceStorage:
    """Encrypt PDF bytes before they enter the database.

    A dedicated AES-256 key keeps auth-key rotation independent from queued
    work. Operators must drain or cancel retained jobs before rotating this
    storage key.
    """

    _AAD_PREFIX = b"flashcard-generation-source:v1:"

    @classmethod
    def encrypt(cls, plaintext: bytes, fingerprint: str) -> tuple[bytes, bytes]:
        nonce = os.urandom(12)
        aad = cls._AAD_PREFIX + fingerprint.encode("ascii")
        key = get_settings().generation_source_encryption_key_bytes
        return nonce, AESGCM(key).encrypt(nonce, plaintext, aad)

    @classmethod
    def decrypt(cls, nonce: bytes, payload: bytes, fingerprint: str) -> bytes:
        try:
            aad = cls._AAD_PREFIX + fingerprint.encode("ascii")
            key = get_settings().generation_source_encryption_key_bytes
            return AESGCM(key).decrypt(nonce, payload, aad)
        except Exception as exc:
            raise SourceStorageError("The retained source file could not be decrypted") from exc
