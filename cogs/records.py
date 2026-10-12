"""Private Imperium records — restricted command; posts only to private channel."""

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from utils.access import can_manage_records
from utils.embeds import err, ok
from utils.records import refresh_records
from utils.wall import refresh_record_wall

logger = logging.getLogger(__name__)


class Records(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        # Hide from the command picker for people without Manage Guild;
        # real lock is the allowlist check below.
        for c in self.get_app_commands():
            c.default_permissions = discord.Permissions(manage_guild=True)

    @app_commands.command(
        name="records",
        description="Refresh Imperium records in the private records channel (admin only)",
    )
    async def records_cmd(self, interaction: discord.Interaction) -> None:
        if not can_manage_records(interaction):
            await interaction.response.send_message(
                embed=err(
                    "Only the records manager can use `/records`.\n"
                    "Numbers only appear in the private records channel."
                ),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        cfg = self.bot.config  # type: ignore[attr-defined]
        try:
            result = await refresh_records(self.bot)  # type: ignore[arg-type]
            wall = await refresh_record_wall(self.bot)  # type: ignore[arg-type]
        except Exception:
            logger.exception("records failed")
            await interaction.followup.send(
                embed=err("Could not refresh records."), ephemeral=True
            )
            return

        if result.message is None:
            await interaction.followup.send(
                embed=err(result.error or "Could not post to the private records channel."),
                ephemeral=True,
            )
            return

        wall_note = (
            f"\nRecord Wall updated in {wall.message.channel.mention}."
            if wall.message
            else ""
        )
        # Do NOT echo the numbers here — they only live in the private / wall channels.
        await interaction.followup.send(
            embed=ok(
                "Records refreshed",
                f"Private records updated in {result.message.channel.mention}."
                f"{wall_note}\n"
                "Numbers were not posted in public chat.",
                cfg.brand_name,
                cfg.brand_color,
            ),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Records(bot))
