"""Help — everyone can use."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils.embeds import ok


class Help(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        for c in self.get_app_commands():
            c.default_permissions = None

    @app_commands.command(name="commands", description="List commands")
    async def commands_list(self, interaction: discord.Interaction) -> None:
        cfg = self.bot.config  # type: ignore[attr-defined]
        text = (
            "**Everyone can use these**\n\n"
            "`/sale <amount>` — log a sale (that amount only)\n"
            "`/mysales` — today / week / month / lifetime\n"
            "`/sales` — history\n"
            "`/remove_sale` — remove a sale\n"
            "`/leaderboard` — WEEKLY AP board\n"
            "`/refresh_leaderboard` — update board message\n"
            "`/reset_leaderboard confirm:True` — wipe all to $0\n"
            "`/config leaderboard_channel` — set board channel\n"
            "`/commands` — this list"
        )
        await interaction.response.send_message(
            embed=ok(f"📋 {cfg.brand_name}", text, cfg.brand_name, cfg.brand_color),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Help(bot))
