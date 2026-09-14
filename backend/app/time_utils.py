"""Timezone-aware UTC helpers shared by models and services."""

from datetime import UTC, datetime


def utcnow() -> datetime:
    """Return an aware UTC timestamp."""

    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    """Normalize driver-returned timestamps; SQLite drops timezone metadata."""

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
