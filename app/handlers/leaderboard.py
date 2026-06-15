from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.locales import t
from app.repositories import repo
from app.keyboards.keyboards import leaderboard_kb
from app.admin.handlers import is_admin

router = Router(name="leaderboard")

_MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}

_FETCHERS = {
    "downloads": repo.leaderboard_most_downloads,
    "referrals": repo.leaderboard_most_referrals,
}

_VALID_CATEGORIES = set(_FETCHERS.keys())
_VALID_PERIODS = {"weekly", "monthly", "all_time"}


async def _display_name(session: AsyncSession, user_id: int, lang: str) -> str:
    u = await repo.get_user_by_id(session, user_id)
    if u is None:
        return t(lang, "leaderboard_anon_user", id=user_id)
    if u.username:
        return f"@{u.username}"
    name = " ".join(filter(None, [u.first_name, u.last_name])).strip()
    return name or t(lang, "leaderboard_anon_user", id=user_id)


async def _render_leaderboard(session: AsyncSession, user, lang: str, category: str, period: str) -> str:
    fetcher = _FETCHERS[category]
    rows = await fetcher(session, period, limit=10)

    lines = [
        t(lang, "leaderboard_title"),
        f"{t(lang, f'leaderboard_category_{category}')} · {t(lang, f'leaderboard_period_{period}')}",
        "",
    ]

    if not rows:
        lines.append(t(lang, "leaderboard_empty"))
    else:
        for i, (uid, value) in enumerate(rows, 1):
            medal = _MEDALS.get(i, "")
            name = await _display_name(session, uid, lang)
            lines.append(t(lang, "leaderboard_row", medal=medal, rank=i, name=name, value=value))

    lines.append("")
    rank, value = await repo.user_rank_in_leaderboard(session, category, period, user.id, top_n=100)
    if rank is not None:
        lines.append(t(lang, "leaderboard_your_rank", rank=rank, value=value))
    else:
        lines.append(t(lang, "leaderboard_your_rank_unranked"))

    return "\n".join(lines)


@router.message(Command("leaderboard"))
async def cmd_leaderboard(message: Message, session: AsyncSession, user, lang: str) -> None:
    if not is_admin(message.from_user.id):
        await message.answer(t(lang, "admin_only"))
        return
    category, period = "downloads", "weekly"
    text = await _render_leaderboard(session, user, lang, category, period)
    await message.answer(text, parse_mode="HTML", reply_markup=leaderboard_kb(lang, category, period))


@router.callback_query(F.data.startswith("lb:cat:"))
async def cb_leaderboard_switch(cb: CallbackQuery, session: AsyncSession, user, lang: str) -> None:
    if not is_admin(cb.from_user.id):
        await cb.answer(t(lang, "admin_only"), show_alert=True)
        return
    parts = cb.data.split(":")
    # lb:cat:<category>:<period>
    if len(parts) != 4:
        await cb.answer()
        return
    category, period = parts[2], parts[3]
    if category not in _VALID_CATEGORIES or period not in _VALID_PERIODS:
        await cb.answer()
        return

    text = await _render_leaderboard(session, user, lang, category, period)
    await cb.answer()
    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=leaderboard_kb(lang, category, period))
    except Exception:
        pass
