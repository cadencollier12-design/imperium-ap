"""Imperium Sales Bot — weekly leaderboard + lifetime stats. Run: python bot.py"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from config import Config, load_config
from database import Database
from utils.board import CH_KEY, MSG_KEY, WEEK_KEY, refresh
from utils.embeds import err
from utils.helpers import utc_iso, week_start
from utils.records import (
    CAT_MSG_KEY as RECORDS_CAT_MSG_KEY,
    CH_KEY as RECORDS_CH_KEY,
    MSG_KEY as RECORDS_MSG_KEY,
    refresh_records,
)
from utils.wall import (
    CH_KEY as WALL_CH_KEY,
    MSG_KEY as WALL_MSG_KEY,
    refresh_record_wall,
)

LOG = Path(__file__).resolve().parent / "logs"
LOG.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG / "imperium.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("imperium")
COGS = ("cogs.sales", "cogs.leaderboard", "cogs.admin", "cogs.help", "cogs.records")


async def health() -> asyncio.AbstractServer | None:
    raw = os.getenv("PORT")
    if not raw:
        return None
    try:
        port = int(raw)
    except ValueError:
        return None

    async def h(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            await reader.read(1024)
            writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok")
            await writer.drain()
        finally:
            writer.close()

    server = await asyncio.start_server(h, "0.0.0.0", port)
    log.info("Health :%s", port)
    return server


class Bot(commands.Bot):
    def __init__(self, config: Config) -> None:
        intents = discord.Intents.default()
        intents.guilds = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents, help_command=None)
        self.config = config
        self.db = Database(config.db_path)
        self.cached_board_channel_id: int | None = config.leaderboard_channel_id
        self.cached_board_message_id: int | None = None
        self.cached_records_channel_id: int | None = config.private_records_channel_id
        self.cached_records_message_id: int | None = None
        self.cached_catalogue_message_id: int | None = None
        self.cached_wall_channel_id: int | None = config.record_wall_channel_id
        self.cached_wall_message_id: int | None = None

    async def setup_hook(self) -> None:
        await self.db.connect()

        raw_ch = await self.db.get_setting(CH_KEY)
        raw_msg = await self.db.get_setting(MSG_KEY)
        if raw_ch:
            try:
                self.cached_board_channel_id = int(raw_ch)
            except ValueError:
                pass
        if raw_msg:
            try:
                self.cached_board_message_id = int(raw_msg)
            except ValueError:
                pass
        if self.cached_board_channel_id is None:
            self.cached_board_channel_id = self.config.leaderboard_channel_id

        raw_rch = await self.db.get_setting(RECORDS_CH_KEY)
        raw_rmsg = await self.db.get_setting(RECORDS_MSG_KEY)
        raw_rcat = await self.db.get_setting(RECORDS_CAT_MSG_KEY)
        if raw_rch:
            try:
                self.cached_records_channel_id = int(raw_rch)
            except ValueError:
                pass
        if raw_rmsg:
            try:
                self.cached_records_message_id = int(raw_rmsg)
            except ValueError:
                pass
        if raw_rcat:
            try:
                self.cached_catalogue_message_id = int(raw_rcat)
            except ValueError:
                pass
        if self.cached_records_channel_id is None:
            self.cached_records_channel_id = self.config.private_records_channel_id

        raw_wch = await self.db.get_setting(WALL_CH_KEY)
        raw_wmsg = await self.db.get_setting(WALL_MSG_KEY)
        if raw_wch:
            try:
                self.cached_wall_channel_id = int(raw_wch)
            except ValueError:
                pass
        if raw_wmsg:
            try:
                self.cached_wall_message_id = int(raw_wmsg)
            except ValueError:
                pass
        if self.cached_wall_channel_id is None:
            self.cached_wall_channel_id = self.config.record_wall_channel_id

        # Seed week pointer so first boot doesn't fake a Sunday reset
        current_week = utc_iso(week_start(self.config.timezone))
        if await self.db.get_setting(WEEK_KEY) is None:
            await self.db.set_setting(WEEK_KEY, current_week)

        for module in COGS:
            await self.load_extension(module)
            log.info("Loaded %s", module)

        for cmd in self.tree.get_commands():
            cmd.default_permissions = None

        if self.config.guild_id:
            guild = discord.Object(id=self.config.guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            log.info("Synced %d guild commands", len(synced))
        else:
            synced = await self.tree.sync()
            log.info("Synced %d global commands", len(synced))

    async def on_ready(self) -> None:
        assert self.user
        log.info(
            "Online %s · board=%s · records=%s · records_admins=%s · tz=%s · week_start=%s · db=%s",
            self.user,
            self.cached_board_channel_id,
            self.cached_records_channel_id,
            list(self.config.records_admin_ids) or "NONE — /records locked",
            self.config.timezone,
            week_start(self.config.timezone).isoformat(),
            self.config.db_path,
        )
        if not self.config.records_admin_ids:
            log.warning(
                "RECORDS_ADMIN_USER_IDS is empty — nobody can run /records until you set it."
            )
        try:
            n = await self.db.count_active_sales()
            log.info("Active sales in database: %d", n)
            if n == 0:
                log.error(
                    "DATABASE HAS 0 SALES. If you expected history, Railway is missing a "
                    "persistent Volume at /data (or DATABASE_PATH is wrong). "
                    "Redeploys without /data create an empty DB and look like a wipe. "
                    "Sales are NEVER deleted by the Sunday board rollover."
                )
        except Exception:
            log.exception("Could not count sales")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{self.config.brand_name} weekly board",
            )
        )
        try:
            result = await refresh(self)
            if result.message:
                log.info(
                    "Board ready in #%s (message %s)",
                    getattr(result.message.channel, "name", "?"),
                    result.message.id,
                )
            else:
                log.warning("No board yet: %s", result.error)
        except Exception:
            log.exception("startup board")
        try:
            rec = await refresh_records(self)
            if rec.message:
                log.info(
                    "Records ready in #%s (message %s)",
                    getattr(rec.message.channel, "name", "?"),
                    rec.message.id,
                )
            else:
                log.warning("No records board yet: %s", rec.error)
        except Exception:
            log.exception("startup records")
        try:
            wall = await refresh_record_wall(self)
            if wall.message:
                log.info(
                    "Record wall ready in #%s (message %s)",
                    getattr(wall.message.channel, "name", "?"),
                    wall.message.id,
                )
            else:
                log.warning("No record wall yet: %s", wall.error)
        except Exception:
            log.exception("startup record wall")

    async def close(self) -> None:
        await self.db.close()
        await super().close()

    async def on_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        root = error.__cause__ or error
        if isinstance(root, discord.NotFound) and getattr(root, "code", None) == 10062:
            log.error(
                "Unknown interaction (10062). Another process is using this bot token. "
                "Keep only one instance (Railway OR local — not both)."
            )
            return
        log.exception("cmd error: %s", error)
        embed = err("Something went wrong. Try that command again.")
        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.HTTPException:
            pass


async def main() -> None:
    try:
        cfg = load_config()
    except Exception as exc:
        log.error("%s", exc)
        sys.exit(1)

    srv = await health()
    bot = Bot(cfg)
    try:
        async with bot:
            await bot.start(cfg.token)
    except discord.LoginFailure:
        log.error("Bad DISCORD_TOKEN — reset the token in the Discord Developer Portal.")
        sys.exit(1)
    finally:
        if srv:
            srv.close()
            await srv.wait_closed()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
