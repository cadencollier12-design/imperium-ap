"""SQLite storage — sales are kept forever; weekly board is a time window."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import aiosqlite

from utils.helpers import utc_iso

logger = logging.getLogger(__name__)


@dataclass
class Sale:
    id: int
    user_id: int
    amount: float
    created_at: str
    removed: int
    display_name: str | None = None


@dataclass
class Stats:
    ap: float
    policies: int


@dataclass
class AgentStats:
    user_id: int
    display_name: str
    today: Stats
    week: Stats
    month: Stats
    lifetime: Stats


@dataclass
class Rank:
    rank: int
    user_id: int
    display_name: str
    ap: float
    policies: int


class Database:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._conn: aiosqlite.Connection | None = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("DB not connected")
        return self._conn

    async def connect(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self.conn.execute("PRAGMA foreign_keys = ON")
        await self.conn.execute("PRAGMA journal_mode = DELETE")
        await self.conn.execute("PRAGMA busy_timeout = 5000")
        await self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS agents (
                user_id INTEGER PRIMARY KEY,
                display_name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL CHECK(amount > 0),
                created_at TEXT NOT NULL,
                removed INTEGER NOT NULL DEFAULT 0,
                removed_at TEXT,
                removed_by INTEGER,
                FOREIGN KEY (user_id) REFERENCES agents(user_id)
            );
            CREATE INDEX IF NOT EXISTS idx_sales_active
                ON sales(removed, created_at);
            CREATE INDEX IF NOT EXISTS idx_sales_user
                ON sales(user_id, removed, created_at);
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        await self.conn.commit()
        logger.info("DB ready: %s", self.path)

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def get_setting(self, key: str) -> str | None:
        async with self.conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ) as cur:
            row = await cur.fetchone()
        return str(row["value"]) if row else None

    async def set_setting(self, key: str, value: str) -> None:
        await self.conn.execute(
            """
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
        await self.conn.commit()

    async def delete_setting(self, key: str) -> None:
        await self.conn.execute("DELETE FROM settings WHERE key = ?", (key,))
        await self.conn.commit()

    async def upsert_agent(self, user_id: int, display_name: str, now: datetime) -> None:
        ts = utc_iso(now)
        await self.conn.execute(
            """
            INSERT INTO agents (user_id, display_name, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                display_name = excluded.display_name,
                updated_at = excluded.updated_at
            """,
            (user_id, display_name, ts, ts),
        )

    async def add_sale(
        self, user_id: int, display_name: str, amount: float, now: datetime
    ) -> Sale:
        await self.upsert_agent(user_id, display_name, now)
        ts = utc_iso(now)
        cur = await self.conn.execute(
            "INSERT INTO sales (user_id, amount, created_at, removed) VALUES (?, ?, ?, 0)",
            (user_id, float(amount), ts),
        )
        await self.conn.commit()
        assert cur.lastrowid is not None
        return Sale(cur.lastrowid, user_id, float(amount), ts, 0, display_name)

    async def find_duplicate(
        self, user_id: int, amount: float, since: datetime
    ) -> Sale | None:
        async with self.conn.execute(
            """
            SELECT id, user_id, amount, created_at, removed FROM sales
            WHERE user_id = ? AND amount = ? AND removed = 0 AND created_at >= ?
            ORDER BY created_at DESC LIMIT 1
            """,
            (user_id, float(amount), utc_iso(since)),
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return None
        return Sale(
            int(row["id"]),
            int(row["user_id"]),
            float(row["amount"]),
            row["created_at"],
            int(row["removed"]),
        )

    def _sale_from_row(self, row: aiosqlite.Row) -> Sale:
        return Sale(
            int(row["id"]),
            int(row["user_id"]),
            float(row["amount"]),
            row["created_at"],
            int(row["removed"]),
            row["display_name"] if "display_name" in row.keys() else None,
        )

    async def get_sale(self, sale_id: int) -> Sale | None:
        async with self.conn.execute(
            """
            SELECT s.id, s.user_id, s.amount, s.created_at, s.removed, a.display_name
            FROM sales s JOIN agents a ON a.user_id = s.user_id
            WHERE s.id = ?
            """,
            (sale_id,),
        ) as cur:
            row = await cur.fetchone()
        return self._sale_from_row(row) if row else None

    async def remove_sale(self, sale_id: int, by: int, now: datetime) -> Sale | None:
        sale = await self.get_sale(sale_id)
        if sale is None or sale.removed:
            return None
        await self.conn.execute(
            """
            UPDATE sales
            SET removed = 1, removed_at = ?, removed_by = ?
            WHERE id = ? AND removed = 0
            """,
            (utc_iso(now), by, sale_id),
        )
        await self.conn.commit()
        return await self.get_sale(sale_id)

    async def find_by_amount(self, user_id: int, amount: float) -> Sale | None:
        async with self.conn.execute(
            """
            SELECT s.id, s.user_id, s.amount, s.created_at, s.removed, a.display_name
            FROM sales s JOIN agents a ON a.user_id = s.user_id
            WHERE s.user_id = ? AND s.amount = ? AND s.removed = 0
            ORDER BY s.created_at DESC LIMIT 1
            """,
            (user_id, float(amount)),
        ) as cur:
            row = await cur.fetchone()
        return self._sale_from_row(row) if row else None

    async def list_sales(
        self,
        user_id: int | None = None,
        limit: int = 15,
        include_removed: bool = False,
    ) -> list[Sale]:
        where = ["1=1"]
        params: list[Any] = []
        if user_id is not None:
            where.append("s.user_id = ?")
            params.append(user_id)
        if not include_removed:
            where.append("s.removed = 0")
        params.append(limit)
        async with self.conn.execute(
            f"""
            SELECT s.id, s.user_id, s.amount, s.created_at, s.removed, a.display_name
            FROM sales s JOIN agents a ON a.user_id = s.user_id
            WHERE {" AND ".join(where)}
            ORDER BY s.created_at DESC
            LIMIT ?
            """,
            params,
        ) as cur:
            rows = await cur.fetchall()
        return [self._sale_from_row(r) for r in rows]

    async def _sum(self, user_id: int | None, start: datetime | None) -> Stats:
        where = ["removed = 0"]
        params: list[Any] = []
        if user_id is not None:
            where.append("user_id = ?")
            params.append(user_id)
        if start is not None:
            where.append("created_at >= ?")
            params.append(utc_iso(start))
        async with self.conn.execute(
            f"""
            SELECT COALESCE(SUM(amount), 0) ap, COUNT(id) n
            FROM sales
            WHERE {" AND ".join(where)}
            """,
            params,
        ) as cur:
            row = await cur.fetchone()
        return Stats(float(row["ap"]), int(row["n"]))

    async def agent_stats(
        self,
        user_id: int,
        display_name: str,
        day: datetime,
        week: datetime,
        month: datetime,
    ) -> AgentStats:
        async with self.conn.execute(
            "SELECT display_name FROM agents WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
        name = row["display_name"] if row else display_name
        return AgentStats(
            user_id,
            name,
            await self._sum(user_id, day),
            await self._sum(user_id, week),
            await self._sum(user_id, month),
            await self._sum(user_id, None),
        )

    async def leaderboard(
        self, since: datetime, limit: int = 50
    ) -> tuple[list[Rank], Stats]:
        """Weekly board: only sales since Sunday week start. Lifetime is untouched."""
        async with self.conn.execute(
            """
            SELECT s.user_id, a.display_name,
                   COALESCE(SUM(s.amount), 0) ap, COUNT(s.id) n
            FROM sales s
            JOIN agents a ON a.user_id = s.user_id
            WHERE s.removed = 0 AND s.created_at >= ?
            GROUP BY s.user_id
            HAVING ap > 0
            ORDER BY ap DESC, n DESC, a.display_name ASC
            LIMIT ?
            """,
            (utc_iso(since), limit),
        ) as cur:
            rows = await cur.fetchall()
        ranks = [
            Rank(
                i + 1,
                int(r["user_id"]),
                r["display_name"],
                float(r["ap"]),
                int(r["n"]),
            )
            for i, r in enumerate(rows)
        ]
        return ranks, await self._sum(None, since)
