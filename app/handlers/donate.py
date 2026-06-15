from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.locales import t
from app.keyboards.keyboards import donate_kb
from app.payments.stars import send_donation_invoice

router = Router(name="donate")

# Telegram Stars invoices accept amounts from 1 to 100000.
MIN_DONATION = 1
MAX_DONATION = 100_000


class DonateFSM(StatesGroup):
    waiting_amount = State()


@router.message(Command("donate"))
async def cmd_donate(message: Message, lang: str) -> None:
    await message.answer(
        f"{t(lang, 'donate_title')}\n\n{t(lang, 'donate_body')}",
        parse_mode="HTML",
        reply_markup=donate_kb(lang),
    )


@router.callback_query(F.data.startswith("donate:"))
async def cb_donate_amount(cb: CallbackQuery, state: FSMContext, lang: str) -> None:
    value = cb.data.split(":", 1)[1]

    if value == "custom":
        await state.set_state(DonateFSM.waiting_amount)
        await cb.answer()
        await cb.message.answer(
            t(lang, "donate_custom_prompt", min=MIN_DONATION, max=MAX_DONATION),
            parse_mode="HTML",
        )
        return

    try:
        amount = int(value)
    except ValueError:
        await cb.answer()
        return

    await cb.answer()
    await send_donation_invoice(cb.bot, cb.message.chat.id, cb.from_user.id, lang, amount)


@router.message(DonateFSM.waiting_amount)
async def on_custom_amount(message: Message, session: AsyncSession, user, lang: str, state: FSMContext) -> None:
    await state.clear()
    text = (message.text or "").strip()
    try:
        amount = int(text)
    except ValueError:
        await message.answer(t(lang, "donate_invalid_amount", min=MIN_DONATION, max=MAX_DONATION), parse_mode="HTML")
        return

    if amount < MIN_DONATION or amount > MAX_DONATION:
        await message.answer(t(lang, "donate_invalid_amount", min=MIN_DONATION, max=MAX_DONATION), parse_mode="HTML")
        return

    await send_donation_invoice(message.bot, message.chat.id, user.id, lang, amount)
