from __future__ import annotations

from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.locales import t
from app.repositories import repo

router = Router(name="achievements")

# Maps achievement code -> emoji badge
ACHIEVEMENT_EMOJI: dict[str, str] = {
    "first_download": "🥇",
    "downloads_10": "🔟",
    "downloads_50": "🏵️",
    "downloads_100": "💯",
    "first_referral": "🤝",
    "referrals_3": "👥",
    "premium_subscriber": "⭐",
}


@router.message(Command("achievements"))
async def cmd_achievements(message: Message, session: AsyncSession, user, lang: str) -> None:
    progress = await repo.achievement_progress(session, user.id)
    unlocked_count = sum(1 for v in progress.values() if v["unlocked"])
    total = len(repo.ACHIEVEMENT_DEFS)

    lines = [
        t(lang, "achievements_title"),
        t(lang, "achievements_summary", unlocked=unlocked_count, total=total),
        "",
    ]

    for ach in repo.ACHIEVEMENT_DEFS:
        code = ach["code"]
        emoji = ACHIEVEMENT_EMOJI.get(code, "🏆")
        name = t(lang, f"ach_{code}_name")
        info = progress[code]
        if info["unlocked"]:
            date_str = info["unlocked_at"].strftime("%Y-%m-%d") if info["unlocked_at"] else "-"
            lines.append(t(lang, "achievement_row_unlocked", emoji=emoji, name=name, date=date_str))
        else:
            lines.append(t(
                lang, "achievement_row_locked",
                name=name, progress=info["progress"], threshold=info["threshold"],
            ))

    await message.answer("\n".join(lines), parse_mode="HTML")


async def check_achievements_and_notify(
    session: AsyncSession,
    user,
    lang: str,
    bot: Bot,
    chat_id: int,
) -> list[str]:
    """
    Evaluate achievement progress for `user`, unlock any newly-earned
    achievements, persist them, and notify the user. Returns the list of
    newly unlocked achievement codes. Call this after any action that could
    move the needle (download, referral, subscription purchase, streak update).
    """
    newly_unlocked = await repo.check_and_unlock_achievements(session, user.id)

    for code in newly_unlocked:
        emoji = ACHIEVEMENT_EMOJI.get(code, "🏆")
        name = t(lang, f"ach_{code}_name")
        description = t(lang, f"ach_{code}_desc")
        try:
            await bot.send_message(
                chat_id,
                t(lang, "achievement_unlocked_notification", emoji=emoji, name=name, description=description),
                parse_mode="HTML",
            )
        except Exception:
            pass
        await repo.log_audit(session, user.id, "achievement_unlocked", code)

    return newly_unlocked
