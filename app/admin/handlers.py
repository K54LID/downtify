from __future__ import annotations
import asyncio
from datetime import datetime, timedelta, timezone
from aiogram import Router, F, Bot
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.locales import t
from app.repositories import repo

router = Router(name="admin")


def is_admin(user_id: int) -> bool:
    return user_id in settings.admin_ids


async def _format_user_line(session: AsyncSession, u) -> str:
    """Format a single user entry for the admin Users list.

    Format: @username 🟢/🔴 · language · expiry date · telegramID
    """
    sub = await repo.active_subscription(session, u.id)
    status = "🟢" if sub else "🔴"
    expiry = sub.expires_at.strftime("%Y-%m-%d") if sub else "—"
    username = f"@{u.username}" if u.username else "—"
    return f"{username} {status} · {u.language} · {expiry} · <code>{u.telegram_id}</code>"


class BroadcastState(StatesGroup):
    waiting_text = State()


async def _build_dashboard_text(session: AsyncSession, lang: str) -> str:
    now = datetime.now(timezone.utc)

    users = await repo.count_users(session)
    active = await repo.count_active_subscriptions(session)
    expired = await repo.count_expired_subscriptions(session)
    revenue = await repo.total_revenue_stars(session)
    today = await repo.count_downloads_since(session, now - timedelta(days=1))
    week = await repo.count_downloads_since(session, now - timedelta(days=7))
    month = await repo.count_downloads_since(session, now - timedelta(days=30))
    new_today = await repo.count_new_users_since(session, now - timedelta(days=1))
    dau = await repo.count_distinct_active_users_since(session, now - timedelta(days=1))
    wau = await repo.count_distinct_active_users_since(session, now - timedelta(days=7))
    mau = await repo.count_distinct_active_users_since(session, now - timedelta(days=30))
    countries = await repo.top_countries(session)
    platforms = await repo.top_platforms(session)

    countries_str = "\n".join(f"  {c} — {n}" for c, n in countries) or "  —"
    platforms_str = "\n".join(f"  {p} — {n}" for p, n in platforms) or "  —"

    return t(lang, "admin_dashboard",
             users=users, active=active, expired=expired, revenue=revenue,
             today=today, week=week, month=month, new_today=new_today,
             dau=dau, wau=wau, mau=mau,
             countries=countries_str, platforms=platforms_str)


@router.message(Command("admin"))
async def cmd_admin(message: Message, session: AsyncSession, lang: str) -> None:
    if not is_admin(message.from_user.id):
        await message.answer(t(lang, "admin_only")); return
    await message.answer(await _build_dashboard_text(session, lang), parse_mode="HTML")


async def _build_stats_text(session: AsyncSession, lang: str) -> str:
    now = datetime.now(timezone.utc)

    # Users
    total_users = await repo.count_users(session)
    new_today   = await repo.count_new_users_since(session, now - timedelta(days=1))
    new_week    = await repo.count_new_users_since(session, now - timedelta(days=7))
    new_month   = await repo.count_new_users_since(session, now - timedelta(days=30))

    # Active users — distinct, based on last_seen_at
    dau = await repo.count_distinct_active_users_since(session, now - timedelta(days=1))
    wau = await repo.count_distinct_active_users_since(session, now - timedelta(days=7))
    mau = await repo.count_distinct_active_users_since(session, now - timedelta(days=30))

    # Downloads
    total_downloads = await repo.count_all_downloads(session)
    dl_day   = await repo.count_downloads_since(session, now - timedelta(days=1))
    dl_week  = await repo.count_downloads_since(session, now - timedelta(days=7))
    dl_month = await repo.count_downloads_since(session, now - timedelta(days=30))

    # Premium
    active_subs = await repo.count_active_subscriptions(session)
    revenue     = await repo.total_revenue_stars(session)

    # Referrals
    total_referrals   = await repo.total_referral_count(session)
    rewarded_referrals = await repo.count_rewarded_referrals_all(session)
    referral_cvr = (
        round(rewarded_referrals * 100 / total_referrals, 1)
        if total_referrals > 0 else 0.0
    )

    # Daily free usage
    free_users_today = await repo.count_free_users_active_today(session)
    free_uses_today  = await repo.sum_free_uses_today(session)
    avg_free_uses = (
        round(free_uses_today / free_users_today, 1)
        if free_users_today > 0 else 0.0
    )

    return t(lang, "admin_stats",
             total_users=total_users,
             new_today=new_today, new_week=new_week, new_month=new_month,
             dau=dau, wau=wau, mau=mau,
             total_downloads=total_downloads,
             dl_day=dl_day, dl_week=dl_week, dl_month=dl_month,
             active_subs=active_subs, revenue=revenue,
             total_referrals=total_referrals,
             rewarded_referrals=rewarded_referrals,
             referral_cvr=referral_cvr,
             free_users_today=free_users_today,
             free_uses_today=free_uses_today,
             avg_free_uses=avg_free_uses)


