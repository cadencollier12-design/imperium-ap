"""Environment config."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
logger = logging.getLogger(__name__)

_TZ = {
    "PST": "America/Los_Angeles",
    "PDT": "America/Los_Angeles",
    "PT": "America/Los_Angeles",
    "EST": "America/New_York",
    "EDT": "America/New_York",
    "ET": "America/New_York",
    "CST": "America/Chicago",
    "CDT": "America/Chicago",
    "CT": "America/Chicago",
    "MST": "America/Denver",
    "MDT": "America/Denver",
    "MT": "America/Denver",
    "UTC": "UTC",
}


def _s(name: str, default: str | None = None) -> str | None:
    v = os.getenv(name)
    return default if v is None or not v.strip() else v.strip()


def _i(name: str, default: int | None = None) -> int | None:
    v = _s(name)
    if v is None:
        return default
    return int(v)


def _tz(raw: str) -> str:
    mapped = _TZ.get(raw.upper())
    if mapped:
        return mapped
    try:
        ZoneInfo(raw)
    except ZoneInfoNotFoundError as e:
        raise ValueError(f"Bad TIMEZONE: {raw!r}") from e
    return raw


@dataclass(frozen=True)
class Config:
    token: str
    db_path: Path
    timezone: str
    guild_id: int | None
    leaderboard_channel_id: int | None
    brand_name: str
    brand_color: int
    duplicate_seconds: int


def load_config() -> Config:
    token = _s("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN missing")

    color = (_s("BRAND_COLOR", "D4AF37") or "D4AF37").lstrip("#")
    db = Path(_s("DATABASE_PATH", "data/sales.db") or "data/sales.db")
    if not db.is_absolute():
        db = ROOT / db
    db.parent.mkdir(parents=True, exist_ok=True)

    return Config(
        token=token,
        db_path=db,
        timezone=_tz(_s("TIMEZONE", "America/Los_Angeles") or "America/Los_Angeles"),
        guild_id=_i("GUILD_ID"),
        leaderboard_channel_id=_i("LEADERBOARD_CHANNEL_ID"),
        brand_name=_s("BRAND_NAME", "Imperium") or "Imperium",
        brand_color=int(color, 16),
        duplicate_seconds=_i("DUPLICATE_WINDOW_SECONDS", 30) or 30,
    )
