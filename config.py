"""Environment config for Imperium Sales Bot."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")


def _color(raw: str | None, default: int = 0xD4AF37) -> int:
    if not raw:
        return default
    text = raw.strip().removeprefix("#")
    try:
        return int(text, 16)
    except ValueError:
        return default


def _optional_int(raw: str | None) -> int | None:
    if not raw or not raw.strip():
        return None
    try:
        return int(raw.strip())
    except ValueError as exc:
        raise ValueError(f"Invalid integer env value: {raw!r}") from exc


@dataclass(frozen=True)
class Config:
    token: str
    guild_id: int | None
    timezone: str
    brand_name: str
    brand_color: int
    leaderboard_channel_id: int | None
    db_path: Path
    duplicate_seconds: int


# Default board channel for this test server (override with LEADERBOARD_CHANNEL_ID)
DEFAULT_LEADERBOARD_CHANNEL_ID = 1554506265726820402
DEFAULT_GUILD_ID = 1552050961696948224


def load_config() -> Config:
    token = (os.getenv("DISCORD_TOKEN") or "").strip()
    if not token or token == "your_bot_token_here":
        raise RuntimeError("Set DISCORD_TOKEN in .env or Railway variables.")

    tz = (os.getenv("TIMEZONE") or "America/Los_Angeles").strip()
    if tz.upper() in {"PST", "PDT", "PACIFIC"}:
        tz = "America/Los_Angeles"

    db_raw = (os.getenv("DATABASE_PATH") or "data/sales.db").strip()
    db_path = Path(db_raw)
    if not db_path.is_absolute():
        db_path = ROOT / db_path

    dup = int(os.getenv("DUPLICATE_WINDOW_SECONDS") or "30")

    guild_id = _optional_int(os.getenv("GUILD_ID")) or DEFAULT_GUILD_ID
    board_id = (
        _optional_int(os.getenv("LEADERBOARD_CHANNEL_ID"))
        or DEFAULT_LEADERBOARD_CHANNEL_ID
    )

    return Config(
        token=token,
        guild_id=guild_id,
        timezone=tz,
        brand_name=(os.getenv("BRAND_NAME") or "Imperium").strip() or "Imperium",
        brand_color=_color(os.getenv("BRAND_COLOR")),
        leaderboard_channel_id=board_id,
        db_path=db_path,
        duplicate_seconds=max(0, dup),
    )
