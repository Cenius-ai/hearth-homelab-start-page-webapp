"""Human-friendly formatting shared by templates and JSON payloads."""

from __future__ import annotations

from datetime import datetime, timezone

UTC = timezone.utc

STATUS_LABELS = {"up": "Up", "down": "Down"}


def utcnow() -> datetime:
    return datetime.now(tz=UTC)


def iso(dt: datetime) -> str:
    return dt.astimezone(UTC).replace(microsecond=0).isoformat()


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def relative_time(value: str | None, *, now: datetime | None = None) -> str:
    """`just now`, `4 minutes ago`, `yesterday`, then an absolute date."""
    moment = parse_iso(value)
    if moment is None:
        return "an unknown time"
    now = now or utcnow()
    seconds = int((now - moment).total_seconds())
    if seconds < 0:
        return "just now"
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return "1 minute ago" if minutes == 1 else f"{minutes} minutes ago"
    hours = minutes // 60
    if hours < 24:
        return "1 hour ago" if hours == 1 else f"{hours} hours ago"
    days = hours // 24
    if days == 1:
        return "yesterday"
    if days < 14:
        return f"{days} days ago"
    return moment.strftime("%d %b %Y")


def status_label(health: dict | None) -> str:
    if not health:
        return "Never checked"
    status = health.get("status")
    return STATUS_LABELS.get(status, "Unknown")


def status_detail(health: dict | None, *, now: datetime | None = None) -> str:
    """The tooltip/aria text: status plus how long ago it was checked."""
    if not health:
        return "Never checked"
    label = STATUS_LABELS.get(health.get("status"), "Unknown")
    return f"{label} — checked {relative_time(health.get('checked_at'), now=now)}"


def status_tone(health: dict | None) -> str:
    if not health:
        return "unknown"
    return health.get("status") or "unknown"
