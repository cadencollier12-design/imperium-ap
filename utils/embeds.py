"""Discord embeds — clean, readable, on-brand."""

from __future__ import annotations

from datetime import datetime, timezone

import discord

from typing import TYPE_CHECKING

from database import AgentStats, Rank, Sale, Stats
from utils.helpers import countdown, medal, money, updated_stamp, when

if TYPE_CHECKING:
    from utils.records import ImperiumRecords

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
    e.set_footer(text="Shows this week only · sales stay saved · board view clears Sunday")
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


def _personal_line(label: str, rec: object | None) -> str:
    if rec is None:
        return f"**{label}** · _none yet_"
    ap = getattr(rec, "ap", 0.0)
    holder = getattr(rec, "holder", None)
    period = getattr(rec, "label", "—")
    if ap <= 0 or not holder:
        return f"**{label}** · _none yet_"
    return f"**{label}** · {money(ap)} — **{holder}** ({period})"


def records_board(brand: str, color: int, data: "ImperiumRecords") -> discord.Embed:
    medals = ("🥇", "🥈", "🥉")
    if data.month_top3:
        top3_lines = []
        for i, rec in enumerate(data.month_top3):
            medal = medals[i] if i < len(medals) else f"#{i + 1}"
            top3_lines.append(
                f"{medal} **{rec.holder}** — {money(rec.ap)}"
            )
        top3_block = "\n".join(top3_lines)
    else:
        top3_block = "_No sales this month yet._"

    body = (
        f"**{data.stamp}**\n"
        f"_Private Imperium numbers — Tobe / leadership_\n\n"
        f"**All-time AP sold** · {money(data.all_time_ap)}\n"
        f"**All-time policies sold** · {data.all_time_policies}\n\n"
        f"**Current weekly total** · {money(data.current_week.ap)} "
        f"({data.current_week.label})\n"
        f"**Best week of AP sold** · {money(data.best_week.ap)} "
        f"({data.best_week.label})\n\n"
        f"**Current monthly total** · {money(data.current_month.ap)} "
        f"({data.current_month.label})\n"
        f"**Best month ever** · {money(data.best_month.ap)} "
        f"({data.best_month.label})\n\n"
        f"**Most $10K weeks in a row (current)** · {data.ten_k_streak_current}\n"
        f"**Most $10K weeks in a row (record)** · {data.ten_k_streak_best}\n\n"
        f"{_personal_line('Personal weekly record', data.personal_weekly_record)}\n"
        f"{_personal_line('Personal monthly record', data.personal_monthly_record)}\n\n"
        f"**This month’s top producers** ({data.current_month.label})\n"
        f"{top3_block}"
    )
    e = discord.Embed(
        title=f"{brand} Records",
        description=body,
        color=discord.Color(color),
        timestamp=datetime.now(timezone.utc),
    )
    e.set_footer(text="Updates on every /sale")
    return e

def _wall_section(title: str, rule: str, entries: list, empty: str) -> list[str]:
    lines = [f"**{title}**", rule, ""]
    if not entries:
        lines.append(empty)
    else:
        medals = ("🥇", "🥈", "🥉")
        for i, e in enumerate(entries):
            name = getattr(e, "display_name", "?")
            ap = getattr(e, "ap", 0.0)
            period = getattr(e, "period_label", None) or getattr(e, "month_label", "—")
            medal = medals[i] if i < len(medals) else f"`#{i + 1}`"
            lines.append(f"{medal} **{name}** — {money(ap)} · {period}")
    lines.append("")
    return lines


def record_wall_board(
    brand: str,
    color: int,
    weekly: list,
    monthly: list,
    stamp: str,
) -> discord.Embed:
    """Record Wall — weekly >$20k and monthly >$50k personal AP."""
    lines = [f"**{stamp}**", ""]
    lines.extend(
        _wall_section(
            "Weekly records",
            "Must be **over $20,000** personal AP in a week to be recognized.",
            weekly,
            "_No weekly records over $20,000 yet._",
        )
    )
    lines.extend(
        _wall_section(
            "Monthly records",
            "Must be **over $50,000** personal AP in a month to be recognized.",
            monthly,
            "_No monthly records over $50,000 yet._",
        )
    )
    e = discord.Embed(
        title=f"{brand} Record Wall",
        description="\n".join(lines).rstrip(),
        color=discord.Color(color),
        timestamp=datetime.now(timezone.utc),
    )
    e.set_footer(text="Weekly >$20k · Monthly >$50k · Updates on every /sale")
    return e

def sales_catalogue(brand: str, color: int, data: "ImperiumRecords") -> discord.Embed:
    """Catalogue: date/time, agent, sale amount, that agent's week total."""
    lines: list[str] = [f"**{data.stamp}**", ""]
    if not data.catalogue:
        lines.append("_No sales logged yet. Use `/sale` to start the catalogue._")
    else:
        for entry in data.catalogue:
            local = entry.when_local
            hour = local.strftime("%I").lstrip("0") or "0"
            stamp = (
                f"{local.month}/{local.day}/{local.strftime('%y')} "
                f"{hour}:{local.strftime('%M')}{local.strftime('%p').lower()}"
            )
            lines.append(
                f"`#{entry.sale_id}` **{stamp}** · **{entry.display_name}** · "
                f"{money(entry.amount)} · week total **{money(entry.week_total)}**"
            )

    # Fit Discord embed description limit
    body = "\n".join(lines)
    while len(body) > 3900 and len(lines) > 3:
        lines.pop()
        body = "\n".join(lines) + "\n_…older sales truncated — use `/sales` for full history_"

    shown = max(0, len(lines) - 2)
    e = discord.Embed(
        title=f"{brand} Sale Catalogue",
        description=body,
        color=discord.Color(color),
        timestamp=datetime.now(timezone.utc),
    )
    e.set_footer(
        text=f"Showing newest {min(shown, data.catalogue_total)} of {data.catalogue_total} "
        f"sales · date · agent · amount · their week total"
    )
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
