"""Sale commands — everyone can use."""

from __future__ import annotations

import logging
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

from database import AgentStats, Stats
from utils.board import refresh
from utils.embeds import err, history, mysales, sale_post
from utils.helpers import now, periods

logger = logging.getLogger(__name__)


class Sales(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        for c in self.get_app_commands():
            c.default_permissions = None

    @app_commands.command(name="sale", description="Record a sale (AP)")
    @app_commands.describe(amount="AP amount, e.g. 2112")
    async def sale(self, interaction: discord.Interaction, amount: float) -> None:
        await interaction.response.defer(ephemeral=False)
        cfg = self.bot.config  # type: ignore[attr-defined]
        db = self.bot.db  # type: ignore[attr-defined]

        if amount <= 0:
            await interaction.followup.send(embed=err("Amount must be positive."), ephemeral=True)
            return
        if amount > 10_000_000:
            await interaction.followup.send(embed=err("Amount looks too high."), ephemeral=True)
            return

        t = now(cfg.timezone)
        u = interaction.user
        dup = await db.find_duplicate(u.id, amount, t - timedelta(seconds=cfg.duplicate_seconds))
        if dup:
            await interaction.followup.send(
                embed=err(f"Duplicate? You already logged ${amount:,.0f} as `#{dup.id}`."),
                ephemeral=True,
            )
            return

        try:
            sale = await db.add_sale(u.id, u.display_name, amount, t)
        except Exception:
            logger.exception("sale failed")
            await interaction.followup.send(embed=err("Could not save sale."), ephemeral=True)
            return

        await interaction.followup.send(
            embed=sale_post(cfg.brand_name, cfg.brand_color, u.display_name, amount, sale.id)
        )
        try:
            result = await refresh(self.bot)  # type: ignore[arg-type]
            if result.message is None:
                logger.warning(
                    "Sale #%s saved but board not updated: %s",
                    sale.id,
                    result.error,
                )
        except Exception:
            logger.exception("board refresh after sale")

    @app_commands.command(name="mysales", description="Your AP including lifetime")
    async def mysales_cmd(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        cfg = self.bot.config  # type: ignore[attr-defined]
        db = self.bot.db  # type: ignore[attr-defined]
        p = periods(cfg.timezone)
        stats = await db.agent_stats(interaction.user.id, p["day"], p["week"], p["month"])
        if stats is None:
            z = Stats(0.0, 0)
            stats = AgentStats(interaction.user.id, interaction.user.display_name, z, z, z, z)
        await interaction.followup.send(
            embed=mysales(cfg.brand_name, cfg.brand_color, stats), ephemeral=True
        )

    @app_commands.command(name="sales", description="Recent sales")
    @app_commands.describe(agent="Filter by agent", limit="1–25", include_removed="Include removed")
    async def sales_cmd(
        self,
        interaction: discord.Interaction,
        agent: discord.Member | None = None,
        limit: app_commands.Range[int, 1, 25] = 15,
        include_removed: bool = False,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        cfg = self.bot.config  # type: ignore[attr-defined]
        db = self.bot.db  # type: ignore[attr-defined]
        rows = await db.list_sales(
            user_id=agent.id if agent else None,
            limit=limit,
            include_removed=include_removed,
        )
        title = f"📜 Sales — {agent.display_name}" if agent else f"📜 {cfg.brand_name} Team Sales"
        await interaction.followup.send(
            embed=history(cfg.brand_name, cfg.brand_color, rows, cfg.timezone, title),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Sales(bot))
