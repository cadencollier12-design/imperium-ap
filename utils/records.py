"""Private Imperium records — all-time totals, bests, streaks, trainer/MGA, sale catalogue."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import discord

from utils.embeds import records_board, sales_catalogue
from utils.helpers import month_start, updated_stamp, week_start, zone

if TYPE_CHECKING:
    from bot import Bot

logger = logging.getLogger(__name__)

CH_KEY = "private_records_channel_id"
MSG_KEY = "private_records_message_id"
CAT_MSG_KEY = "private_catalogue_message_id"
HINTS = ("IMPERIUM RECORDS",)
CAT_HINTS = ("SALE CATALOGUE", "SALES CATALOGUE")
TEN_K = 10_000.0
CATALOGUE_LIMIT = 80  # newest sales kept in the catalogue embed

_lock = asyncio.Lock()


@dataclass
class PeriodRecord:
    ap: float
    label: str
    holder: str | None = None
    policies: int = 0


@dataclass
class CatalogueEntry:
    when_local: datetime
    display_name: str
    amount: float
    week_total: float
    sale_id: int


@dataclass
class ImperiumRecords:
    all_time_ap: float
    all_time_policies: int
    current_week: PeriodRecord
    best_week: PeriodRecord
    current_month: PeriodRecord
    best_month: PeriodRecord
    ten_k_streak_current: int
    ten_k_streak_best: int
    personal_weekly_record: PeriodRecord | None
    personal_monthly_record: PeriodRecord | None
    month_top3: list[PeriodRecord] = field(default_factory=list)
    catalogue: list[CatalogueEntry] = field(default_factory=list)
    catalogue_total: int = 0
    stamp: str = ""


@dataclass
class RecordsResult:
    message: discord.Message | None
    catalogue_message: discord.Message | None = None
    error: str | None = None
    data: ImperiumRecords | None = None


def _parse_iso(iso: str, tz_name: str) -> datetime:
    dt = datetime.fromisoformat(iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(zone(tz_name))


def _week_label(start: datetime) -> str:
    end = start + timedelta(days=6)
    if start.year == end.year:
        return f"{start.strftime('%b')} {start.day}–{end.day}, {start.year}"
    return f"{start.strftime('%b %d, %Y')} – {end.strftime('%b %d, %Y')}"


def _month_label(start: datetime) -> str:
    return start.strftime("%B %Y")


async def compute_records(bot: Bot) -> ImperiumRecords:
    tz = bot.config.timezone
    rows = await bot.db.active_sale_rows()

    week_totals: dict[datetime, float] = defaultdict(float)
    month_totals: dict[datetime, float] = defaultdict(float)
    user_week: dict[tuple[int, datetime], float] = defaultdict(float)
    user_month: dict[int, dict[datetime, float]] = defaultdict(lambda: defaultdict(float))
    names: dict[int, str] = {}
    all_time_ap = 0.0
    all_time_policies = 0

    parsed: list[tuple[int, str, float, datetime, str]] = []
    for user_id, display_name, amount, created in rows:
        local = _parse_iso(created, tz)
        ws = week_start(tz, local)
        ms = month_start(tz, local)
        week_totals[ws] += amount
        month_totals[ms] += amount
        user_week[(user_id, ws)] += amount
        user_month[user_id][ms] += amount
        names[user_id] = display_name
        all_time_ap += amount
        all_time_policies += 1
        parsed.append((user_id, display_name, amount, local, created))

    # Need sale ids for catalogue — pull recent list
    recent = await bot.db.list_sales(limit=CATALOGUE_LIMIT, include_removed=False)
    # Build week totals lookup already have; catalogue newest first
    catalogue: list[CatalogueEntry] = []
    for sale in recent:
        local = _parse_iso(sale.created_at, tz)
        ws = week_start(tz, local)
        catalogue.append(
            CatalogueEntry(
                when_local=local,
                display_name=sale.display_name or names.get(sale.user_id, str(sale.user_id)),
                amount=sale.amount,
                week_total=user_week.get((sale.user_id, ws), sale.amount),
                sale_id=sale.id,
            )
        )

    cur_week = week_start(tz)
    cur_month = month_start(tz)
    current_week_ap = week_totals.get(cur_week, 0.0)
    current_month_ap = month_totals.get(cur_month, 0.0)

    best_week_start = cur_week
    best_week_ap = current_week_ap
    for ws, ap in week_totals.items():
        if ap > best_week_ap or (ap == best_week_ap and ws < best_week_start):
            best_week_ap, best_week_start = ap, ws

    best_month_start = cur_month
    best_month_ap = current_month_ap
    for ms, ap in month_totals.items():
        if ap > best_month_ap or (ap == best_month_ap and ms < best_month_start):
            best_month_ap, best_month_start = ap, ms

    streak_best = 0
    streak_current = 0
    if week_totals:
        first = min(week_totals)
        cursor = first
        run = 0
        while cursor <= cur_week:
            ap = week_totals.get(cursor, 0.0)
            if ap >= TEN_K:
                run += 1
                streak_best = max(streak_best, run)
            else:
                run = 0
            cursor += timedelta(days=7)
        streak_current = run

    # Best personal week / month ever (single agent)
    personal_week: PeriodRecord | None = None
    for (uid, ws), ap in user_week.items():
        if ap <= 0:
            continue
        if personal_week is None or ap > personal_week.ap:
            personal_week = PeriodRecord(ap, _week_label(ws), names.get(uid, str(uid)))

    personal_month: PeriodRecord | None = None
    for uid, months in user_month.items():
        for ms, ap in months.items():
            if ap <= 0:
                continue
            if personal_month is None or ap > personal_month.ap:
                personal_month = PeriodRecord(
                    ap, _month_label(ms), names.get(uid, str(uid))
                )

    # Current month top 3 producers
    month_rows = [
        (uid, user_month.get(uid, {}).get(cur_month, 0.0))
        for uid in names
    ]
    month_rows = [(uid, ap) for uid, ap in month_rows if ap > 0]
    month_rows.sort(key=lambda x: (-x[1], names.get(x[0], "")))
    month_top3 = [
        PeriodRecord(ap, _month_label(cur_month), names.get(uid, str(uid)))
        for uid, ap in month_rows[:3]
    ]

    return ImperiumRecords(
        all_time_ap=all_time_ap,
        all_time_policies=all_time_policies,
        current_week=PeriodRecord(current_week_ap, _week_label(cur_week)),
        best_week=PeriodRecord(best_week_ap, _week_label(best_week_start)),
        current_month=PeriodRecord(current_month_ap, _month_label(cur_month)),
        best_month=PeriodRecord(best_month_ap, _month_label(best_month_start)),
        ten_k_streak_current=streak_current,
        ten_k_streak_best=streak_best,
        personal_weekly_record=personal_week,
        personal_monthly_record=personal_month,
        month_top3=month_top3,
        catalogue=catalogue,
        catalogue_total=all_time_policies,
        stamp=updated_stamp(tz),
    )


async def _get_text_channel(bot: Bot, channel_id: int) -> discord.TextChannel | None:
    ch = bot.get_channel(channel_id)
    if ch is None:
        try:
            ch = await bot.fetch_channel(channel_id)
        except discord.HTTPException as exc:
            logger.warning("Cannot fetch records channel %s: %s", channel_id, exc)
            return None
    return ch if isinstance(ch, discord.TextChannel) else None


async def _pin(message: discord.Message) -> None:
    try:
        if not message.pinned:
            await message.pin(reason="Imperium private records")
    except discord.HTTPException as exc:
        logger.warning("Could not pin message: %s", exc)


def _match(msg: discord.Message, bot_id: int, hints: tuple[str, ...]) -> bool:
    if msg.author.id != bot_id or not msg.embeds:
        return False
    title = (msg.embeds[0].title or "").upper()
    return any(h in title for h in hints)


async def channel_for(bot: Bot) -> discord.TextChannel | None:
    """
    Records post ONLY to PRIVATE_RECORDS_CHANNEL_ID
    (default #📅private-records📅). No other channel is used.
    """
    channel_id = bot.config.private_records_channel_id
    if channel_id is None:
        return None
    ch = await _get_text_channel(bot, channel_id)
    if ch is None:
        return None
    bot.cached_records_channel_id = ch.id
    await bot.db.set_setting(CH_KEY, str(ch.id))
    return ch


async def _upsert_embed(
    bot: Bot,
    ch: discord.TextChannel,
    embed: discord.Embed,
    cache_attr: str,
    setting_key: str,
    hints: tuple[str, ...],
) -> discord.Message | None:
    msg_id = getattr(bot, cache_attr, None)
    if msg_id is None:
        raw = await bot.db.get_setting(setting_key)
        if raw:
            try:
                msg_id = int(raw)
            except ValueError:
                msg_id = None

    if msg_id is not None:
        try:
            msg = await ch.fetch_message(msg_id)
            await msg.edit(embed=embed)
            await _pin(msg)
            setattr(bot, cache_attr, msg.id)
            await bot.db.set_setting(setting_key, str(msg.id))
            return msg
        except (discord.NotFound, discord.HTTPException) as exc:
            logger.warning("Saved %s message unusable: %s", setting_key, exc)
            setattr(bot, cache_attr, None)
            await bot.db.delete_setting(setting_key)

    if bot.user:
        try:
            async for old in ch.history(limit=50):
                if _match(old, bot.user.id, hints):
                    await old.edit(embed=embed)
                    await _pin(old)
                    setattr(bot, cache_attr, old.id)
                    await bot.db.set_setting(setting_key, str(old.id))
                    return old
        except discord.HTTPException as exc:
            logger.warning("History scan failed: %s", exc)

    try:
        msg = await ch.send(embed=embed)
        await _pin(msg)
        setattr(bot, cache_attr, msg.id)
        await bot.db.set_setting(setting_key, str(msg.id))
        return msg
    except discord.HTTPException as exc:
        logger.error("Post failed: %s", exc)
        return None


async def refresh_records(bot: Bot) -> RecordsResult:
    async with _lock:
        data = await compute_records(bot)
        ch = await channel_for(bot)
        if ch is None:
            return RecordsResult(
                None,
                None,
                "Private records channel not found. Set PRIVATE_RECORDS_CHANNEL_ID "
                "or `/config records_channel`.",
                data,
            )

        summary = records_board(bot.config.brand_name, bot.config.brand_color, data)
        catalogue = sales_catalogue(bot.config.brand_name, bot.config.brand_color, data)

        summary_msg = await _upsert_embed(
            bot, ch, summary, "cached_records_message_id", MSG_KEY, HINTS
        )
        cat_msg = await _upsert_embed(
            bot, ch, catalogue, "cached_catalogue_message_id", CAT_MSG_KEY, CAT_HINTS
        )

        if summary_msg is None and cat_msg is None:
            return RecordsResult(
                None,
                None,
                f"Could not post in {ch.mention}. Need Send Messages, Embed Links, "
                "Read Message History (+ Manage Messages to pin).",
                data,
            )
        return RecordsResult(summary_msg, cat_msg, None, data)
