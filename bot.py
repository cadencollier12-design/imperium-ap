"""Imperium Sales Bot — fresh rewrite. Run: python bot.py"""

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
from utils.board import CH_KEY, MSG_KEY, refresh
from utils.embeds import err

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
COGS = ("cogs.sales", "cogs.leaderboard", "cogs.admin", "cogs.help")


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

    s = await asyncio.start_server(h, "0.0.0.0", port)
    log.info("Health :%s", port)
    return s


class Bot(commands.Bot):
    def __init__(self, config: Config) -> None:
        intents = discord.Intents.default()
        intents.guilds = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents, help_command=None)
        self.config = config
        self.db = Database(config.db_path)
        # Sticky board pointers (survive flaky DB reads within a process)
        self.cached_board_channel_id: int | None = config.leaderboard_channel_id
        self.cached_board_message_id: int | None = None

    async def board_channel_id(self) -> int | None:
        if self.cached_board_channel_id is not None:
            return self.cached_board_channel_id
        raw = await self.db.get_setting(CH_KEY)
        if raw:
            try:
                self.cached_board_channel_id = int(raw)
                return self.cached_board_channel_id
            except ValueError:
                pass
        return self.config.leaderboard_channel_id

    async def setup_hook(self) -> None:
        await self.db.connect()
        # Warm sticky cache from DB
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

        for m in COGS:
            await self.load_extension(m)
            log.info("Loaded %s", m)
        for c in self.tree.get_commands():
            c.default_permissions = None
        if self.config.guild_id:
            g = discord.Object(id=self.config.guild_id)
            self.tree.copy_global_to(guild=g)
            n = await self.tree.sync(guild=g)
            log.info("Synced %d guild commands", len(n))
        else:
            n = await self.tree.sync()
            log.info("Synced %d global commands", len(n))

    async def on_ready(self) -> None:
        assert self.user
        log.info(
            "Online %s · board channel cache=%s · db=%s",
            self.user,
            self.cached_board_channel_id,
            self.config.db_path,
        )
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{self.config.brand_name} Weekly AP",
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

    async def close(self) -> None:
        await self.db.close()
        await super().close()

    async def on_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        log.exception("cmd error: %s", error)
        e = err("Something went wrong.")
        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=e, ephemeral=True)
            else:
                await interaction.response.send_message(embed=e, ephemeral=True)
        except discord.HTTPException:
            pass


async def main() -> None:
    try:
        cfg = load_config()
    except Exception as e:
        log.error("%s", e)
        sys.exit(1)
    srv = await health()
    bot = Bot(cfg)
    try:
        async with bot:
            await bot.start(cfg.token)
    except discord.LoginFailure:
        log.error("Bad DISCORD_TOKEN")
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