@router.message(Command("stats"))
async def cmd_stats(message: Message, session: AsyncSession, lang: str) -> None:
    if not is_admin(message.from_user.id):
        await message.answer(t(lang, "admin_only")); return
    await message.answer(await _build_stats_text(session, lang), parse_mode="HTML")


@router.message(Command("users"))
async def cmd_users(message: Message, session: AsyncSession, lang: str) -> None:
    if not is_admin(message.from_user.id):
        await message.answer(t(lang, "admin_only")); return
    users = await repo.list_users(session, limit=50)
    if not users:
        await message.answer(t(lang, "admin_no_users")); return
    lines = [await _format_user_line(session, u) for u in users]
    await message.answer("\n".join(lines)[:4000], parse_mode="HTML")


@router.message(Command("user"))
async def cmd_user(message: Message, command: CommandObject, session: AsyncSession, lang: str) -> None:
    if not is_admin(message.from_user.id):
        await message.answer(t(lang, "admin_only")); return
    if not command.args:
        await message.answer("Usage: /user <telegram_id>"); return
    try:
        tid = int(command.args.strip().split()[0])
    except ValueError:
        await message.answer("Invalid id."); return
    u = await repo.get_user_by_tg(session, tid)
    if not u:
        await message.answer(t(lang, "admin_user_not_found")); return
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
    )


@router.message(Command("grant"))
async def cmd_grant(message: Message, command: CommandObject, session: AsyncSession, lang: str) -> None:
    if not is_admin(message.from_user.id):
        await message.answer(t(lang, "admin_only")); return
    if not command.args:
        await message.answer("Usage: /grant <telegram_id> <days>"); return
    parts = command.args.split()
    if len(parts) != 2:
        await message.answer("Usage: /grant <telegram_id> <days>"); return
    try:
        tid = int(parts[0]); days = int(parts[1])
    except ValueError:
        await message.answer("Invalid args."); return
    u = await repo.get_user_by_tg(session, tid)
    if not u:
        await message.answer(t(lang, "admin_user_not_found")); return
    await repo.grant_subscription(session, u.id, days, source="admin")
    await repo.log_admin_action(session, message.from_user.id, "grant", u.id, str(days))
    await message.answer(t(lang, "admin_granted", days=days, tg=tid), parse_mode="HTML")


@router.message(Command("revoke"))
async def cmd_revoke(message: Message, command: CommandObject, session: AsyncSession, lang: str) -> None:
    if not is_admin(message.from_user.id):
        await message.answer(t(lang, "admin_only")); return
    if not command.args:
        await message.answer("Usage: /revoke <telegram_id>"); return
    try:
        tid = int(command.args.strip().split()[0])
    except ValueError:
        await message.answer("Invalid id."); return
    u = await repo.get_user_by_tg(session, tid)
    if not u:
        await message.answer(t(lang, "admin_user_not_found")); return
    await repo.revoke_subscription(session, u.id)
    await repo.log_admin_action(session, message.from_user.id, "revoke", u.id, None)
    await message.answer(t(lang, "admin_revoked", tg=tid), parse_mode="HTML")


@router.message(Command("shout"))
async def cmd_shout(message: Message, state: FSMContext, lang: str) -> None:
    if not is_admin(message.from_user.id):
        await message.answer(t(lang, "admin_only")); return
    await state.set_state(BroadcastState.waiting_text)
    await message.answer(t(lang, "admin_shout_prompt"))


@router.message(BroadcastState.waiting_text)
async def do_broadcast(message: Message, state: FSMContext, session: AsyncSession, lang: str, bot: Bot) -> None:
    await state.clear()
    if not is_admin(message.from_user.id):
        return
    text = message.text or message.caption or ""
    if not text:
        await message.answer("No text."); return
    ids = await repo.all_user_tg_ids(session)
    total = len(ids); sent = 0; failed = 0
    progress = await message.answer(t(lang, "admin_shout_progress", sent=0, total=total, failed=0))
    for i, tg_id in enumerate(ids, 1):
        try:
            await bot.send_message(tg_id, text)
            sent += 1
        except Exception:
            failed += 1
        if i % 25 == 0:
            try:
                await progress.edit_text(
                    t(lang, "admin_shout_progress", sent=sent, total=total, failed=failed)
                )
            except Exception:
                pass
            await asyncio.sleep(0.5)
        await asyncio.sleep(0.04)  # ~25 msg/s
    await repo.add_broadcast(session, message.from_user.id, text, total, sent, failed)
    await progress.edit_text(t(lang, "admin_shout_done", total=total, success=sent, failed=failed))
