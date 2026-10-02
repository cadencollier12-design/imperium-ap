# Imperium Sales Bot

Brand-new Discord AP tracker with a live **WEEKLY AP** leaderboard.

## Rules

- `/sale` posts **only that sale** (no lifetime on the announce)
- Sales **stay on the board** until `/reset_leaderboard confirm:True`
- **No auto-reset timer**
- **Everyone** can use every command

## Commands

| Command | Action |
|---------|--------|
| `/sale <amount>` | Log a sale + update board |
| `/mysales` | Today / week / month / lifetime |
| `/sales` | History |
| `/remove_sale` | Remove a sale |
| `/leaderboard` | Show board |
| `/refresh_leaderboard` | Refresh board message |
| `/reset_leaderboard confirm:True` | Wipe everyone to $0 |
| `/config leaderboard_channel` | Set board channel |

## Railway (important)

1. Force-push this repo to GitHub.
2. Railway → deploy from Dockerfile.
3. Variables:
   - `DISCORD_TOKEN`
   - `GUILD_ID`
   - `TIMEZONE=America/Los_Angeles` (or `PST`)
   - `DATABASE_PATH=/data/sales.db`
   - `LEADERBOARD_CHANNEL_ID=` *(copy from Discord: right-click board channel → Copy Channel ID)*
4. **Attach a Volume at `/data`** — without this, sales + channel settings wipe on every restart.
5. In Discord: `/config leaderboard_channel:#your-board-channel` once.

## Local

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add token
python bot.py
```
