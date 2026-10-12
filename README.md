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
| `/config leaderboard_channel` | Public weekly board channel |
| `/records` | **Admin only** — refresh private records (does not post numbers in public) |
| `/commands` | Help |

### Who can use `/records`
Only Discord user IDs listed in `RECORDS_ADMIN_USER_IDS`. Everyone else is denied.

Records / catalogue messages are posted **only** in `PRIVATE_RECORDS_CHANNEL_ID` (`#📅private-records📅`). They are never sent to the public leaderboard channel.

## Private records (`#📅private-records📅`)

Two pinned messages for leadership (keep the channel private — Tobe + bot):

**Records summary**
- All-time AP sold + all-time policies sold  
- Current week / best week of AP  
- Current month / best month  
- Most $10K weeks in a row (current + record)  
- Top **Sale Trainer** this month + biggest Sale Trainer month ever  
- Top **(MGA)** this month + biggest MGA month ever  

**Sale catalogue**
- Every sale with date + time, agent, amount, and that agent’s week total  
- Newest sales shown in the embed; full history via `/sales`  

Role stats use only **Sale Trainer** and **(MGA)**. Updates on every `/sale`.

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
GUILD_ID=1552050961696948224
LEADERBOARD_CHANNEL_ID=1554506265726820402
PRIVATE_RECORDS_CHANNEL_ID=1558994164639866980
RECORDS_ADMIN_USER_IDS=1456116798175969301
TIMEZONE=America/Los_Angeles
DATABASE_PATH=/data/sales.db
BRAND_NAME=Imperium
```

`RECORDS_ADMIN_USER_IDS` = your Discord user ID (Developer Mode → right-click your name → Copy User ID).

4. **Volume mounted at `/data` (REQUIRED)**  
   Without this, every redeploy starts a brand-new empty database and it looks like the bot “wiped” sales.  
   The Sunday leaderboard does **not** delete sales — it only changes which week the public board displays.
5. Set `DATABASE_PATH=/data/sales.db`  
6. Deploy → logs should show `Online ...` and `Active sales in database: N` (not 0 if you have history)  
7. In Discord: `/config leaderboard_channel:#your-board`  
8. Run only **one** instance (don’t also run it on your PC)

### Restore wiped sales
If a deploy lost history, use (records admin only):

```
/backfill_sale agent:@Name amount:2112 when_local:10/6/26 8:49am
/backup_sales
```

## Local

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # paste new bot token + IDs
python bot.py
```
