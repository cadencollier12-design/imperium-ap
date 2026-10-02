"""Embeds."""

from __future__ import annotations

from datetime import datetime, timezone

import discord

from database import AgentStats, Rank, Sale, Stats
from utils.helpers import medal, money, when

SEP = "━━━━━━━━━━━━━━━━━━━━"


def sale_post(brand: str, color: int, name: str, amount: float, sale_id: int) -> discord.Embed:
    e = discord.Embed(
        title="🔥 NEW SALE",
        description=f"**{name}**\n**{money(amount)} AP**",
        color=discord.Color(color),
        timestamp=datetime.now(timezone.utc),
    )
    e.set_footer(text=f"{brand} · Sale #{sale_id}")
    return e


def mysales(brand: str, color: int, s: AgentStats) -> discord.Embed:
    e = discord.Embed(
        title=f"📊 {s.display_name} — Sales Report",
        color=discord.Color(color),
        timestamp=datetime.now(timezone.utc),
    )
    for label, p in (("Today", s.today), ("This Week", s.week), ("This Month", s.month)):
        e.add_field(name=label, value=f"**{money(p.ap)}** AP\n{p.policies} policies", inline=True)
    e.add_field(
        name="Lifetime",
        value=f"**{money(s.lifetime.ap)}** AP\n{s.lifetime.policies} policies",
        inline=False,
    )
    e.set_footer(text=brand)
    return e


def board(brand: str, color: int, ranks: list[Rank], team: Stats) -> discord.Embed:
    body = (
        "_No sales yet. Use `/sale` to get ranked!_"
        if not ranks
        else "\n".join(f"{medal(r.rank)} **{r.display_name}** — {money(r.ap)}" for r in ranks)
    )
    e = discord.Embed(
        title=f"🏆 {brand.upper()} WEEKLY AP",
        description=(
            f"{body}\n{SEP}\n"
            f"**TEAM AP:** {money(team.ap)}\n"
            f"**POLICIES SOLD:** {team.policies}"
        ),
        color=discord.Color(color),
        timestamp=datetime.now(timezone.utc),
    )
    e.set_footer(text="Weekly AP · clears only with /reset_leaderboard · Live")
    return e


def history(brand: str, color: int, sales: list[Sale], tz: str, title: str) -> discord.Embed:
    e = discord.Embed(title=title, color=discord.Color(color), timestamp=datetime.now(timezone.utc))
    if not sales:
        e.description = "_No sales found._"
    else:
        lines = []
        for s in sales:
            name = s.display_name or f"User {s.user_id}"
            tag = " · ~~removed~~" if s.removed else ""
            lines.append(f"`#{s.id}` **{name}** — {money(s.amount)} · {when(s.created_at, tz)}{tag}")
        e.description = "\n".join(lines)
    e.set_footer(text=f"{brand} · /remove_sale")
    return e


def err(msg: str) -> discord.Embed:
    return discord.Embed(title="⚠️ Error", description=msg, color=discord.Color(0x8B0000))


def ok(title: str, desc: str, brand: str, color: int) -> discord.Embed:
    e = discord.Embed(
        title=title, description=desc, color=discord.Color(color),
        timestamp=datetime.now(timezone.utc),
    )
    e.set_footer(text=brand)
    return e
