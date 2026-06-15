from __future__ import annotations
from aiogram import Router, F
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from app.locales import t
from app.config import settings
from app.keyboards.keyboards import language_kb, subscribe_kb
from app.repositories import repo
from app.services.subscription import is_subscribed, days_remaining, premium_badge

router = Router(name="common")


async def _send_welcome(message: Message, session: AsyncSession, user, lang: str) -> None:
    """Send the welcome message with inline usage reminder / premium status."""
    subscribed = await is_subscribed(session, user)
    badge = premium_badge(subscribed)

    # Title line — prefix with ⭐ for premium members
    title = f"{badge}{t(lang, 'welcome_title').lstrip('👋 ')}"
    await message.answer(f"{'⭐' if subscribed else '👋'} {title}", parse_mode="HTML")

    if subscribed:
        days = await days_remaining(session, user)
        await message.answer(t(lang, "welcome_premium"), parse_mode="HTML")
    else:
        remaining = await repo.get_daily_uses_remaining(session, user.id, settings.DAILY_FREE_USES)
        if remaining == 0:
            body = t(lang, "welcome_free_zero")
            await message.answer(body, parse_mode="HTML",
                                 reply_markup=subscribe_kb(lang, settings.SUBSCRIPTION_STARS))
        elif remaining == 1:
            await message.answer(t(lang, "welcome_free_one"), parse_mode="HTML")
        else:
            await message.answer(
                t(lang, "welcome_free_plural", count=remaining), parse_mode="HTML"
            )


@router.message(CommandStart(deep_link=True))
async def cmd_start_deep_link(
    message: Message, command: CommandObject, session: AsyncSession, user, lang: str
) -> None:
    payload = (command.args or "").strip()
    is_new_user = bool(user) and user.created_at == user.last_seen_at

    if payload.startswith("ref_"):
        code = payload[len("ref_"):]
        referrer = await repo.get_user_by_referral_code(session, code)
        if referrer is None:
            await repo.log_audit(session, user.id if user else None, "referral_invalid", code)
        elif user is not None:
            ref = await repo.link_referral(
                session, referred_user=user, referrer=referrer,
                reward_days=settings.REFERRAL_REWARD_DAYS,
            )
            if ref is not None:
                await repo.log_audit(session, user.id, "referral_linked", code)
                if is_new_user:
                    await message.answer(t(lang, "referral_applied"), parse_mode="HTML")
            elif user.referred_by_id is not None:
                await message.answer(t(lang, "referral_already_referred"), parse_mode="HTML")
            elif referrer.id == user.id:
                await message.answer(t(lang, "referral_self"), parse_mode="HTML")

    await cmd_start(message, session, user, lang)


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, user, lang: str) -> None:
    # First-time users: only show language selector — nothing else.
    if not user or user.created_at == user.last_seen_at:
        await message.answer(
            t("en", "choose_language") + "\n" +
            t("ru", "choose_language") + "\n" +
            t("tr", "choose_language") + "\n" +
            t("ar", "choose_language"),
            reply_markup=language_kb(),
        )
        return
    await _send_welcome(message, session, user, lang)

    # Make every feature reachable via the persistent menu keyboard.
    from app.handlers.menu import send_main_menu
    from app.admin.handlers import is_admin
    await send_main_menu(message, lang, admin=is_admin(message.from_user.id))


@router.message(Command("help"))
async def cmd_help(message: Message, lang: str) -> None:
    await message.answer(t(lang, "help"), parse_mode="HTML")


@router.message(Command("legal"))
async def cmd_legal(message: Message, lang: str) -> None:
    await message.answer(t(lang, "legal"), parse_mode="HTML")


@router.message(Command("language"))
async def cmd_language(message: Message, lang: str) -> None:
    await message.answer(t(lang, "language_prompt"), reply_markup=language_kb())


@router.callback_query(F.data.startswith("lang:"))
async def cb_language(cb: CallbackQuery, session: AsyncSession, user) -> None:
    code = cb.data.split(":", 1)[1]
    if code not in ("en", "ru", "tr", "ar"):
        await cb.answer()
        return
    if user:
        await repo.set_language(session, user.id, code)
    await cb.message.edit_text(t(code, "language_set"))
    await _send_welcome(cb.message, session, user, lang=code)

    from app.handlers.menu import send_main_menu
    from app.admin.handlers import is_admin
    await send_main_menu(cb.message, code, admin=is_admin(cb.from_user.id))

    await cb.answer()
