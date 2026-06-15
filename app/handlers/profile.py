"""
Feature 15 — Personal Statistics Dashboard
Command: /profile
Shows: downloads, uses, streaks, loyalty points, referrals, achievements,
       premium status/days, leaderboard rank, badges.
"""
from __future__ import annotations

from datetime import datetime, timezone

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from app.locales import t
from app.repositories import repo
from app.repositories.repo import ACHIEVEMENT_DEFS
from app.services.subscription import days_remaining, is_subscribed
from app.admin.handlers import is_admin

router = Router(name="profile")

# Badge display metadata: badge_key -> (emoji, display name)
BADGE_META: dict[str, tuple[str, str]] = {
    "gold": ("🥇", "Gold Badge"),
}


def profile_kb(lang: str, admin: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text=t(lang, "profile_btn_achievements"), callback_data="ach:view"),
            InlineKeyboardButton(text=t(lang, "profile_btn_points"), callback_data="points:main"),
        ],
    ]
    if admin:
        rows.append([
            InlineKeyboardButton(text=t(lang, "profile_btn_leaderboard"), callback_data="lb:cat:downloads:all_time"),
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _fmt_date_short(dt: datetime) -> str:
    return dt.strftime("%d %b %Y")


@router.message(Command("profile"))
async def cmd_profile(message: Message, session: AsyncSession, user, lang: str) -> None:
    # ---- gather all stats concurrently (sequential awaits — acceptable) ----

    # Downloads & uses
    total_downloads = await repo.count_successful_downloads(session, user.id)
    total_uses = await repo.get_total_uses(session, user.id)

    # Streaks
    streak = await repo.get_streak(session, user.id)

    # Loyalty points
    points = await repo.get_loyalty_points(session, user.id)

    # Referrals
    referral_count = await repo.count_rewarded_referrals(session, user.id)

    # Achievements
    num_unlocked = await repo.count_total_unlocked_achievements(session, user.id)
    total_achievements = len(ACHIEVEMENT_DEFS)

    # Premium
    subscribed = await is_subscribed(session, user)
    days_left = await days_remaining(session, user) if subscribed else 0
    days_earned = await repo.get_total_premium_days_earned(session, user.id)

    # Leaderboard rank (downloads, all-time)
    rank, _ = await repo.user_rank_in_leaderboard(session, "downloads", "all_time", user.id)

    # Badges
    badges = await repo.get_user_badges(session, user.id)

    # ---- compose message ----
    member_date = _fmt_date_short(user.created_at) if user.created_at else "—"

    lines = [
        t(lang, "profile_title"),
        "",
        t(lang, "profile_member_since", date=member_date),
    ]

    # Premium status
    if subscribed:
        lines.append(t(lang, "profile_premium_active", days=days_left))
    else:
        lines.append(t(lang, "profile_premium_inactive"))

    # Stats block
    lines += [
        "",
        t(lang, "profile_stats_header"),
        t(lang, "profile_total_downloads", n=total_downloads),
        t(lang, "profile_total_uses", n=total_uses),
        t(lang, "profile_current_streak", n=streak.current_streak),
        t(lang, "profile_longest_streak", n=streak.longest_streak),
        t(lang, "profile_loyalty_points", n=points),
        t(lang, "profile_referral_count", n=referral_count),
        t(lang, "profile_achievements_earned", n=num_unlocked, total=total_achievements),
        t(lang, "profile_premium_days_earned", n=days_earned),
        t(lang, "profile_premium_days_remaining", n=days_left),
    ]

    # Leaderboard rank
    if rank is not None:
        lines.append(t(lang, "profile_leaderboard_rank", rank=rank))
    else:
        lines.append(t(lang, "profile_leaderboard_unranked"))

    # Badges block
    lines += ["", t(lang, "profile_badges_header")]
    if badges:
        for badge in badges:
            emoji, name = BADGE_META.get(badge.badge_key, ("🎖️", badge.badge_key.title()))
            lines.append(f"  {emoji} <b>{name}</b>")
    else:
        lines.append(f"  {t(lang, 'profile_no_badges')}")

    await message.answer(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=profile_kb(lang, admin=is_admin(message.from_user.id)),
    )
