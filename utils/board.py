"""
Live WEEKLY AP channel message.

The board channel is sticky:
  1) in-memory cache (survives within a running process)
  2) SQLite settings
  3) LEADERBOARD_CHANNEL_ID env
  4) reclaim an existing WEEKLY AP post from Discord
  5) fuzzy channel-name match (leaderboard / leader-board / etc.)
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

import discord

from utils.embeds import board
from utils.helpers import now

if TYPE_CHECKING:
    from bot import Bot

logger = logging.getLogger(__name__)

CH_KEY = "leaderboard_channel_id"
MSG_KEY = "leaderboard_message_id"
HINTS = ("WEEKLY AP",)
TOP = 50
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
    """Match leaderboard, leader-board, 🏆leader-board🏆, etc."""
    cleaned = re.sub(r"[^a-z0-9]+", "", name.lower())
    return "leaderboard" in cleaned or cleaned in {"leaderboard", "lb", "apboard"}


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
    logger.warning("Channel %s is not a text channel (%s)", channel_id, type(ch).__name__)
    return None


async def _remember_channel(bot: Bot, channel: discord.TextChannel) -> None:
    bot.cached_board_channel_id = channel.id
    await bot.db.set_setting(CH_KEY, str(channel.id))


async def _remember_message(bot: Bot, message: discord.Message) -> None:
    bot.cached_board_message_id = message.id
    await bot.db.set_setting(MSG_KEY, str(message.id))
    if isinstance(message.channel, discord.TextChannel):
        await _remember_channel(bot, message.channel)


async def _find_existing_board_anywhere(bot: Bot) -> discord.Message | None:
    """If we already posted a WEEKLY AP embed, reclaim it and stick to that channel."""
    if bot.user is None:
        return None
    for guild in bot.guilds:
        for ch in guild.text_channels:
            me = guild.me
            perms = ch.permissions_for(me) if me else None
            if not perms or not (perms.read_message_history and perms.view_channel):
                continue
            try:
                async for msg in ch.history(limit=30):
                    if _match(msg, bot.user.id):
                        logger.info(
                            "Reclaimed existing board message %s in #%s",
                            msg.id,
                            ch.name,
                        )
                        return msg
            except discord.HTTPException:
                continue
    return None


async def channel_for(bot: Bot) -> discord.TextChannel | None:
    """Resolve the hardstuck leaderboard channel."""
    # 1) Memory
    if bot.cached_board_channel_id:
        ch = await _get_text_channel(bot, bot.cached_board_channel_id)
        if ch is not None:
            return ch

    # 2) SQLite
    raw = await bot.db.get_setting(CH_KEY)
    if raw:
        try:
            ch = await _get_text_channel(bot, int(raw))
            if ch is not None:
                bot.cached_board_channel_id = ch.id
                return ch
        except ValueError:
            pass

    # 3) Env
    if bot.config.leaderboard_channel_id:
        ch = await _get_text_channel(bot, bot.config.leaderboard_channel_id)
        if ch is not None:
            await _remember_channel(bot, ch)
            return ch

    # 4) Reclaim an existing WEEKLY AP post (survives DB wipe / Railway restart)
    existing = await _find_existing_board_anywhere(bot)
    if existing is not None and isinstance(existing.channel, discord.TextChannel):
        await _remember_message(bot, existing)
        return existing.channel

    # 5) Fuzzy channel name
    for guild in bot.guilds:
        for ch in guild.text_channels:
            if not _name_looks_like_leaderboard(ch.name):
                continue
            me = guild.me
            perms = ch.permissions_for(me) if me else None
            if perms and perms.send_messages and perms.embed_links:
                logger.info("Auto-detected board channel #%s (%s)", ch.name, ch.id)
                await _remember_channel(bot, ch)
                return ch

    return None


async def refresh(bot: Bot) -> BoardResult:
    """Update board message. Never clears rankings — only edits the embed."""
    async with _lock:
        ch = await channel_for(bot)
        if ch is None:
            return BoardResult(
                None,
                "No leaderboard channel found. Run "
                "`/config leaderboard_channel:#🏆leader-board🏆` once, "
                "and set Railway `LEADERBOARD_CHANNEL_ID` so it sticks after restarts.",
            )

        await _remember_channel(bot, ch)
        ranks, team = await bot.db.leaderboard(TOP)
        embed = board(bot.config.brand_name, bot.config.brand_color, ranks, team)

        # Prefer cached / saved message id
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
                logger.info("Updated board message %s in #%s", msg.id, ch.name)
                return BoardResult(msg)
            except (discord.NotFound, discord.HTTPException, ValueError) as exc:
                logger.warning("Saved board message %s unusable: %s", msg_id, exc)
                bot.cached_board_message_id = None
                await bot.db.delete_setting(MSG_KEY)

        # Reclaim any WEEKLY AP post in THIS channel
        if bot.user:
            try:
                async for old in ch.history(limit=30):
                    if _match(old, bot.user.id):
                        await old.edit(embed=embed)
                        await _remember_message(bot, old)
                        logger.info("Reclaimed board %s in #%s", old.id, ch.name)
                        return BoardResult(old)
            except discord.HTTPException as exc:
                logger.warning("History scan failed in #%s: %s", ch.name, exc)

        # Post new
        try:
            msg = await ch.send(embed=embed)
            await _remember_message(bot, msg)
            logger.info("Posted new board %s in #%s", msg.id, ch.name)
            return BoardResult(msg)
        except discord.HTTPException as exc:
            logger.error("Post board failed in #%s: %s", ch.name, exc)
            return BoardResult(
                None,
                f"Found {ch.mention} but could not post/edit there. "
                "Give the bot **Send Messages**, **Embed Links**, and "
                "**Read Message History** in that channel.",
            )


async def wipe(bot: Bot, by: int) -> tuple[BoardResult, int, float]:
    """Manual reset — wipe all AP and post empty board."""
    async with _lock:
        n, ap = await bot.db.wipe_all(by, now(bot.config.timezone))
        # Temporarily release path by calling inner logic without re-entering lock:
        # we already hold _lock, so do channel work inline.
        ch = await channel_for(bot)
        if ch is None:
            return (
                BoardResult(
                    None,
                    "Sales wiped, but no board channel is set. "
                    "Run `/config leaderboard_channel`.",
                ),
                n,
                ap,
            )

        await _remember_channel(bot, ch)
        bot.cached_board_message_id = None
        await bot.db.delete_setting(MSG_KEY)

        if bot.user:
            try:
                async for old in ch.history(limit=40):
                    if _match(old, bot.user.id):
                        try:
                            await old.delete()
                        except discord.HTTPException:
                            pass
            except discord.HTTPException:
                pass

        ranks, team = await bot.db.leaderboard(TOP)
        embed = board(bot.config.brand_name, bot.config.brand_color, ranks, team)
        try:
            msg = await ch.send(embed=embed)
            await _remember_message(bot, msg)
            return BoardResult(msg), n, ap
        except discord.HTTPException as exc:
            logger.error("Post wiped board failed: %s", exc)
            return (
                BoardResult(None, f"Sales wiped, but could not post board: {exc}"),
                n,
                ap,
            )
