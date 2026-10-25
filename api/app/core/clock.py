"""One place for "now" in server-side expiry logic, so tests can move the clock."""

from datetime import UTC, datetime


def utcnow() -> datetime:
    return datetime.now(UTC)
