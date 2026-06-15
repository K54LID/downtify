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
