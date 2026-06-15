from __future__ import annotations
from aiogram import Router, F
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession
from app.locales import t
from app.config import settings
from app.repositories import repo
from app.services.subscription import days_remaining
from app.keyboards.keyboards import gift_menu_kb

router = Router(name="gifting")


@router.message(Command("gift"))
async def cmd_gift(message: Message, lang: str) -> None:
    await message.answer(
        f"{t(lang, 'gift_menu_title')}\n\n{t(lang, 'gift_menu_body')}",
        parse_mode="HTML",
        reply_markup=gift_menu_kb(lang),
    )


@router.callback_query(F.data.startswith("gift:create:"))
async def cb_gift_create(cb: CallbackQuery, session: AsyncSession, user, lang: str) -> None:
    try:
        days = int(cb.data.split(":")[2])
    except (IndexError, ValueError):
        await cb.answer()
        return

    available = await days_remaining(session, user)
    if available <= 0:
        await cb.answer()
        await cb.message.answer(t(lang, "gift_no_subscription"), parse_mode="HTML")
        return
    if available < days:
        await cb.answer()
        await cb.message.answer(
            t(lang, "gift_not_enough_days", available=available, requested=days),
            parse_mode="HTML",
        )
        return

    deducted = await repo.deduct_subscription_days(session, user.id, days)
    if not deducted:
        await cb.answer()
        await cb.message.answer(
            t(lang, "gift_not_enough_days", available=available, requested=days),
            parse_mode="HTML",
        )
        return

    gift = await repo.create_gift(
        session, sender_id=user.id, days=days, expires_in_days=settings.GIFT_EXPIRY_DAYS
    )
    await repo.log_audit(session, user.id, "gift_created", gift.code)

    await cb.answer()
    await cb.message.answer(
        t(
            lang, "gift_created",
            days=gift.days, code=gift.code,
            expires=gift.expires_at.strftime("%Y-%m-%d"),
        ),
        parse_mode="HTML",
    )


@router.message(Command("redeem"))
async def cmd_redeem(message: Message, command: CommandObject, session: AsyncSession, user, lang: str) -> None:
    if not command.args:
        await message.answer(t(lang, "gift_redeem_usage"), parse_mode="HTML")
        return

    code = command.args.strip().split()[0]
    gift = await repo.get_gift_by_code(session, code)
    if gift is None:
        await message.answer(t(lang, "gift_redeem_not_found"), parse_mode="HTML")
        return

    success, reason = await repo.claim_gift(session, gift, claimer_id=user.id)
    if not success:
        key = {
            "self_gift": "gift_redeem_self",
            "already_claimed": "gift_redeem_already_claimed",
            "expired": "gift_redeem_expired",
            "cancelled": "gift_redeem_cancelled",
            "wrong_recipient": "gift_redeem_wrong_recipient",
        }.get(reason, "gift_redeem_not_found")
        await message.answer(t(lang, key), parse_mode="HTML")
        return

    sub = await repo.grant_subscription(session, user.id, gift.days, source="gift")
    await repo.log_audit(session, user.id, "gift_claimed", gift.code)

    await message.answer(
        t(lang, "gift_redeem_success", days=gift.days, date=sub.expires_at.strftime("%Y-%m-%d")),
        parse_mode="HTML",
    )

    # Notify the sender, best-effort
    sender = await repo.get_user_by_id(session, gift.sender_id)
    if sender:
        try:
            await message.bot.send_message(
                sender.telegram_id,
                t(sender.language or "en", "gift_sender_notify", days=gift.days, code=gift.code),
                parse_mode="HTML",
            )
        except Exception:
            pass


@router.message(Command("gifts"))
async def cmd_gifts(message: Message, session: AsyncSession, user, lang: str) -> None:
    sent = await repo.list_sent_gifts(session, user.id, limit=20)
    received = await repo.list_received_gifts(session, user.id, limit=20)

    if not sent and not received:
        await message.answer(
            f"{t(lang, 'gift_history_title')}\n\n{t(lang, 'gift_history_empty')}",
            parse_mode="HTML",
        )
        return

    lines = [t(lang, "gift_history_title"), ""]

    if sent:
        lines.append(t(lang, "gift_sent_title"))
        status_keys = {
            "pending": "gift_status_pending",
            "claimed": "gift_status_claimed",
            "expired": "gift_status_expired",
            "cancelled": "gift_status_cancelled",
        }
        for i, g in enumerate(sent, 1):
            status = t(lang, status_keys.get(g.status, "gift_status_pending"))
            lines.append(t(
                lang, "gift_row_sent",
                i=i, days=g.days, status=status, date=g.created_at.strftime("%Y-%m-%d"),
            ))
        lines.append("")

    if received:
        lines.append(t(lang, "gift_received_title"))
        for i, g in enumerate(received, 1):
            date = (g.claimed_at or g.created_at).strftime("%Y-%m-%d")
            lines.append(t(lang, "gift_row_received", i=i, days=g.days, date=date))

    await message.answer("\n".join(lines), parse_mode="HTML")
