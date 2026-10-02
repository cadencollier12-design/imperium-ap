"""Small helpers."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def now(tz: str) -> datetime:
    return datetime.now(ZoneInfo(tz))


def periods(tz: str) -> dict[str, datetime]:
    cur = now(tz)
    day = cur.replace(hour=0, minute=0, second=0, microsecond=0)
    week = day - timedelta(days=day.weekday())
    month = day.replace(day=1)
    return {"day": day, "week": week, "month": month}


def money(n: float) -> str:
    return f"${n:,.0f}" if n == int(n) else f"${n:,.2f}"


def when(iso: str, tz: str) -> str:
    dt = datetime.fromisoformat(iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(tz))
    return dt.astimezone(ZoneInfo(tz)).strftime("%b %d, %Y · %I:%M %p")


def medal(rank: int) -> str:
    return {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"**{rank}.**")
