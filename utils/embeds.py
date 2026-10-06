"""Discord embeds — clean, readable, on-brand."""

from __future__ import annotations

from datetime import datetime, timezone

import discord

from database import AgentStats, Rank, Sale, Stats
from utils.helpers import countdown, medal, money, updated_stamp, when

SEP = "──────────────────────"


def sale_post(
    brand: str,
    color: int,
    name: str,
    amount: float,
    sale_id: int,
    week_ap: float,
    week_rank: int | None,
) -> discord.Embed:
    rank_line = (
        f"**Weekly rank:** #{week_rank}"
        if week_rank
        else "**Weekly rank:** — (first sale this week)"
    )
    e = discord.Embed(
        title="Sale logged",
        description=(
            f"**Agent** · {name}\n"
            f"**Amount** · {money(amount)} AP\n"
            f"**This week** · {money(week_ap)} AP\n"
            f"{rank_line}"
        ),
        color=discord.Color(color),
        timestamp=datetime.now(timezone.utc),
    )
    e.set_footer(text=f"{brand} · Sale #{sale_id} · Lifetime saved forever")
    return e


def mysales(brand: str, color: int, s: AgentStats, next_reset: datetime, tz: str) -> discord.Embed:
    e = discord.Embed(
        title=f"{s.display_name} · Sales",
        description=(
            f"**Lifetime** is permanent.\n"
            f"Weekly board resets in **{countdown(next_reset, tz)}** (Sunday)."
        ),
        color=discord.Color(color),
        timestamp=datetime.now(timezone.utc),
    )
    e.add_field(
        name="Today",
        value=f"**{money(s.today.ap)}**\n{s.today.policies} sale(s)",
        inline=True,
    )
    e.add_field(
        name="This week",
        value=f"**{money(s.week.ap)}**\n{s.week.policies} sale(s)",
        inline=True,
    )
    e.add_field(
        name="This month",
        value=f"**{money(s.month.ap)}**\n{s.month.policies} sale(s)",
        inline=True,
    )
    e.add_field(
        name="Lifetime",
        value=f"**{money(s.lifetime.ap)} AP** · {s.lifetime.policies} sale(s) all-time",
        inline=False,
    )
    e.set_footer(text=brand)
    return e


def board(
    brand: str,
    color: int,
    ranks: list[Rank],
    team: Stats,
    week_label: str,
    next_reset: datetime,
    tz: str,
) -> discord.Embed:
    if not ranks:
        body = "_No sales this week yet. Use `/sale` to take the top spot._"
    else:
        lines = []
        for r in ranks:
            lines.append(
                f"{medal(r.rank)} **{r.display_name}** — {money(r.ap)} "
                f"· {r.policies} sale{'s' if r.policies != 1 else ''}"
            )
        body = "\n".join(lines)

    e = discord.Embed(
        title=f"{brand} · Weekly Leaderboard",
        description=(
            f"**{updated_stamp(tz)}**\n\n"
            f"{body}\n"
            f"{SEP}\n"
            f"**Team this week** · {money(team.ap)} AP · {team.policies} sale(s)\n"
            f"**Week** · {week_label}\n"
            f"**Resets** · Sunday ({countdown(next_reset, tz)} left)"
        ),
        color=discord.Color(color),
        timestamp=datetime.now(timezone.utc),
    )
    e.set_footer(text="Weekly rankings · Lifetime stats stay in /mysales")
    return e


def history(
    brand: str, color: int, sales: list[Sale], tz: str, title: str
) -> discord.Embed:
    e = discord.Embed(
        title=title,
        color=discord.Color(color),
        timestamp=datetime.now(timezone.utc),
    )
    if not sales:
        e.description = "_No sales found._"
    else:
        lines = []
        for s in sales:
            name = s.display_name or f"User {s.user_id}"
            tag = " · removed" if s.removed else ""
            lines.append(
                f"`#{s.id}` **{name}** — {money(s.amount)} · {when(s.created_at, tz)}{tag}"
            )
        e.description = "\n".join(lines)
    e.set_footer(text=f"{brand} · /remove_sale to undo")
    return e


def week_reset_notice(brand: str, color: int, next_reset: datetime, tz: str) -> discord.Embed:
    e = discord.Embed(
        title="New week · leaderboard reset",
        description=(
            "The weekly board is clear. Lifetime stats are unchanged.\n"
            f"Next reset: **Sunday** ({countdown(next_reset, tz)} from now).\n"
            "Log sales with `/sale`."
        ),
        color=discord.Color(color),
        timestamp=datetime.now(timezone.utc),
    )
    e.set_footer(text=brand)
    return e


def err(msg: str) -> discord.Embed:
    return discord.Embed(
        title="Something went wrong",
        description=msg,
        color=discord.Color(0xB91C1C),
    )


def ok(title: str, desc: str, brand: str, color: int) -> discord.Embed:
    e = discord.Embed(
        title=title,
        description=desc,
        color=discord.Color(color),
        timestamp=datetime.now(timezone.utc),
    )
    e.set_footer(text=brand)
    return e
