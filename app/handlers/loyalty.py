"""
Feature 14 — Loyalty Points System
Commands: /points, /redeem
Callback data:
  points:history          → points ledger page
  points:redeem           → redemption menu
  points:redeem:<key>     → execute a specific redemption
  points:redeem_history   → past redemptions
"""
from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.locales import t
from app.repositories import repo

router = Router(name="loyalty")

# ---------- Keyboard builders ----------

def points_main_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "points_btn_redeem"), callback_data="points:redeem")],
        [InlineKeyboardButton(text=t(lang, "points_btn_history"), callback_data="points:history")],
        [InlineKeyboardButton(text=t(lang, "points_btn_redemption_history"), callback_data="points:redeem_history")],
    ])


def redeem_kb(lang: str) -> InlineKeyboardMarkup:
    keys = list(repo.REDEMPTION_CATALOGUE.keys())
    rows = []
    for key in keys:
        _, label_key = repo.REDEMPTION_CATALOGUE[key]
        rows.append([InlineKeyboardButton(
            text=t(lang, label_key),
            callback_data=f"points:redeem:{key}",
        )])
    rows.append([InlineKeyboardButton(text=t(lang, "back_btn"), callback_data="points:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_to_points_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "back_btn"), callback_data="points:main")]
    ])


# ---------- Helpers ----------

def _fmt_date(dt) -> str:
    return dt.strftime("%Y-%m-%d %H:%M") if dt else "—"


# ---------- /points ----------

@router.message(Command("points"))
async def cmd_points(message: Message, session: AsyncSession, user, lang: str) -> None:
    balance = await repo.get_loyalty_points(session, user.id)
    text = (
        f"{t(lang, 'points_title')}\n\n"
        f"{t(lang, 'points_balance', points=balance)}\n\n"
        f"{t(lang, 'points_how_to_earn')}"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=points_main_kb(lang))


# ---------- Callback: main menu ----------

@router.callback_query(F.data == "points:main")
async def cb_points_main(cb: CallbackQuery, session: AsyncSession, user, lang: str) -> None:
    balance = await repo.get_loyalty_points(session, user.id)
    text = (
        f"{t(lang, 'points_title')}\n\n"
        f"{t(lang, 'points_balance', points=balance)}\n\n"
        f"{t(lang, 'points_how_to_earn')}"
    )
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=points_main_kb(lang))
    await cb.answer()


# ---------- Callback: points history ----------

@router.callback_query(F.data == "points:history")
async def cb_points_history(cb: CallbackQuery, session: AsyncSession, user, lang: str) -> None:
    ledger = await repo.get_points_ledger(session, user.id, limit=20)
    if not ledger:
        text = f"{t(lang, 'points_history_title')}\n\n{t(lang, 'points_history_empty')}"
    else:
        rows = []
        for i, entry in enumerate(ledger, 1):
            reason_label = t(lang, entry.reason) if entry.reason else entry.reason
            rows.append(
                t(lang, "points_history_row",
                  i=i,
                  reason=reason_label,
                  delta=entry.delta,
                  balance=entry.balance_after,
                  date=_fmt_date(entry.created_at))
            )
        text = f"{t(lang, 'points_history_title')}\n\n" + "\n".join(rows)
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=back_to_points_kb(lang))
    await cb.answer()


# ---------- Callback: redeem menu ----------

@router.callback_query(F.data == "points:redeem")
async def cb_redeem_menu(cb: CallbackQuery, session: AsyncSession, user, lang: str) -> None:
    balance = await repo.get_loyalty_points(session, user.id)
    text = (
        f"{t(lang, 'redeem_title')}\n\n"
        f"{t(lang, 'redeem_balance', points=balance)}\n\n"
        f"{t(lang, 'redeem_options')}"
    )
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=redeem_kb(lang))
    await cb.answer()


# ---------- Callback: execute redemption ----------

@router.callback_query(F.data.startswith("points:redeem:"))
async def cb_do_redeem(cb: CallbackQuery, session: AsyncSession, user, lang: str) -> None:
    item_key = cb.data.split(":", 2)[2]
    if item_key not in repo.REDEMPTION_CATALOGUE:
        await cb.answer("Unknown item.", show_alert=True)
        return

    cost, label_key = repo.REDEMPTION_CATALOGUE[item_key]
    success, new_balance = await repo.spend_loyalty_points(
        session, user.id, cost, reason=f"redeem:{item_key}"
    )
    if not success:
        current = await repo.get_loyalty_points(session, user.id)
        await cb.answer(
            t(lang, "redeem_not_enough", needed=cost, have=current),
            show_alert=True,
        )
        return

    # Record redemption
    await repo.add_redemption(session, user.id, item_key, cost)

    # Fulfil reward
    reply_text: str
    if item_key == "premium_1":
        await repo.grant_subscription(session, user.id, 1, source="points")
        reply_text = t(lang, "redeem_success_premium", days=1)
    elif item_key == "premium_3":
        await repo.grant_subscription(session, user.id, 3, source="points")
        reply_text = t(lang, "redeem_success_premium", days=3)
    elif item_key == "premium_7":
        await repo.grant_subscription(session, user.id, 7, source="points")
        reply_text = t(lang, "redeem_success_premium", days=7)
    elif item_key == "uses_5":
        await repo.add_streak_bonus_uses(session, user.id, 5)
        reply_text = t(lang, "redeem_success_uses", count=5)
    elif item_key == "uses_10":
        await repo.add_streak_bonus_uses(session, user.id, 10)
        reply_text = t(lang, "redeem_success_uses", count=10)
    elif item_key == "spin":
        await repo.grant_bonus_spin(session, user.id)
        reply_text = t(lang, "redeem_success_spin")
    elif item_key == "badge_gold":
        await repo.award_badge(session, user.id, "gold")
        reply_text = t(lang, "redeem_success_badge")
    else:
        reply_text = "✅ Redeemed!"

    await repo.log_audit(session, user.id, "points_redeemed", f"{item_key}:{cost}")

    balance_now = await repo.get_loyalty_points(session, user.id)
    full_text = (
        f"{reply_text}\n\n"
        f"{t(lang, 'points_balance', points=balance_now)}"
    )
    await cb.message.edit_text(full_text, parse_mode="HTML", reply_markup=points_main_kb(lang))
    await cb.answer()


# ---------- Callback: redemption history ----------

@router.callback_query(F.data == "points:redeem_history")
async def cb_redeem_history(cb: CallbackQuery, session: AsyncSession, user, lang: str) -> None:
    history = await repo.get_redemption_history(session, user.id, limit=20)
    if not history:
        text = (
            f"{t(lang, 'points_redemption_history_title')}\n\n"
            f"{t(lang, 'points_redemption_history_empty')}"
        )
    else:
        rows = []
        for i, entry in enumerate(history, 1):
            _, label_key = repo.REDEMPTION_CATALOGUE.get(entry.item_key, (0, entry.item_key))
            item_label = t(lang, label_key) if label_key in [
                t.__doc__ or "" for _ in []  # placeholder, just use label_key directly
            ] else t(lang, label_key) if label_key.startswith("redeem_btn_") else entry.item_key
            rows.append(
                t(lang, "points_redemption_row",
                  i=i,
                  item=item_label,
                  cost=entry.cost,
                  date=_fmt_date(entry.created_at))
            )
        text = f"{t(lang, 'points_redemption_history_title')}\n\n" + "\n".join(rows)
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=back_to_points_kb(lang))
    await cb.answer()
