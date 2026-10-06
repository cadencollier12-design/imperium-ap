"""Weekly leaderboard — auto-resets every Sunday; lifetime untouched."""

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils.board import WEEK_KEY, announce_new_week, refresh, week_label
from utils.embeds import board, err, ok
from utils.helpers import next_week_start, utc_iso, week_start

logger = logging.getLogger(__name__)


class Leaderboard(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        for c in self.get_app_commands():
            c.default_permissions = None
        self.sunday_watch.start()

    async def cog_unload(self) -> None:
        self.sunday_watch.cancel()

    @app_commands.command(
        name="leaderboard",
        description="This week's rankings (resets every Sunday)",
    )
    async def leaderboard(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=False)
        cfg = self.bot.config  # type: ignore[attr-defined]
        tz = cfg.timezone
        since = week_start(tz)
        from utils.board import TOP as BOARD_TOP

        ranks, team = await self.bot.db.leaderboard(since, BOARD_TOP)  # type: ignore[attr-defined]
        await interaction.followup.send(
            embed=board(
                cfg.brand_name,
                cfg.brand_color,
                ranks,
                team,
                week_label(tz),
                next_week_start(tz),
                tz,
            )
        )

    @app_commands.command(
        name="refresh_leaderboard",
        description="Force-update the live board message",
    )
    async def refresh_leaderboard(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        cfg = self.bot.config  # type: ignore[attr-defined]
        result = await refresh(self.bot)  # type: ignore[arg-type]
        if result.message is None:
            await interaction.followup.send(
                embed=err(result.error or "Could not refresh the board."),
                ephemeral=True,
            )
            return
        await interaction.followup.send(
            embed=ok(
                "Board updated",
                f"Live board refreshed in {result.message.channel.mention}.",
                cfg.brand_name,
                cfg.brand_color,
            ),
            ephemeral=True,
        )

    @tasks.loop(minutes=1.0)
    async def sunday_watch(self) -> None:
        """When the Sunday week boundary rolls over, refresh the empty board."""
        cfg = self.bot.config  # type: ignore[attr-defined]
        db = self.bot.db  # type: ignore[attr-defined]
        current = week_start(cfg.timezone)
        key = utc_iso(current)
        stored = await db.get_setting(WEEK_KEY)
        if stored == key:
            return
        if stored is None:
            # First boot — record current week, don't announce a fake reset
            await db.set_setting(WEEK_KEY, key)
            logger.info("Week pointer set to %s", key)
            return
        logger.info("Sunday rollover detected (%s → %s)", stored, key)
        await db.set_setting(WEEK_KEY, key)
        try:
            result = await announce_new_week(self.bot)  # type: ignore[arg-type]
            if result.message:
                logger.info("Posted new-week board in #%s", result.message.channel)
            else:
                logger.warning("Week rolled over but board update failed: %s", result.error)
        except Exception:
            logger.exception("sunday rollover refresh failed")

    @sunday_watch.before_loop
    async def before_sunday_watch(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Leaderboard(bot))
