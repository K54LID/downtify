from __future__ import annotations
from urllib.parse import quote
from aiogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton,
)
from app.locales import t


def main_menu_kb(lang: str, is_admin: bool = False) -> ReplyKeyboardMarkup:
    """
    Persistent reply keyboard giving access to every user-facing feature
    without requiring the user to type any commands.
    """
    rows = [
        [KeyboardButton(text=t(lang, "menu_btn_download")), KeyboardButton(text=t(lang, "menu_btn_subscription"))],
        [KeyboardButton(text=t(lang, "menu_btn_referral")), KeyboardButton(text=t(lang, "menu_btn_spin"))],
        [KeyboardButton(text=t(lang, "menu_btn_language")), KeyboardButton(text=t(lang, "menu_btn_donate"))],
        [KeyboardButton(text=t(lang, "menu_btn_help")), KeyboardButton(text=t(lang, "menu_btn_legal"))],
    ]
    if is_admin:
        rows.append([KeyboardButton(text=t(lang, "menu_btn_leaderboard")), KeyboardButton(text=t(lang, "menu_btn_admin"))])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def admin_menu_kb(lang: str) -> InlineKeyboardMarkup:
    """Inline admin panel — only ever shown to verified admins."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "admin_btn_dashboard"), callback_data="admin:dashboard")],
        [InlineKeyboardButton(text=t(lang, "admin_btn_stats"), callback_data="admin:stats")],
        [InlineKeyboardButton(text=t(lang, "admin_btn_users"), callback_data="admin:users")],
        [InlineKeyboardButton(text=t(lang, "admin_btn_user_lookup"), callback_data="admin:user_lookup")],
        [InlineKeyboardButton(text=t(lang, "admin_btn_grant"), callback_data="admin:grant")],
        [InlineKeyboardButton(text=t(lang, "admin_btn_revoke"), callback_data="admin:revoke")],
        [InlineKeyboardButton(text=t(lang, "admin_btn_broadcast"), callback_data="admin:broadcast")],
    ])


def back_to_admin_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "back_btn"), callback_data="admin:menu")]
    ])


def language_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="lang:en"),
         InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru")],
        [InlineKeyboardButton(text="🇹🇷 Türkçe", callback_data="lang:tr"),
         InlineKeyboardButton(text="🇸🇦 العربية", callback_data="lang:ar")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def tiktok_kb(lang: str, token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t(lang, "btn_video"), callback_data=f"dl:tiktok:video:{token}"),
        InlineKeyboardButton(text=t(lang, "btn_audio"), callback_data=f"dl:tiktok:audio:{token}"),
    ]])


def instagram_kb(lang: str, token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t(lang, "btn_video"), callback_data=f"dl:instagram:video:{token}"),
        InlineKeyboardButton(text=t(lang, "btn_media"), callback_data=f"dl:instagram:media:{token}"),
    ]])


def youtube_kb(lang: str, token: str) -> InlineKeyboardMarkup:
    rows = [[
        InlineKeyboardButton(text=t(lang, "btn_video"), callback_data=f"yt:video:{token}"),
        InlineKeyboardButton(text=t(lang, "btn_audio"), callback_data=f"dl:youtube:audio:{token}"),
    ]]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def youtube_quality_kb(lang: str, token: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=t(lang, "btn_quality_best"), callback_data=f"dl:youtube:video:best:{token}"),
         InlineKeyboardButton(text=t(lang, "btn_quality_720"), callback_data=f"dl:youtube:video:720:{token}")],
        [InlineKeyboardButton(text=t(lang, "btn_quality_480"), callback_data=f"dl:youtube:video:480:{token}"),
         InlineKeyboardButton(text=t(lang, "btn_quality_360"), callback_data=f"dl:youtube:video:360:{token}")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def subscribe_kb(lang: str, stars: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t(lang, "subscribe_btn", stars=stars), callback_data="sub:buy")
    ]])


def renew_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t(lang, "renew_btn"), callback_data="sub:buy")
    ]])


def search_results_kb(token: str, items: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for i, it in enumerate(items[:8]):
        title = it.get("title", "?")[:50]
        rows.append([InlineKeyboardButton(text=f"{i+1}. {title}", callback_data=f"mus:{token}:{i}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def referral_kb(lang: str, link: str) -> InlineKeyboardMarkup:
    share_text = t(lang, "referral_share_text", link=link)
    share_url = (
        "https://t.me/share/url?url="
        + quote(link, safe="")
        + "&text="
        + quote(share_text, safe="")
    )
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t(lang, "referral_share_btn"), url=share_url)
    ]])


def upgrade_kb(lang: str, stars: int) -> InlineKeyboardMarkup:
    """Shown when a free user hits their daily limit."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=t(lang, "free_uses_upgrade_btn"),
            callback_data="sub:buy",
        )
    ]])


def donate_kb(lang: str) -> InlineKeyboardMarkup:
    """Preset Telegram Stars donation amounts, plus a custom-amount option."""
    amounts = [10, 25, 50, 100, 250, 500]
    rows = []
    for i in range(0, len(amounts), 3):
        rows.append([
            InlineKeyboardButton(text=f"⭐ {a}", callback_data=f"donate:{a}")
            for a in amounts[i:i + 3]
        ])
    rows.append([InlineKeyboardButton(text=t(lang, "donate_btn_custom"), callback_data="donate:custom")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def spin_kb(lang: str, can_spin: bool) -> InlineKeyboardMarkup:
    rows = []
    if can_spin:
        rows.append([InlineKeyboardButton(text=t(lang, "spin_btn"), callback_data="spin:go")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def leaderboard_kb(lang: str, category: str, period: str) -> InlineKeyboardMarkup:
    """Inline keyboard to switch between leaderboard categories and periods."""
    categories = ["downloads", "referrals"]
    periods = ["weekly", "monthly", "all_time"]

    cat_row = []
    for c in categories:
        label = t(lang, f"leaderboard_category_{c}")
        prefix = "✅ " if c == category else ""
        cat_row.append(InlineKeyboardButton(text=f"{prefix}{label}", callback_data=f"lb:cat:{c}:{period}"))

    period_row = []
    for p in periods:
        label = t(lang, f"leaderboard_period_{p}")
        prefix = "✅ " if p == period else ""
        period_row.append(InlineKeyboardButton(text=f"{prefix}{label}", callback_data=f"lb:cat:{category}:{p}"))

    # Telegram allows up to several buttons per row but keep it mobile-friendly: 2 per row
    rows = []
    for i in range(0, len(cat_row), 2):
        rows.append(cat_row[i:i + 2])
    rows.append(period_row)
    return InlineKeyboardMarkup(inline_keyboard=rows)
