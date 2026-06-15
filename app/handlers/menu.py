"""
Main menu / navigation router.

Provides a persistent reply keyboard (built via main_menu_kb) so that every
user-facing feature is reachable via buttons, without the user needing to
type slash commands. Also provides an inline admin panel, visible only to
authorized admins, that exposes admin-only actions through buttons while
remaining completely hidden (and inaccessible) to regular users.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from aiogram import Router, F, Bot
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.locales import t, SUPPORTED
from app.config import settings
from app.repositories import repo
from app.keyboards.keyboards import (
    main_menu_kb, admin_menu_kb, back_to_admin_kb, language_kb,
)

# Re-use the existing feature handlers/commands so the menu doesn't
# duplicate any business logic.
from app.handlers.subscription import cmd_subscription
from app.handlers.referral import cmd_referral
from app.handlers.donate import cmd_donate
from app.handlers.spin import cmd_spin
from app.handlers.leaderboard import cmd_leaderboard
from app.handlers.common import cmd_help, cmd_language, cmd_legal
from app.admin.handlers import is_admin

router = Router(name="menu")


class AdminFSM(StatesGroup):
    waiting_user_lookup = State()
    waiting_grant = State()
    waiting_revoke = State()


async def send_main_menu(message: Message, lang: str, admin: bool) -> None:
    await message.answer(
        t(lang, "menu_download_hint"),
        parse_mode="HTML",
        reply_markup=main_menu_kb(lang, is_admin=admin),
    )


def _menu_label_map(lang: str) -> dict[str, str]:
    """Map localized button labels -> internal action keys for this language."""
    return {
        t(lang, "menu_btn_download"): "download",
        t(lang, "menu_btn_subscription"): "subscription",
        t(lang, "menu_btn_donate"): "donate",
        t(lang, "menu_btn_referral"): "referral",
        t(lang, "menu_btn_spin"): "spin",
        t(lang, "menu_btn_leaderboard"): "leaderboard",
        t(lang, "menu_btn_language"): "language",
        t(lang, "menu_btn_help"): "help",
        t(lang, "menu_btn_legal"): "legal",
        t(lang, "menu_btn_admin"): "admin",
    }


def _resolve_menu_action(text: str) -> str | None:
    """Find the action key for `text` across all supported languages."""
    for code in SUPPORTED:
        mapping = _menu_label_map(code)
        if text in mapping:
            return mapping[text]
    return None


@router.message(Command("menu"))
async def cmd_menu(message: Message, lang: str) -> None:
    await send_main_menu(message, lang, admin=is_admin(message.from_user.id))


@router.message(F.text & ~F.text.startswith("/"))
async def on_menu_text(message: Message, session: AsyncSession, user, lang: str, state: FSMContext) -> None:
    """
    Intercept presses on the persistent reply keyboard and route them to
    the corresponding feature handler. Any text that doesn't match a menu
    button falls through (returns without consuming the update) so the
    downloads router's catch-all can process it as a URL/search query.
    """
    text = (message.text or "").strip()
    action = _resolve_menu_action(text)

    if action is None:
        raise SkipHandler  # not a menu button — let other routers handle it


    # A menu button press always cancels any pending FSM state (e.g. a
    # half-finished admin prompt or broadcast).
    await state.clear()

    if action == "download":
        await message.answer(t(lang, "menu_download_hint"), parse_mode="HTML")
        return
    if action == "subscription":
        await cmd_subscription(message, session, user, lang)
        return
    if action == "donate":
        await cmd_donate(message, lang)
        return
    if action == "referral":
        await cmd_referral(message, session, user, lang)
        return
    if action == "spin":
        await cmd_spin(message, session, user, lang)
        return
    if action == "leaderboard":
        await cmd_leaderboard(message, session, user, lang)
        return
    if action == "language":
        await cmd_language(message, lang)
        return
    if action == "help":
        await cmd_help(message, lang)
        return
    if action == "legal":
        await cmd_legal(message, lang)
        return
    if action == "admin":
        if not is_admin(message.from_user.id):
            # Should never be reachable for non-admins (button isn't shown
            # to them), but guard anyway.
            await message.answer(t(lang, "admin_only"))
            return
        await message.answer(
            t(lang, "admin_menu_title"), parse_mode="HTML",
            reply_markup=admin_menu_kb(lang),
        )
        return


# ---------------- Admin inline panel ----------------

def _admin_guard(user_id: int) -> bool:
    return is_admin(user_id)


@router.callback_query(F.data.startswith("admin:"))
async def cb_admin_panel(cb: CallbackQuery, session: AsyncSession, lang: str, state: FSMContext, bot: Bot) -> None:
    if not _admin_guard(cb.from_user.id):
        await cb.answer(t(lang, "admin_only"), show_alert=True)
        return

    action = cb.data.split(":", 1)[1]

    if action == "menu":
        await state.clear()
        await cb.message.edit_text(t(lang, "admin_menu_title"), parse_mode="HTML",
                                    reply_markup=admin_menu_kb(lang))
        await cb.answer()
        return

    if action == "dashboard":
        from app.admin.handlers import _build_dashboard_text
        text = await _build_dashboard_text(session, lang)
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=back_to_admin_kb(lang))
        await cb.answer()
        return

    if action == "stats":
        from app.admin.handlers import _build_stats_text
        text = await _build_stats_text(session, lang)
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=back_to_admin_kb(lang))
        await cb.answer()
        return

    if action == "users":
        from app.admin.handlers import _format_user_line
        users = await repo.list_users(session, limit=50)
        if not users:
            text = t(lang, "admin_no_users")
        else:
            lines = [await _format_user_line(session, u) for u in users]
            text = "\n".join(lines)[:4000]
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=back_to_admin_kb(lang))
        await cb.answer()
        return

    if action == "user_lookup":
        await state.set_state(AdminFSM.waiting_user_lookup)
        await cb.message.edit_text(t(lang, "admin_user_lookup_prompt"), reply_markup=back_to_admin_kb(lang))
        await cb.answer()
        return

    if action == "grant":
        await state.set_state(AdminFSM.waiting_grant)
        await cb.message.edit_text(t(lang, "admin_grant_prompt"), parse_mode="HTML", reply_markup=back_to_admin_kb(lang))
        await cb.answer()
        return

    if action == "revoke":
        await state.set_state(AdminFSM.waiting_revoke)
        await cb.message.edit_text(t(lang, "admin_revoke_prompt"), reply_markup=back_to_admin_kb(lang))
        await cb.answer()
        return

    if action == "broadcast":
        from app.admin.handlers import BroadcastState
        await state.set_state(BroadcastState.waiting_text)
        await cb.message.edit_text(t(lang, "admin_shout_prompt"), reply_markup=back_to_admin_kb(lang))
        await cb.answer()
        return

    await cb.answer()


@router.message(AdminFSM.waiting_user_lookup)
async def admin_fsm_user_lookup(message: Message, session: AsyncSession, lang: str, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    await state.clear()
    try:
        tid = int((message.text or "").strip().split()[0])
    except (ValueError, IndexError):
        await message.answer(t(lang, "admin_invalid_input"), reply_markup=back_to_admin_kb(lang))
        return

    u = await repo.get_user_by_tg(session, tid)
    if not u:
        await message.answer(t(lang, "admin_user_not_found"), reply_markup=back_to_admin_kb(lang))
        return
    sub = await repo.active_subscription(session, u.id)
    downloads = len(await repo.recent_downloads(session, u.id, limit=1000))
    searches = await repo.count_searches(session, u.id)
    sub_s = f"active until {sub.expires_at.strftime('%Y-%m-%d')}" if sub else "none"
    await message.answer(
        t(lang, "admin_user_card",
          tg=u.telegram_id, username=(u.username or "—"),
          joined=u.created_at.strftime("%Y-%m-%d"),
          last_seen=u.last_seen_at.strftime("%Y-%m-%d %H:%M"),
          lang=u.language, downloads=downloads, searches=searches, sub=sub_s),
        parse_mode="HTML",
        reply_markup=back_to_admin_kb(lang),
    )


@router.message(AdminFSM.waiting_grant)
async def admin_fsm_grant(message: Message, session: AsyncSession, lang: str, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    await state.clear()
    parts = (message.text or "").split()
    if len(parts) != 2:
        await message.answer(t(lang, "admin_invalid_input"), reply_markup=back_to_admin_kb(lang))
        return
    try:
        tid = int(parts[0]); days = int(parts[1])
    except ValueError:
        await message.answer(t(lang, "admin_invalid_input"), reply_markup=back_to_admin_kb(lang))
        return

    u = await repo.get_user_by_tg(session, tid)
    if not u:
        await message.answer(t(lang, "admin_user_not_found"), reply_markup=back_to_admin_kb(lang))
        return
    await repo.grant_subscription(session, u.id, days, source="admin")
    await repo.log_admin_action(session, message.from_user.id, "grant", u.id, str(days))
    await message.answer(t(lang, "admin_granted", days=days, tg=tid), parse_mode="HTML",
                          reply_markup=back_to_admin_kb(lang))


@router.message(AdminFSM.waiting_revoke)
async def admin_fsm_revoke(message: Message, session: AsyncSession, lang: str, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    await state.clear()
    try:
        tid = int((message.text or "").strip().split()[0])
    except (ValueError, IndexError):
        await message.answer(t(lang, "admin_invalid_input"), reply_markup=back_to_admin_kb(lang))
        return

    u = await repo.get_user_by_tg(session, tid)
    if not u:
        await message.answer(t(lang, "admin_user_not_found"), reply_markup=back_to_admin_kb(lang))
        return
    await repo.revoke_subscription(session, u.id)
    await repo.log_admin_action(session, message.from_user.id, "revoke", u.id, None)
    await message.answer(t(lang, "admin_revoked", tg=tid), parse_mode="HTML",
                          reply_markup=back_to_admin_kb(lang))
