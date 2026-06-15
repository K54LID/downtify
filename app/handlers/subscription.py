from __future__ import annotations
from datetime import datetime, timezone
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, PreCheckoutQuery
from sqlalchemy.ext.asyncio import AsyncSession
from app.locales import t
from app.config import settings
from app.repositories import repo
from app.keyboards.keyboards import subscribe_kb, renew_kb
from app.payments.stars import send_subscription_invoice, SUB_PAYLOAD_PREFIX, DONATE_PAYLOAD_PREFIX
from app.services.subscription import days_remaining, is_subscribed

router = Router(name="subscription")


@router.message(Command("subscription"))
async def cmd_subscription(message: Message, session: AsyncSession, user, lang: str) -> None:
    sub = await repo.active_subscription(session, user.id)
    if sub:
        days = max(0, (sub.expires_at - datetime.now(timezone.utc)).days)
        # Use the badged active string which includes the ⭐ Premium Member header
        body = t(lang, "subscription_active_badge",
                 date=sub.expires_at.strftime("%Y-%m-%d"), days=days)
        await message.answer(body, parse_mode="HTML", reply_markup=renew_kb(lang))
    else:
        from app.repositories import repo as _repo
        remaining = await _repo.get_daily_uses_remaining(session, user.id, settings.DAILY_FREE_USES)
        if remaining == 1:
            uses_line = t(lang, "free_uses_remaining_one")
        elif remaining > 1:
            uses_line = t(lang, "free_uses_remaining_plural", count=remaining)
        else:
            uses_line = ""

        inactive_text = t(lang, "subscription_inactive")
        body = f"{t(lang, 'subscription_title')}\n\n{inactive_text}"
        if uses_line:
            body += f"\n\n{uses_line}"
        await message.answer(body, parse_mode="HTML",
                             reply_markup=subscribe_kb(lang, settings.SUBSCRIPTION_STARS))


@router.callback_query(F.data == "sub:buy")
async def cb_subscribe(cb: CallbackQuery, user, lang: str) -> None:
    await send_subscription_invoice(cb.bot, cb.message.chat.id, user.id, lang)
    await cb.answer()


@router.pre_checkout_query()
async def pre_checkout(pcq: PreCheckoutQuery) -> None:
    await pcq.bot.answer_pre_checkout_query(pcq.id, ok=True)


@router.message(F.successful_payment)
async def on_successful_payment(message: Message, session: AsyncSession, user, lang: str) -> None:
    sp = message.successful_payment
    charge_id = sp.telegram_payment_charge_id or sp.provider_payment_charge_id or "n/a"
    payload = sp.invoice_payload or ""
    await repo.add_payment(session, user.id, charge_id, sp.total_amount, payload)

    if payload.startswith(DONATE_PAYLOAD_PREFIX):
        await repo.log_audit(session, user.id, "donation", payload)
        await message.answer(
            t(lang, "donate_thanks", stars=sp.total_amount),
            parse_mode="HTML",
        )
        return

    sub = await repo.grant_subscription(session, user.id, settings.SUBSCRIPTION_DAYS, source="stars")
    await repo.log_audit(session, user.id, "payment", payload)
    await message.answer(
        t(lang, "payment_success", date=sub.expires_at.strftime("%Y-%m-%d")),
        parse_mode="HTML",
    )
