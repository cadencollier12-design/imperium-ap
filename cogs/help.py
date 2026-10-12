"""Help — everyone can use."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils.embeds import ok
from utils.helpers import countdown, next_week_start


class Help(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        for c in self.get_app_commands():
            c.default_permissions = None

    @app_commands.command(name="commands", description="How to use the bot")
    async def commands_list(self, interaction: discord.Interaction) -> None:
        cfg = self.bot.config  # type: ignore[attr-defined]
        reset_in = countdown(next_week_start(cfg.timezone), cfg.timezone)
        text = (
            "**Everyone can use these**\n\n"
            f"`/sale <amount>` — log a sale (credits **you**)\n"
            f"`/mysales` — today / week / month / **lifetime forever**\n"
            f"`/leaderboard` — this week's rankings\n"
            f"`/sales` — recent history\n"
            f"`/remove_sale` — undo a mistake\n"
            f"`/refresh_leaderboard` — refresh the live board\n"
            f"`/config leaderboard_channel` — public weekly board\n\n"
            f"_`/records` is private — records manager only; "
            f"numbers post only in the private records channel._\n\n"
            f"Weekly **board view** rolls over Sunday ({reset_in} left) — "
            f"sales are **not deleted**.\n"
            f"Lifetime stays in `/mysales` forever."
        )
        await interaction.response.send_message(
            embed=ok(f"{cfg.brand_name} commands", text, cfg.brand_name, cfg.brand_color),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Help(bot))
