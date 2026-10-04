"""Authenticated, short-lived storage for fully validated candidate cards."""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from uuid import UUID

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.ai.contracts import ValidatedCard
from app.config import Settings


VALIDATION_POLICY_VERSION = "grounded_candidate_choice_v2"
MAX_ENCRYPTED_BYTES = 16 * 1024 * 1024


class CandidateStorageError(RuntimeError):
    """A staged payload is unavailable or cannot be authenticated safely."""


@dataclass(frozen=True)
class DecryptedCandidates:
    cards: list[ValidatedCard]
    duplicate_similarity_threshold: float


def _valid_threshold(value: object) -> bool:
    return (
        type(value) in (int, float)
        and math.isfinite(value)
        and 0.5 <= value <= 1.0
    )


def _aad(job_id: UUID, fingerprint: str, manual_retry_number: int, attempt_number: int) -> bytes:
    return (
        f"generation-validated-candidates:v1:{job_id}:{fingerprint}:"
        f"{manual_retry_number}:{attempt_number}:{VALIDATION_POLICY_VERSION}"
    ).encode("ascii")


def encrypt_candidates(
    settings: Settings,
    *,
    job_id: UUID,
    fingerprint: str,
    manual_retry_number: int,
    attempt_number: int,
    cards: tuple[ValidatedCard, ...],
    duplicate_similarity_threshold: float,
) -> tuple[bytes, bytes]:
    if not cards or len(cards) > 500:
        raise CandidateStorageError("Validated candidate count is out of bounds")
    if not _valid_threshold(duplicate_similarity_threshold):
        raise CandidateStorageError("Validated candidate policy is unavailable")
    plaintext = json.dumps(
        {
            "duplicate_similarity_threshold": duplicate_similarity_threshold,
            "cards": [card.model_dump(mode="json") for card in cards],
        },
        ensure_ascii=False, separators=(",", ":"),
    ).encode("utf-8")
    if len(plaintext) + 16 > min(settings.generation_candidate_choice_max_bytes_per_job, MAX_ENCRYPTED_BYTES):
        raise CandidateStorageError("Validated candidates exceed the temporary storage limit")
    nonce = os.urandom(12)
    payload = AESGCM(settings.generation_source_encryption_key_bytes).encrypt(
        nonce, plaintext,
        _aad(job_id, fingerprint, manual_retry_number, attempt_number),
    )
    return nonce, payload


def decrypt_candidates(
    settings: Settings,
    *,
    job_id: UUID,
    fingerprint: str,
    manual_retry_number: int,
    attempt_number: int,
    nonce: bytes,
    payload: bytes,
    expected_count: int,
) -> DecryptedCandidates:
    if len(nonce) != 12 or not 1 <= expected_count <= 500 or not 17 <= len(payload) <= MAX_ENCRYPTED_BYTES:
        raise CandidateStorageError("Validated candidates are unavailable")
    try:
        plaintext = AESGCM(settings.generation_source_encryption_key_bytes).decrypt(
            nonce, payload,
            _aad(job_id, fingerprint, manual_retry_number, attempt_number),
        )
        raw = json.loads(plaintext)
        if not isinstance(raw, dict) or set(raw) != {"duplicate_similarity_threshold", "cards"}:
            raise ValueError("staged candidate policy differs from authenticated payload")
        threshold = raw["duplicate_similarity_threshold"]
        cards = raw["cards"]
        if not _valid_threshold(threshold) or not isinstance(cards, list) or len(cards) != expected_count:
            raise ValueError("staged candidate count differs from authenticated payload")
        return DecryptedCandidates(
            cards=[ValidatedCard.model_validate(item) for item in cards],
            duplicate_similarity_threshold=float(threshold),
        )
    except Exception as exc:
        raise CandidateStorageError("Validated candidates are unavailable") from exc
