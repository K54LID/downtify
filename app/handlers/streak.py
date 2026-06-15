from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.locales import t
from app.repositories import repo
from app.repositories.repo import add_loyalty_points_with_ledger, POINTS_PER_DAILY_USAGE, POINTS_PER_STREAK_REWARD

router = Router(name="streak")

# Maps milestone reward_key -> (streak_threshold, i18n achievement key)
_MILESTONE_META: dict[str, tuple[int, str]] = {
    "bonus_uses_3": (7, "streak_achieved_7"),
    "bonus_uses_7": (14, "streak_achieved_14"),
    "premium_7days": (30, "streak_achieved_30"),
}

# Next-reward labels (i18n keys)
_NEXT_REWARD_KEY: dict[str, str] = {
    "bonus_uses_3": "streak_reward_7",
    "bonus_uses_7": "streak_reward_14",
    "premium_7days": "streak_reward_30",
}


def _next_reward_text(streak_row, lang: str) -> str:
    """Return a human-readable description of the next unclaimed milestone."""
    granted = set(streak_row.rewards_granted.split(",")) if streak_row.rewards_granted else set()
    for reward_key, threshold_and_key in _MILESTONE_META.items():
        if reward_key not in granted:
            return t(lang, _NEXT_REWARD_KEY[reward_key])
    return t(lang, "streak_no_next_reward")


@router.message(Command("streak"))
async def cmd_streak(message: Message, session: AsyncSession, user, lang: str) -> None:
    streak = await repo.get_streak(session, user.id)
    next_reward = _next_reward_text(streak, lang)

    text = (
        f"{t(lang, 'streak_title')}\n\n"
        f"{t(lang, 'streak_current', days=streak.current_streak)}\n"
        f"{t(lang, 'streak_longest', days=streak.longest_streak)}\n\n"
        f"{t(lang, 'streak_next_reward', reward=next_reward)}"
    )
    await message.answer(text, parse_mode="HTML")


async def process_streak_on_usage(
    session: AsyncSession,
    user,
    lang: str,
    bot,
    chat_id: int,
) -> None:
    """
    Call this once per day (on first usage) to update the streak and
    dispatch any milestone reward notifications + effects.
    """
    streak, new_milestones = await repo.update_streak(session, user.id)

    # Award daily usage points (once per day — streak.update_streak only fires on first daily use)
    await add_loyalty_points_with_ledger(session, user.id, POINTS_PER_DAILY_USAGE, "points_earned_daily")

    for reward_key in new_milestones:
        _, achievement_key = _MILESTONE_META[reward_key]

        # Grant the reward
        if reward_key == "bonus_uses_3":
            await repo.add_streak_bonus_uses(session, user.id, 3)
        elif reward_key == "bonus_uses_7":
            await repo.add_streak_bonus_uses(session, user.id, 7)
        elif reward_key == "premium_7days":
            await repo.grant_subscription(session, user.id, 7, source="streak")
            await repo.log_audit(session, user.id, "streak_reward_premium", "30_day_streak")

        # Award bonus loyalty points for milestone
        await add_loyalty_points_with_ledger(session, user.id, POINTS_PER_STREAK_REWARD, "points_earned_streak")

        # Notify user
        try:
            await bot.send_message(chat_id, t(lang, achievement_key), parse_mode="HTML")
        except Exception:
            pass
