from __future__ import annotations
import time
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
import redis.asyncio as redis
from app.config import settings
from app.locales import t

_redis: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


class ThrottleMiddleware(BaseMiddleware):
    """Sliding-window rate limit per user using Redis."""

    def __init__(self, max_per_minute: int = settings.RATE_LIMIT_PER_MINUTE) -> None:
        self.max = max_per_minute

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None:
            return await handler(event, data)
        r = get_redis()
        key = f"rl:{user.id}:{int(time.time()) // 60}"
        try:
            cnt = await r.incr(key)
            if cnt == 1:
                await r.expire(key, 65)
        except Exception:
            return await handler(event, data)
        if cnt > self.max:
            lang = data.get("lang", "en")
            msg = t(lang, "rate_limited")
            if isinstance(event, Message):
                await event.answer(msg)
            elif isinstance(event, CallbackQuery):
                await event.answer(msg, show_alert=False)
            return None
        return await handler(event, data)
