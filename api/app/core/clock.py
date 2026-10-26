"""One place for "now" in server-side expiry logic, so tests can move the clock."""

from datetime import UTC, date, datetime


def utcnow() -> datetime:
    return datetime.now(UTC)


def quota_day(at: datetime | None = None) -> date:
    """The day every daily counter (model calls, runs) belongs to: the UTC calendar day. The ONE
    place that says where a day starts; a counter row per (day, scope) means no reset job exists."""
    return (at or utcnow()).astimezone(UTC).date()
