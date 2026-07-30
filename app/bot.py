from __future__ import annotations
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.telegram import TelegramAPIServer
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
import redis.asyncio as redis
from app.config import settings
from app.middleware.db import DbSessionMiddleware, UserMiddleware
from app.middleware.throttle import ThrottleMiddleware
from app.handlers import common as h_common
from app.handlers import subscription as h_sub
from app.handlers import referral as h_referral
from app.handlers import donate as h_donate
from app.handlers import downloads as h_downloads
from app.handlers import spin as h_spin
from app.handlers import leaderboard as h_leaderboard
from app.handlers import menu as h_menu
from app.admin import handlers as h_admin


def build_bot() -> Bot:
    if settings.TELEGRAM_API_ROOT:
        session = AiohttpSession(
            api=TelegramAPIServer.from_base(settings.TELEGRAM_API_ROOT, is_local=True)
        )
    else:
        session = None

    return Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        session=session,
    )


def build_dispatcher() -> Dispatcher:
    storage = RedisStorage(redis=redis.from_url(settings.redis_url))
    dp = Dispatcher(storage=storage)

    dp.update.outer_middleware(DbSessionMiddleware())
    dp.update.outer_middleware(UserMiddleware())
    dp.update.outer_middleware(ThrottleMiddleware())

    dp.include_router(h_common.router)
    dp.include_router(h_sub.router)
    dp.include_router(h_referral.router)
    dp.include_router(h_donate.router)
    dp.include_router(h_spin.router)
    dp.include_router(h_leaderboard.router)
    dp.include_router(h_admin.router)
    dp.include_router(h_menu.router)
    dp.include_router(h_downloads.router)
    return dp
