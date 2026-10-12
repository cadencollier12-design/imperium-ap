"""Public Record Wall — weekly (>$20k) and monthly (>$50k) personal AP."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import discord

from utils.embeds import record_wall_board
from utils.helpers import month_start, updated_stamp, week_start, zone

if TYPE_CHECKING:
    from bot import Bot

logger = logging.getLogger(__name__)

CH_KEY = "record_wall_channel_id"
MSG_KEY = "record_wall_message_id"
HINTS = ("RECORD WALL",)
WEEKLY_MIN = 20_000.0
MONTHLY_MIN = 50_000.0
_lock = asyncio.Lock()


@dataclass
class WallEntry:
    display_name: str
    ap: float
    period_label: str


@dataclass
class WallResult:
    message: discord.Message | None
    error: str | None = None
    weekly: list[WallEntry] | None = None
    monthly: list[WallEntry] | None = None


def _parse_iso(iso: str, tz_name: str) -> datetime:
    dt = datetime.fromisoformat(iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(zone(tz_name))


def _month_label(start: datetime) -> str:
    return start.strftime("%B %Y")


def _week_label(start: datetime) -> str:
    end = start + timedelta(days=6)
    if start.year == end.year:
        return f"{start.strftime('%b')} {start.day}–{end.day}, {start.year}"
    return f"{start.strftime('%b %d, %Y')} – {end.strftime('%b %d, %Y')}"


async def compute_wall(
    bot: Bot,
) -> tuple[list[WallEntry], list[WallEntry], str]:
    tz = bot.config.timezone
    rows = await bot.db.active_sale_rows()
    user_week: dict[int, dict[datetime, float]] = defaultdict(lambda: defaultdict(float))
    user_month: dict[int, dict[datetime, float]] = defaultdict(lambda: defaultdict(float))
    names: dict[int, str] = {}

    for user_id, display_name, amount, created in rows:
        local = _parse_iso(created, tz)
        ws = week_start(tz, local)
        ms = month_start(tz, local)
        user_week[user_id][ws] += amount
        user_month[user_id][ms] += amount
        names[user_id] = display_name

    weekly: list[WallEntry] = []
    for uid, weeks in user_week.items():
        for ws, ap in weeks.items():
            if ap > WEEKLY_MIN:
                weekly.append(
                    WallEntry(names.get(uid, str(uid)), ap, _week_label(ws))
                )
    weekly.sort(key=lambda e: (-e.ap, e.period_label, e.display_name))

    monthly: list[WallEntry] = []
    for uid, months in user_month.items():
        for ms, ap in months.items():
            if ap > MONTHLY_MIN:
                monthly.append(
                    WallEntry(names.get(uid, str(uid)), ap, _month_label(ms))
                )
    monthly.sort(key=lambda e: (-e.ap, e.period_label, e.display_name))

    return weekly, monthly, updated_stamp(tz)


async def _get_text_channel(bot: Bot, channel_id: int) -> discord.TextChannel | None:
    ch = bot.get_channel(channel_id)
    if ch is None:
        try:
            ch = await bot.fetch_channel(channel_id)
        except discord.HTTPException as exc:
            logger.warning("Cannot fetch record wall channel %s: %s", channel_id, exc)
            return None
    return ch if isinstance(ch, discord.TextChannel) else None


async def _pin(message: discord.Message) -> None:
    try:
        if not message.pinned:
            await message.pin(reason="Imperium Record Wall")
    except discord.HTTPException as exc:
        logger.warning("Could not pin record wall: %s", exc)


def _match(msg: discord.Message, bot_id: int) -> bool:
    if msg.author.id != bot_id or not msg.embeds:
        return False
    title = (msg.embeds[0].title or "").upper()
    return any(h in title for h in HINTS)


async def channel_for(bot: Bot) -> discord.TextChannel | None:
    channel_id = bot.config.record_wall_channel_id
    if channel_id is None:
        return None
    ch = await _get_text_channel(bot, channel_id)
    if ch is None:
        return None
    bot.cached_wall_channel_id = ch.id
    await bot.db.set_setting(CH_KEY, str(ch.id))
    return ch


async def refresh_record_wall(bot: Bot) -> WallResult:
    async with _lock:
        weekly, monthly, stamp = await compute_wall(bot)
        ch = await channel_for(bot)
        if ch is None:
            return WallResult(
                None,
                "Record wall channel not found. Set RECORD_WALL_CHANNEL_ID.",
                weekly,
                monthly,
            )

        embed = record_wall_board(
            bot.config.brand_name,
            bot.config.brand_color,
            weekly,
            monthly,
            stamp,
        )

        msg_id = getattr(bot, "cached_wall_message_id", None)
        if msg_id is None:
            raw = await bot.db.get_setting(MSG_KEY)
            if raw:
                try:
                    msg_id = int(raw)
                except ValueError:
                    msg_id = None

        if msg_id is not None:
            try:
                msg = await ch.fetch_message(msg_id)
                await msg.edit(embed=embed)
                await _pin(msg)
                bot.cached_wall_message_id = msg.id
                await bot.db.set_setting(MSG_KEY, str(msg.id))
                return WallResult(msg, None, weekly, monthly)
            except (discord.NotFound, discord.HTTPException) as exc:
                logger.warning("Saved record wall message unusable: %s", exc)
                bot.cached_wall_message_id = None
                await bot.db.delete_setting(MSG_KEY)

        if bot.user:
            try:
                async for old in ch.history(limit=40):
                    if _match(old, bot.user.id):
                        await old.edit(embed=embed)
                        await _pin(old)
                        bot.cached_wall_message_id = old.id
                        await bot.db.set_setting(MSG_KEY, str(old.id))
                        return WallResult(old, None, weekly, monthly)
            except discord.HTTPException as exc:
                logger.warning("Record wall history scan failed: %s", exc)

        try:
            msg = await ch.send(embed=embed)
            await _pin(msg)
            bot.cached_wall_message_id = msg.id
            await bot.db.set_setting(MSG_KEY, str(msg.id))
            return WallResult(msg, None, weekly, monthly)
        except discord.HTTPException as exc:
            logger.error("Post record wall failed: %s", exc)
            return WallResult(
                None,
                f"Could not post in {ch.mention}. Need Send Messages + Embed Links.",
                weekly,
                monthly,
            )
