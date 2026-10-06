# Imperium Sales Bot

A clean Discord sales tracker:

1. **`/sale <amount>`** — log a sale (credits the person who posts it)
2. **Weekly leaderboard** — live channel board, **resets every Sunday at 12:00 AM**
3. **`/mysales`** — today / week / month / **lifetime forever**

Everyone can use every command. Lifetime is never wiped by the Sunday reset.

## Commands

| Command | What it does |
|---------|----------------|
| `/sale 2112` | Log a sale for **you**, update the board |
| `/mysales` | Your stats (lifetime is permanent) |
| `/leaderboard` | This week's rankings |
| `/sales` | Recent sales history |
| `/remove_sale` | Undo a bad entry |
| `/refresh_leaderboard` | Force-refresh the live board |
| `/config leaderboard_channel` | Pick the board channel |
| `/commands` | Help |

## Week rules

- Week runs **Sunday 12:00 AM → next Sunday** in `TIMEZONE` (default `America/Los_Angeles`)
- At Sunday midnight the live board clears and a short “new week” notice posts
- `/mysales` lifetime totals keep every sale forever

## Discord setup

1. [Discord Developer Portal](https://discord.com/developers/applications) → New Application → Bot → copy token  
2. Enable **Server Members Intent**  
3. Invite with scopes `bot` + `applications.commands`  
4. Permissions: View Channels, Send Messages, Embed Links, Read Message History  
5. Copy Server ID → `GUILD_ID`  
6. Copy board channel ID → `LEADERBOARD_CHANNEL_ID`

## Railway (24/7 hosting)

1. Push this repo to GitHub  
2. New Railway project from that repo (Dockerfile)  
3. Variables:

```
DISCORD_TOKEN=...
GUILD_ID=...
LEADERBOARD_CHANNEL_ID=...
TIMEZONE=America/Los_Angeles
DATABASE_PATH=/data/sales.db
BRAND_NAME=Imperium
```

4. **Volume** mounted at `/data` (required — otherwise stats wipe on restart)  
5. Deploy → logs should show `Online ...`  
6. In Discord once: `/config leaderboard_channel:#your-board`  
7. Run only **one** instance (don’t also run it on your PC)

## Local

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # paste new bot token + IDs
python bot.py
```
