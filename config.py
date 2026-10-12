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


def _id_set(raw: str | None) -> frozenset[int]:
    """Comma/space-separated Discord user IDs."""
    if not raw or not raw.strip():
        return frozenset()
    out: set[int] = set()
    for part in raw.replace(";", ",").replace(" ", ",").split(","):
        part = part.strip()
        if not part:
            continue
        out.add(int(part))
    return frozenset(out)


@dataclass(frozen=True)
class Config:
    token: str
    guild_id: int | None
    timezone: str
    brand_name: str
    brand_color: int
    leaderboard_channel_id: int | None
    private_records_channel_id: int | None
    record_wall_channel_id: int | None
    records_admin_ids: frozenset[int]
    db_path: Path
    duplicate_seconds: int


# Default channels for this server
DEFAULT_LEADERBOARD_CHANNEL_ID = 1554506265726820402
DEFAULT_PRIVATE_RECORDS_CHANNEL_ID = 1558994164639866980
DEFAULT_RECORD_WALL_CHANNEL_ID = 1559017373808201829
DEFAULT_GUILD_ID = 1552050961696948224
DEFAULT_RECORDS_ADMIN_USER_ID = 1456116798175969301


def load_config() -> Config:
    token = (os.getenv("DISCORD_TOKEN") or "").strip()
    if not token or token == "your_bot_token_here":
        raise RuntimeError("Set DISCORD_TOKEN in .env or Railway variables.")

    tz = (os.getenv("TIMEZONE") or "America/Los_Angeles").strip()
    if tz.upper() in {"PST", "PDT", "PACIFIC"}:
        tz = "America/Los_Angeles"

    on_railway = bool(
        os.getenv("RAILWAY_ENVIRONMENT")
        or os.getenv("RAILWAY_PROJECT_ID")
        or os.getenv("RAILWAY_SERVICE_ID")
    )
    db_raw = (os.getenv("DATABASE_PATH") or "").strip()
    if on_railway:
        # Never store the DB on the ephemeral container filesystem.
        # Without a Volume at /data, every redeploy looks like a "wipe".
        if not db_raw or not db_raw.startswith("/data"):
            db_raw = "/data/sales.db"
        db_path = Path(db_raw)
    else:
        db_raw = db_raw or "data/sales.db"
        db_path = Path(db_raw)
        if not db_path.is_absolute():
            db_path = ROOT / db_path

    dup = int(os.getenv("DUPLICATE_WINDOW_SECONDS") or "30")

    guild_id = _optional_int(os.getenv("GUILD_ID")) or DEFAULT_GUILD_ID
    board_id = (
        _optional_int(os.getenv("LEADERBOARD_CHANNEL_ID"))
        or DEFAULT_LEADERBOARD_CHANNEL_ID
    )
    records_id = (
        _optional_int(os.getenv("PRIVATE_RECORDS_CHANNEL_ID"))
        or DEFAULT_PRIVATE_RECORDS_CHANNEL_ID
    )
    wall_id = (
        _optional_int(os.getenv("RECORD_WALL_CHANNEL_ID"))
        or DEFAULT_RECORD_WALL_CHANNEL_ID
    )

    return Config(
        token=token,
        guild_id=guild_id,
        timezone=tz,
        brand_name=(os.getenv("BRAND_NAME") or "Imperium").strip() or "Imperium",
        brand_color=_color(os.getenv("BRAND_COLOR")),
        leaderboard_channel_id=board_id,
        private_records_channel_id=records_id,
        record_wall_channel_id=wall_id,
        records_admin_ids=_id_set(
            os.getenv("RECORDS_ADMIN_USER_IDS") or str(DEFAULT_RECORDS_ADMIN_USER_ID)
        ),
        db_path=db_path,
        duplicate_seconds=max(0, dup),
    )
