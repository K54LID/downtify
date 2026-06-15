<<<<<<< HEAD
# Downtify Bot

A production-ready multilingual Telegram bot for downloading TikTok, Instagram, YouTube media and searching music. Subscription-based using Telegram Stars.

## Features

- 🌍 Multilingual (English, Russian, Turkish, Arabic)
- 📹 TikTok video/audio downloads
- 📸 Instagram Reels / Posts / Videos
- 🎬 YouTube video/audio downloads with quality selection
- 🎵 Music search (YouTube Music backend via yt-dlp)
- ⭐ Telegram Stars subscriptions ($2/month equivalent)
- 🤝 Referral program (invite via deep links, earn Premium for both sides)
- 🎡 Daily spin wheel rewards
- 🛡️ Admin dashboard with analytics, broadcasts, grants
- 🗄️ PostgreSQL + SQLAlchemy + Alembic migrations
- ⚡ Redis-backed rate limiting and FSM storage
- 🐳 Docker + Docker Compose + Nginx ready

## Quick Start (Docker)

```bash
cp .env.example .env
# edit .env with BOT_TOKEN, ADMIN_IDS, etc.
docker compose up -d --build
docker compose exec bot alembic upgrade head
```

See `deploy/UBUNTU_VPS_GUIDE.md` for a full VPS walkthrough.

## Local development

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
python -m app.main
```

## Project layout

```
app/
  main.py                # entrypoint
  config.py              # pydantic settings
  bot.py                 # bot + dispatcher factory
  handlers/              # message/callback handlers
  services/              # business logic
  database/              # engine + models
  repositories/          # data access
  middleware/            # i18n, throttle, db session, subscription
  locales/               # JSON translations
  admin/                 # admin commands & dashboard
  payments/              # Telegram Stars
  downloads/             # yt-dlp wrappers
  keyboards/             # inline keyboards
  utils/                 # helpers, logging
```

## Commands

User: `/start /help /language /subscription /donate /legal`
Referrals: `/referral`
Spin: `/spin`
Admin: `/admin /users /user <id> /grant <id> <days> /revoke <id> /shout /stats /leaderboard`

## Referral program

- Each user gets a unique referral code via `/referral`, exposed as a deep link:
  `https://t.me/<bot_username>?start=ref_<CODE>`
- New users who open the bot via that link are linked to the referrer (one-time only;
  self-referrals and double-referrals are rejected).
- When the referred user completes their **first successful download**, both the
  referrer and the referred user are granted Premium days
  (`REFERRAL_REWARD_DAYS` and `REFERRAL_BONUS_DAYS` in config).

## Testing

```bash
pip install -r requirements.txt
pytest
```

Tests use an in-memory SQLite database and cover the referral repository
logic, including anti-abuse edge cases (self-referral, double referral).

## License

Provided as-is for the requester.
=======
# telegram-ytdl

#### A simple & fast YouTube download Telegram bot.

[![Telegram Bot](https://img.shields.io/badge/TELEGRAM-BOT-%2330A3E6?style=for-the-badge&logo=telegram)](https://t.me/Downtify_Bot)

## Synopsis

meow

I was never satisfied with any YouTube downloader solution, because they either required chasing some website that was
either bloated with ads, painfully slow, taken down the next day or all of those combined.
Using [yt-dlp][yt-dlp] in the command line was my go-to,
but doesn't really work great on mobile.

**So I made this bot, to download from a single place across platforms, fast and effortless.**

The bot then simply passes the URL to [yt-dlp][yt-dlp] with the `-f b` flag, which downloads the best quality
format that contains both video and audio. This is meant to work together with a self-hosted
Telegram bot API server, so that the upload limit for bots is increased from 50MB to 2GB.

Because content sites change often (especially TikTok!), the bot uses the nightly build of yt-dlp to
always get the latest resolvers. It will also auto-update yt-dlp every night as long as you don't
set `YTDL_AUTOUPDATE` to `"false"`.

The instance hosted by me is no longer available for public use, but you can simply host your own instance.

## Hosting

To host your own instance of this bot, you need to have a Telegram bot token, Telegram API Token
and a server to run the bot on. You can create a Telegram bot with [BotFather][botfather] and purchase
a cheap VPS with the hoster of your choice.



### Installation

- [Install Docker](https://docs.docker.com/engine/install)
- Create a folder and put the [compose.yml](./compose.yml) into it.
- Fill out and adjust the following variables in the docker-compose.yml file:

  | Variable                | Description                                                                                                                                    |
  | ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
  | `TELEGRAM_BOT_TOKEN`    | Your Telegram bot token (get it from [BotFather][botfather])                                                                                   |
  | `WHITELISTED_IDS`       | A comma-separated list of Telegram user IDs that are allowed to use the bot (get them from [this bot][id-bot]), leave empty to allow all users |
  | `ADMIN_ID`              | Your Telegram user ID (get it from [this bot][id-bot])                                                                                         |
  | `TELEGRAM_API_ID`       | Your Telegram API ID (get it [here][telegram-api-id])                                                                                          |
  | `TELEGRAM_API_HASH`     | Your Telegram API hash (get it [here][telegram-api-id])                                                                                        |
  | `TELEGRAM_API_ROOT`     | The URL of your Telegram bot API server (can probably be left unchanged)                                                                       |
  | `TELEGRAM_WEBHOOK_PORT` | The port the bot will listen on (can probably be left unchanged)                                                                               |
  | `TELEGRAM_WEBHOOK_URL`  | The URL of your Telegram bot API server (can probably be left unchanged)                                                                       |
  | `YTDL_AUTOUPDATE`       | Whether to automatically update yt-dlp (defaults to `"true"`, set to `"false"` to disable)                                                     |
  | `OPENAI_API_KEY`        | Your OpenAI API key (optional, used for auto-translation)                                                                                      |

- Run `docker compose up -d` in the folder you created.

If you have any problems with hosting feel free to contact me or open an issue.

[yt-dlp]: https://github.com/yt-dlp/yt-dlp
[telegram-api-id]: https://core.telegram.org/api/obtaining_api_id
[id-bot]: https://t.me/getidsbot
[botfather]: https://t.me/BotFather
[hetzner]: https://hetzner.cloud/?ref=e5ntAQJVvxX1
>>>>>>> 999c38a6195443ce89a56c989d6c53043a079d41
