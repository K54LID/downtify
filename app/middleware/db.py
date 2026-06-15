from __future__ import annotations
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update, Message, CallbackQuery, User as TgUser
from app.database import SessionLocal
from app.repositories import repo


class DbSessionMiddleware(BaseMiddleware):
    """Open a SQLAlchemy session for the lifetime of one update."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        async with SessionLocal() as session:
            data["session"] = session
            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise


class UserMiddleware(BaseMiddleware):
    """Ensure a User row exists and inject `user` + `lang` into handler data."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        tg_user: TgUser | None = data.get("event_from_user")
        session = data.get("session")
        if tg_user and session is not None:
            user = await repo.get_or_create_user(
                session,
                tg_id=tg_user.id,
                username=tg_user.username,
                first_name=tg_user.first_name,
                last_name=tg_user.last_name,
                language=(tg_user.language_code[:2] if tg_user.language_code else None),
            )
            data["user"] = user
            data["lang"] = user.language or "en"
        else:
            data["user"] = None
            data["lang"] = "en"
        return await handler(event, data)
