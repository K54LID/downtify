from __future__ import annotations
import asyncio
from aiogram.types import BotCommand, BotCommandScopeChat
from aiohttp import web
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.bot import build_bot, build_dispatcher
from app.utils.logging import setup_logging, log
from app.services.scheduler_jobs import expire_subscriptions


COMMANDS = [
    BotCommand(command="start", description="Start / welcome"),
    BotCommand(command="menu", description="Open the main menu"),
    BotCommand(command="help", description="How to use the bot"),
    BotCommand(command="language", description="Change language"),
    BotCommand(command="subscription", description="Manage subscription"),
    BotCommand(command="donate", description="Donate Telegram Stars to support the bot"),
    BotCommand(command="referral", description="Invite friends & earn Premium"),
    BotCommand(command="spin", description="Spin the daily wheel for rewards"),
    BotCommand(command="legal", description="Legal information"),
]

# Commands shown in addition to the above, only for admin chats.
ADMIN_COMMANDS = COMMANDS + [
    BotCommand(command="leaderboard", description="View leaderboard (admin only)"),
    BotCommand(command="admin", description="Admin dashboard"),
    BotCommand(command="stats", description="Bot statistics"),
    BotCommand(command="users", description="List users"),
    BotCommand(command="user", description="Look up a user"),
    BotCommand(command="grant", description="Grant subscription days"),
    BotCommand(command="revoke", description="Revoke subscription"),
    BotCommand(command="shout", description="Broadcast a message"),
]


async def on_startup(bot) -> None:
    await bot.set_my_commands(COMMANDS)
    for admin_id in settings.admin_ids:
        try:
            await bot.set_my_commands(ADMIN_COMMANDS, scope=BotCommandScopeChat(chat_id=admin_id))
        except Exception:
            pass
    log.info("bot.started", username=settings.BOT_USERNAME)


async def run_polling() -> None:
    bot = build_bot()
    dp = build_dispatcher()
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(expire_subscriptions, "interval", minutes=15)
    scheduler.start()
    await on_startup(bot)
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


async def run_webhook() -> None:
    bot = build_bot()
    dp = build_dispatcher()
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(expire_subscriptions, "interval", minutes=15)
    scheduler.start()
    await on_startup(bot)
    await bot.set_webhook(
        url=settings.WEBHOOK_URL.rstrip("/") + settings.WEBHOOK_PATH,
        secret_token=settings.WEBHOOK_SECRET or None,
        drop_pending_updates=True,
        allowed_updates=dp.resolve_used_update_types(),
    )
    app = web.Application()
    SimpleRequestHandler(
        dispatcher=dp, bot=bot, secret_token=settings.WEBHOOK_SECRET or None
    ).register(app, path=settings.WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    runner = web.AppRunner(app); await runner.setup()
    site = web.TCPSite(runner, settings.WEBAPP_HOST, settings.WEBAPP_PORT)
    await site.start()
    log.info("webhook.listening", host=settings.WEBAPP_HOST, port=settings.WEBAPP_PORT)
    try:
        await asyncio.Event().wait()
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


def main() -> None:
    setup_logging()
    if settings.WEBHOOK_URL:
        asyncio.run(run_webhook())
    else:
        asyncio.run(run_polling())


if __name__ == "__main__":
    main()
