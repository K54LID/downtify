from __future__ import annotations
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from app.locales import t
from app.repositories import repo

router = Router(name="history")


@router.message(Command("history"))
async def cmd_history(message: Message, session: AsyncSession, user, lang: str) -> None:
    rows = await repo.recent_downloads(session, user.id, limit=20)
    if not rows:
        await message.answer(t(lang, "history_empty"))
        return
    parts = [t(lang, "history_title"), ""]
    for i, d in enumerate(rows, 1):
        parts.append(t(lang, "history_row",
                       i=i, platform=d.platform,
                       kind=d.kind, title=(d.title or "—")[:60],
                       date=d.created_at.strftime("%Y-%m-%d %H:%M")))
    await message.answer("\n".join(parts), parse_mode="HTML")
