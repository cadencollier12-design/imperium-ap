"""Time helpers — week starts Sunday 00:00 in the configured timezone."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


def zone(tz_name: str) -> ZoneInfo:
    return ZoneInfo(tz_name)


def now(tz_name: str) -> datetime:
    return datetime.now(timezone.utc).astimezone(zone(tz_name))


def as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def utc_iso(dt: datetime) -> str:
    return as_utc(dt).isoformat()


def week_start(tz_name: str, when: datetime | None = None) -> datetime:
    """Sunday 00:00:00 in local timezone (returned as aware local datetime)."""
    local = when.astimezone(zone(tz_name)) if when else now(tz_name)
    # Monday=0 ... Sunday=6 → days since Sunday
    days_since_sunday = (local.weekday() + 1) % 7
    start = (local - timedelta(days=days_since_sunday)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return start


def next_week_start(tz_name: str, when: datetime | None = None) -> datetime:
    return week_start(tz_name, when) + timedelta(days=7)


def day_start(tz_name: str, when: datetime | None = None) -> datetime:
    local = when.astimezone(zone(tz_name)) if when else now(tz_name)
    return local.replace(hour=0, minute=0, second=0, microsecond=0)


def month_start(tz_name: str, when: datetime | None = None) -> datetime:
    local = when.astimezone(zone(tz_name)) if when else now(tz_name)
    return local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def periods(tz_name: str) -> dict[str, datetime]:
    return {
        "day": day_start(tz_name),
        "week": week_start(tz_name),
        "month": month_start(tz_name),
        "next_reset": next_week_start(tz_name),
    }


def money(amount: float) -> str:
    if float(amount).is_integer():
        return f"${amount:,.0f}"
    return f"${amount:,.2f}"


def medal(rank: int) -> str:
    return {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"`#{rank}`")


def updated_stamp(tz_name: str, when_dt: datetime | None = None) -> str:
    """e.g. UPDATED 10/6/26 8:49am"""
    local = when_dt.astimezone(zone(tz_name)) if when_dt else now(tz_name)
    # %#I isn't portable on Linux; strip leading zero manually
    hour = local.strftime("%I").lstrip("0") or "0"
    minute = local.strftime("%M")
    ampm = local.strftime("%p").lower()
    return f"UPDATED {local.month}/{local.day}/{local.strftime('%y')} {hour}:{minute}{ampm}"


def when(iso: str, tz_name: str) -> str:
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return iso
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone(zone(tz_name))
    return local.strftime("%a %b %d · %I:%M %p")


def countdown(until: datetime, tz_name: str) -> str:
    local_now = now(tz_name)
    target = until.astimezone(zone(tz_name))
    delta = target - local_now
    if delta.total_seconds() <= 0:
        return "resetting now"
    days = delta.days
    hours = delta.seconds // 3600
    mins = (delta.seconds % 3600) // 60
    if days > 0:
        return f"{days}d {hours}h"
    if hours > 0:
        return f"{hours}h {mins}m"
    return f"{mins}m"
