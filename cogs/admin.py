"""Remove sales + config — everyone can use."""

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from utils.board import CH_KEY, MSG_KEY, refresh
from utils.embeds import err, ok
from utils.helpers import money, now, when

logger = logging.getLogger(__name__)


class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        for c in self.get_app_commands():
            c.default_permissions = None

    @app_commands.command(name="remove_sale", description="Remove a sale")
    @app_commands.describe(
        sale_id="Sale ID from /sales",
        agent="Agent (empty = you)",
        amount="Match AP amount",
    )
    async def remove_sale(
        self,
        interaction: discord.Interaction,
        sale_id: int | None = None,
        agent: discord.Member | None = None,
        amount: float | None = None,
    ) -> None:
        await interaction.response.defer(ephemeral=False)
        cfg = self.bot.config  # type: ignore[attr-defined]
        db = self.bot.db  # type: ignore[attr-defined]
        t = now(cfg.timezone)
        actor = interaction.user

        if sale_id is not None:
            target = await db.get_sale(sale_id)
            if target is None or target.removed:
                await interaction.followup.send(embed=err("Sale not found / already gone."), ephemeral=True)
                return
        else:
            uid = agent.id if agent else actor.id
            name = agent.display_name if agent else actor.display_name
            if amount is not None:
                target = await db.find_by_amount(uid, amount)
                if target is None:
                    await interaction.followup.send(
                        embed=err(f"No {money(amount)} sale for {name}."), ephemeral=True
                    )
                    return
            else:
                rows = await db.list_sales(user_id=uid, limit=1)
                if not rows:
                    await interaction.followup.send(embed=err(f"{name} has no sales."), ephemeral=True)
                    return
                target = rows[0]

        removed = await db.remove_sale(target.id, actor.id, t)
        if removed is None:
            await interaction.followup.send(embed=err("Could not remove."), ephemeral=True)
            return
        name = removed.display_name or str(removed.user_id)
        await interaction.followup.send(
            embed=ok(
                "🗑️ Removed",
                f"Sale `#{removed.id}` for **{name}** ({money(removed.amount)}).",
                cfg.brand_name,
                cfg.brand_color,
            )
        )
        try:
            result = await refresh(self.bot)  # type: ignore[arg-type]
            if result.message is None:
                logger.warning("Removed sale but board not updated: %s", result.error)
        except Exception:
            logger.exception("refresh after remove")

    @app_commands.command(name="sale_info", description="Look up sale by ID")
    async def sale_info(self, interaction: discord.Interaction, sale_id: int) -> None:
        await interaction.response.defer(ephemeral=True)
        cfg = self.bot.config  # type: ignore[attr-defined]
        s = await self.bot.db.get_sale(sale_id)  # type: ignore[attr-defined]
        if s is None:
            await interaction.followup.send(embed=err("Not found."), ephemeral=True)
            return
        await interaction.followup.send(
            embed=ok(
                f"Sale #{s.id}",
                f"**{s.display_name}** — {money(s.amount)}\n"
                f"{when(s.created_at, cfg.timezone)}\n"
                f"{'Removed' if s.removed else 'Active'}",
                cfg.brand_name,
                cfg.brand_color,
            ),
            ephemeral=True,
        )

    config = app_commands.Group(name="config", description="Settings")

    @config.command(name="leaderboard_channel", description="Set live board channel")
    async def lb_channel(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        cfg = self.bot.config  # type: ignore[attr-defined]
        db = self.bot.db  # type: ignore[attr-defined]
        # Stick this channel in memory + DB immediately
        self.bot.cached_board_channel_id = channel.id  # type: ignore[attr-defined]
        self.bot.cached_board_message_id = None  # type: ignore[attr-defined]
        await db.set_setting(CH_KEY, str(channel.id))
        await db.delete_setting(MSG_KEY)
        result = await refresh(self.bot)  # type: ignore[arg-type]
        if result.message is None:
            await interaction.followup.send(
                embed=err(
                    result.error
                    or f"Saved {channel.mention} but could not post. "
                    "Check Send Messages + Embed Links + Read Message History."
                ),
                ephemeral=True,
            )
            return
        await interaction.followup.send(
            embed=ok(
                "✅ Channel Set",
                f"Board is hardstuck to {channel.mention}.\n"
                f"Also set Railway env `LEADERBOARD_CHANNEL_ID={channel.id}` "
                "so it survives restarts.\n"
                "Updates on every `/sale`. Clears only with "
                "`/reset_leaderboard confirm:True`.",
                cfg.brand_name,
                cfg.brand_color,
            ),
            ephemeral=True,
        )

    @config.command(name="show", description="Show settings")
    async def show(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        cfg = self.bot.config  # type: ignore[attr-defined]
        db = self.bot.db  # type: ignore[attr-defined]
        ch = await db.get_setting(CH_KEY) or (
            str(cfg.leaderboard_channel_id) if cfg.leaderboard_channel_id else None
        )
        await interaction.followup.send(
            embed=ok(
                "⚙️ Config",
                f"**Brand:** {cfg.brand_name}\n"
                f"**Timezone:** `{cfg.timezone}`\n"
                f"**Board channel:** {f'<#{ch}>' if ch else '_not set_'}\n"
                f"**Mode:** all sales until `/reset_leaderboard` (no timer)",
                cfg.brand_name,
                cfg.brand_color,
            ),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Admin(bot))
