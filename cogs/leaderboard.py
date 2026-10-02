"""Leaderboard — manual reset only, no timer."""

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from utils.board import TOP, refresh, wipe
from utils.embeds import board, err, ok
from utils.helpers import money

logger = logging.getLogger(__name__)


class Leaderboard(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        for c in self.get_app_commands():
            c.default_permissions = None

    @app_commands.command(name="leaderboard", description="Live WEEKLY AP board")
    async def leaderboard(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=False)
        cfg = self.bot.config  # type: ignore[attr-defined]
        ranks, team = await self.bot.db.leaderboard(TOP)  # type: ignore[attr-defined]
        await interaction.followup.send(embed=board(cfg.brand_name, cfg.brand_color, ranks, team))

    @app_commands.command(name="refresh_leaderboard", description="Update the live board message")
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
                "✅ Updated",
                f"Board refreshed in {result.message.channel.mention}.",
                cfg.brand_name,
                cfg.brand_color,
            ),
            ephemeral=True,
        )

    @app_commands.command(
        name="reset_leaderboard",
        description="FULL WIPE — everyone to $0",
    )
    @app_commands.describe(confirm="Must be True to wipe")
    async def reset_leaderboard(
        self, interaction: discord.Interaction, confirm: bool = False
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        cfg = self.bot.config  # type: ignore[attr-defined]
        if not confirm:
            await interaction.followup.send(
                embed=err("This wipes ALL AP.\nConfirm: `/reset_leaderboard confirm:True`"),
                ephemeral=True,
            )
            return
        result, n, ap = await wipe(self.bot, interaction.user.id)  # type: ignore[arg-type]
        if result.message is None:
            await interaction.followup.send(
                embed=err(result.error or f"Wiped {n} sales, but board update failed."),
                ephemeral=True,
            )
            return
        await interaction.followup.send(
            embed=ok(
                "✅ Reset",
                f"Everyone is at **$0**.\nCleared **{n}** sales ({money(ap)}).\n"
                f"Fresh board in {result.message.channel.mention}.",
                cfg.brand_name,
                cfg.brand_color,
            ),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Leaderboard(bot))
