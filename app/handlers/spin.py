from __future__ import annotations

from datetime import datetime, timezone

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.locales import t
from app.repositories import repo
from app.keyboards.keyboards import spin_kb

router = Router(name="spin")


def _format_wait(next_at: datetime) -> tuple[int, int]:
    now = datetime.now(timezone.utc)
    delta = next_at - now
    total_minutes = max(0, int(delta.total_seconds() // 60))
    hours, minutes = divmod(total_minutes, 60)
    return hours, minutes


async def _do_spin(session: AsyncSession, user, lang: str) -> tuple[bool, str]:
    """
    Execute a spin for `user` — caller must have verified eligibility.
    Returns (success, message_text).
    Applies the reward and records spin history.
    """
    reward = repo.pick_spin_reward()
    code = reward["code"]
    label = t(lang, reward["label_key"])

    # Apply the reward
    if code == "free_use_1":
        await repo.add_streak_bonus_uses(session, user.id, 1)
    elif code == "free_use_2":
        await repo.add_streak_bonus_uses(session, user.id, 2)
    elif code == "free_use_5":
        await repo.add_streak_bonus_uses(session, user.id, 5)
    elif code == "premium_1day":
        await repo.grant_subscription(session, user.id, 1, source="spin")
    elif code == "premium_3day":
        await repo.grant_subscription(session, user.id, 3, source="spin")

    await repo.record_spin(session, user.id, code, label)
    await repo.log_audit(session, user.id, "spin_wheel", code)

    text = f"{t(lang, 'spin_result_title')}\n\n🎁 <b>{label}</b>\n\n{t(lang, 'spin_next_spin')}"
    return True, text


@router.message(Command("spin"))
async def cmd_spin(message: Message, session: AsyncSession, user, lang: str) -> None:
    can, next_at = await repo.can_spin(session, user.id, settings.SPIN_COOLDOWN_HOURS)
    bonus_spins = await repo.count_unused_bonus_spins(session, user.id)

    if not can and bonus_spins == 0:
        hours, minutes = _format_wait(next_at)
        text = (
            f"{t(lang, 'spin_title')}\n\n"
            f"{t(lang, 'spin_already_spun', hours=hours, minutes=minutes)}"
        )
        await message.answer(text, parse_mode="HTML")
        return

    # Either the cooldown is up, or the user has a bonus spin available
    text = f"{t(lang, 'spin_title')}\n\n{t(lang, 'spin_intro')}"
    if bonus_spins > 0 and not can:
        text += f"\n\n🎡 <b>Bonus spins available: {bonus_spins}</b>"
    await message.answer(text, parse_mode="HTML", reply_markup=spin_kb(lang, can_spin=True))


@router.callback_query(F.data == "spin:go")
async def cb_spin(cb: CallbackQuery, session: AsyncSession, user, lang: str) -> None:
    can, next_at = await repo.can_spin(session, user.id, settings.SPIN_COOLDOWN_HOURS)
    bonus_spins = await repo.count_unused_bonus_spins(session, user.id)

    if not can and bonus_spins == 0:
        hours, minutes = _format_wait(next_at)
        await cb.answer(t(lang, "spin_already_spun", hours=hours, minutes=minutes), show_alert=True)
        return

    # Consume a bonus spin token if we're using one
    if not can and bonus_spins > 0:
        await repo.claim_bonus_spin(session, user.id)

    success, text = await _do_spin(session, user, lang)
    if not success:
        await cb.answer(text, show_alert=True)
        return

    await cb.answer()
    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=None)
    except Exception:
        await cb.message.answer(text, parse_mode="HTML")
