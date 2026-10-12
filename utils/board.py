"""
Live weekly leaderboard message in a sticky channel.

Channel resolution order:
  1) in-memory cache
  2) SQLite settings
  3) LEADERBOARD_CHANNEL_ID env
  4) reclaim an existing weekly board post
  5) fuzzy channel-name match
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

import discord

from utils.embeds import board, week_reset_notice
from utils.helpers import next_week_start, week_start

if TYPE_CHECKING:
    from bot import Bot

logger = logging.getLogger(__name__)

CH_KEY = "leaderboard_channel_id"
MSG_KEY = "leaderboard_message_id"
WEEK_KEY = "current_week_start"
HINTS = ("WEEKLY LEADERBOARD", "LEADERBOARD")
TOP = 100  # show every agent's weekly sales
_lock = asyncio.Lock()


@dataclass
class BoardResult:
    message: discord.Message | None
    error: str | None = None


def _match(msg: discord.Message, bot_id: int) -> bool:
    if msg.author.id != bot_id or not msg.embeds:
        return False
    title = (msg.embeds[0].title or "").upper()
    return any(h in title for h in HINTS)


def _name_looks_like_leaderboard(name: str) -> bool:
    cleaned = re.sub(r"[^a-z0-9]+", "", name.lower())
    return "leaderboard" in cleaned or cleaned in {"lb", "apboard", "weeklyap"}


def week_label(tz: str) -> str:
    start = week_start(tz)
    end = next_week_start(tz)
    return f"{start.strftime('%b %d')} → {end.strftime('%b %d')}"


async def _get_text_channel(bot: Bot, channel_id: int) -> discord.TextChannel | None:
    ch = bot.get_channel(channel_id)
    if ch is None:
        try:
            ch = await bot.fetch_channel(channel_id)
        except discord.HTTPException as exc:
            logger.warning("Cannot fetch channel %s: %s", channel_id, exc)
            return None
    if isinstance(ch, discord.TextChannel):
        return ch
    return None


async def _remember_channel(bot: Bot, channel: discord.TextChannel) -> None:
    bot.cached_board_channel_id = channel.id
    await bot.db.set_setting(CH_KEY, str(channel.id))


async def _pin_board(message: discord.Message) -> None:
    """Keep the live board pinned so it stays visible."""
    try:
        if message.pinned:
            return
        await message.pin(reason="Imperium live weekly leaderboard")
        logger.info("Pinned board message %s", message.id)
    except discord.HTTPException as exc:
        # Missing Manage Messages is fine — board still updates in-place
        logger.warning("Could not pin board message: %s", exc)


async def _remember_message(bot: Bot, message: discord.Message) -> None:
    bot.cached_board_message_id = message.id
    await bot.db.set_setting(MSG_KEY, str(message.id))
    if isinstance(message.channel, discord.TextChannel):
        await _remember_channel(bot, message.channel)
    await _pin_board(message)


async def _find_existing_board_anywhere(bot: Bot) -> discord.Message | None:
    if bot.user is None:
        return None
    for guild in bot.guilds:
        for ch in guild.text_channels:
            me = guild.me
            perms = ch.permissions_for(me) if me else None
            if not perms or not (perms.read_message_history and perms.view_channel):
                continue
            try:
                async for msg in ch.history(limit=40):
                    if _match(msg, bot.user.id):
                        logger.info("Reclaimed board %s in #%s", msg.id, ch.name)
                        return msg
            except discord.HTTPException:
                continue
    return None


async def channel_for(bot: Bot) -> discord.TextChannel | None:
    """
    Always prefer the configured board channel so the leaderboard
    stays permanently in one place (1554506265726820402 by default).
    """
    # 1) Config / env (hardstuck channel)
    if bot.config.leaderboard_channel_id:
        ch = await _get_text_channel(bot, bot.config.leaderboard_channel_id)
        if ch is not None:
            await _remember_channel(bot, ch)
            return ch

    # 2) Memory
    if bot.cached_board_channel_id:
        ch = await _get_text_channel(bot, bot.cached_board_channel_id)
        if ch is not None:
            return ch

    # 3) SQLite
    raw = await bot.db.get_setting(CH_KEY)
    if raw:
        try:
            ch = await _get_text_channel(bot, int(raw))
            if ch is not None:
                bot.cached_board_channel_id = ch.id
                return ch
        except ValueError:
            pass

    # 4) Reclaim existing post
    existing = await _find_existing_board_anywhere(bot)
    if existing is not None and isinstance(existing.channel, discord.TextChannel):
        await _remember_message(bot, existing)
        return existing.channel

    # 5) Fuzzy name
    for guild in bot.guilds:
        for ch in guild.text_channels:
            if not _name_looks_like_leaderboard(ch.name):
                continue
            me = guild.me
            perms = ch.permissions_for(me) if me else None
            if perms and perms.send_messages and perms.embed_links:
                logger.info("Auto-detected board channel #%s", ch.name)
                await _remember_channel(bot, ch)
                return ch
    return None


async def build_embed(bot: Bot) -> discord.Embed:
    tz = bot.config.timezone
    since = week_start(tz)
    ranks, team = await bot.db.leaderboard(since, TOP)
    return board(
        bot.config.brand_name,
        bot.config.brand_color,
        ranks,
        team,
        week_label(tz),
        next_week_start(tz),
        tz,
    )


async def refresh(bot: Bot) -> BoardResult:
    async with _lock:
        ch = await channel_for(bot)
        if ch is None:
            return BoardResult(
                None,
                "No leaderboard channel set. Run `/config leaderboard_channel:#channel` once.",
            )

        await _remember_channel(bot, ch)
        embed = await build_embed(bot)

        msg_id = bot.cached_board_message_id
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
                await _remember_message(bot, msg)
                return BoardResult(msg)
            except (discord.NotFound, discord.HTTPException) as exc:
                logger.warning("Saved board message unusable: %s", exc)
                bot.cached_board_message_id = None
                await bot.db.delete_setting(MSG_KEY)

        if bot.user:
            try:
                async for old in ch.history(limit=40):
                    if _match(old, bot.user.id):
                        await old.edit(embed=embed)
                        await _remember_message(bot, old)
                        return BoardResult(old)
            except discord.HTTPException as exc:
                logger.warning("History scan failed in #%s: %s", ch.name, exc)

        try:
            msg = await ch.send(embed=embed)
            await _remember_message(bot, msg)
            return BoardResult(msg)
        except discord.HTTPException as exc:
            logger.error("Post board failed: %s", exc)
            return BoardResult(
                None,
                f"Found {ch.mention} but could not post. "
                "Need Send Messages, Embed Links, Read Message History.",
            )


async def announce_new_week(bot: Bot) -> BoardResult:
    """Refresh board for the new Sunday week and post a short notice."""
    result = await refresh(bot)
    if result.message is None:
        return result
    ch = result.message.channel
    if not isinstance(ch, discord.TextChannel):
        return result
    try:
        await ch.send(
            embed=week_reset_notice(
                bot.config.brand_name,
                bot.config.brand_color,
                next_week_start(bot.config.timezone),
                bot.config.timezone,
            )
        )
    except discord.HTTPException as exc:
        logger.warning("Could not post week-reset notice: %s", exc)
    return result


async def weekly_rank_for(bot: Bot, user_id: int, display_name: str) -> tuple[float, int | None]:
    tz = bot.config.timezone
    since = week_start(tz)
    ranks, _ = await bot.db.leaderboard(since, TOP)
    for r in ranks:
        if r.user_id == user_id:
            return r.ap, r.rank
    from utils.helpers import day_start, month_start

    stats = await bot.db.agent_stats(
        user_id,
        display_name,
        day_start(tz),
        since,
        month_start(tz),
    )
    return stats.week.ap, None
