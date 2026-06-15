from __future__ import annotations
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from app.locales import t
from app.config import settings
from app.repositories import repo
from app.keyboards.keyboards import referral_kb

router = Router(name="referral")


@router.message(Command("referral"))
async def cmd_referral(message: Message, session: AsyncSession, user, lang: str) -> None:
    code = await repo.get_or_create_referral_code(session, user.id)
    link = f"https://t.me/{settings.BOT_USERNAME}?start=ref_{code}"

    count = await repo.count_referrals(session, user.id)
    rewarded = await repo.count_rewarded_referrals(session, user.id)

    body = t(
        lang, "referral_body",
        reward=settings.REFERRAL_REWARD_DAYS,
        link=link, code=code, count=count, rewarded=rewarded,
    )
    await message.answer(
        f"{t(lang, 'referral_title')}\n\n{body}",
        parse_mode="HTML",
        reply_markup=referral_kb(lang, link),
    )
