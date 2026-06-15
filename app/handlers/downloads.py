from __future__ import annotations
import os
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from sqlalchemy.ext.asyncio import AsyncSession
from app.locales import t
from app.config import settings
from app.utils.detect import detect_platform, extract_url, looks_like_music_search
from app.keyboards.keyboards import (
    tiktok_kb, instagram_kb, youtube_kb, youtube_quality_kb,
    search_results_kb, subscribe_kb, upgrade_kb,
)
from app.services import kv
from app.services.subscription import is_subscribed, days_remaining
from app.downloads.ytdlp import download, search_music
from app.repositories import repo


async def _maybe_reward_referral(session, user, lang: str, bot, chat_id: int) -> None:
    """
    On a user's FIRST successful download, if they were referred and the
    referral hasn't been rewarded yet, grant Premium days to both the
    referrer and the referred user, and notify both.
    """
    if user.referred_by_id is None:
        return

    successful = await repo.count_successful_downloads(session, user.id)
    if successful != 1:
        return  # only trigger once, on the first successful download

    referrals = await repo.list_referrals(session, user.referred_by_id)
    ref = next((r for r in referrals if r.referred_id == user.id and not r.rewarded), None)
    if ref is None:
        return

    referrer = await repo.get_user_by_id(session, user.referred_by_id)
    if referrer is None:
        return

    await repo.grant_subscription(session, referrer.id, settings.REFERRAL_REWARD_DAYS, source="referral")
    await repo.grant_subscription(session, user.id, settings.REFERRAL_BONUS_DAYS, source="referral_bonus")
    await repo.mark_referral_rewarded(session, ref.id)
    await repo.log_audit(session, referrer.id, "referral_rewarded", str(ref.id))

    await bot.send_message(
        chat_id,
        t(lang, "referral_reward_referred", days=settings.REFERRAL_BONUS_DAYS),
        parse_mode="HTML",
    )
    try:
        await bot.send_message(
            referrer.telegram_id,
            t(referrer.language or "en", "referral_reward_referrer", days=settings.REFERRAL_REWARD_DAYS),
            parse_mode="HTML",
        )
    except Exception:
        pass


router = Router(name="downloads")


@router.message(F.text & ~F.text.startswith("/"))
async def on_text(message: Message, session: AsyncSession, user, lang: str) -> None:
    text = message.text or ""
    url = extract_url(text)
    platform = detect_platform(text) if url else None

    if url and platform == "tiktok":
        token = await kv.put({"url": url})
        await message.answer(t(lang, "detected_tiktok"), reply_markup=tiktok_kb(lang, token))
        return
    if url and platform == "instagram":
        token = await kv.put({"url": url})
        await message.answer(t(lang, "detected_instagram"), reply_markup=instagram_kb(lang, token))
        return
    if url and platform == "youtube":
        token = await kv.put({"url": url})
        await message.answer(t(lang, "detected_youtube"), reply_markup=youtube_kb(lang, token))
        return

    if looks_like_music_search(text):
        await repo.add_search(session, user.id, text)
        status = await message.answer(t(lang, "processing"))
        try:
            results = await search_music(text)
        except Exception:
            results = []
        if not results:
            await status.edit_text(t(lang, "search_no_results"))
            return
        token = await kv.put({"results": results})
        body = t(lang, "search_found") + "\n\n"
        for i, r in enumerate(results[:8], 1):
            body += f"{i}. {r.get('title','?')[:60]}\n"
        await status.edit_text(body, parse_mode="HTML",
                               reply_markup=search_results_kb(token, results))
        return

    await message.answer(t(lang, "unknown_input"), parse_mode="HTML")


# -------- Guards --------

async def _guard_subscription(message_or_cb, session, user, lang) -> bool:
    """Return True if user is subscribed (premium). Shows upgrade screen otherwise."""
    if await is_subscribed(session, user):
        return True
    chat = message_or_cb.message if isinstance(message_or_cb, CallbackQuery) else message_or_cb
    await chat.answer(t(lang, "subscription_required"),
                      reply_markup=subscribe_kb(lang, settings.SUBSCRIPTION_STARS))
    if isinstance(message_or_cb, CallbackQuery):
        await message_or_cb.answer()
    return False


async def _guard_daily_usage(message_or_cb, session, user, lang) -> bool:
    """
    For non-premium users: check daily free-use limit.
    - If uses remain: consume one and return True (allowed).
    - If limit reached: show upgrade screen and return False (blocked).
    Premium users always pass through without consuming a free use.
    """
    if await is_subscribed(session, user):
        return True  # premium — unlimited

    remaining = await repo.get_daily_uses_remaining(session, user.id, settings.DAILY_FREE_USES)

    if remaining <= 0:
        chat = message_or_cb.message if isinstance(message_or_cb, CallbackQuery) else message_or_cb
        await chat.answer(
            f"{t(lang, 'free_uses_exhausted_title')}\n\n"
            f"{t(lang, 'free_uses_exhausted_body', limit=settings.DAILY_FREE_USES, stars=settings.SUBSCRIPTION_STARS)}",
            parse_mode="HTML",
            reply_markup=upgrade_kb(lang, settings.SUBSCRIPTION_STARS),
        )
        if isinstance(message_or_cb, CallbackQuery):
            await message_or_cb.answer()
        return False

    # Consume one use
    new_count = await repo.increment_daily_usage(session, user.id)
    remaining_after = max(0, settings.DAILY_FREE_USES - new_count)

    # Notify user of remaining uses (append to action, non-blocking)
    chat = message_or_cb.message if isinstance(message_or_cb, CallbackQuery) else message_or_cb
    if remaining_after == 1:
        notice = t(lang, "free_uses_remaining_one")
    elif remaining_after > 1:
        notice = t(lang, "free_uses_remaining_plural", count=remaining_after)
    else:
        notice = None  # last use consumed — final download message is sufficient

    if notice:
        try:
            await chat.answer(notice, parse_mode="HTML")
        except Exception:
            pass

    return True


# -------- Core download runner --------

async def _run_download(bot, chat_id: int, url: str, kind: str, quality: str | None,
                        session, user, lang: str, platform: str) -> None:
    status = await bot.send_message(chat_id, t(lang, "downloading"))
    try:
        result = await download(url, kind=kind if kind != "media" else "video", quality=quality)
    except Exception as exc:
        await repo.log_error(session, user.id, str(exc), context=f"{platform}:{kind}")
        await repo.add_download(session, user.id, platform, url, None, kind, success=False)
        await status.edit_text(t(lang, "download_failed", error=str(exc)[:200]))
        return

    try:
        size_mb = os.path.getsize(result.filepath) / (1024 * 1024)
        if size_mb > settings.DOWNLOAD_MAX_FILESIZE_MB:
            await status.edit_text(t(lang, "file_too_large", limit=settings.DOWNLOAD_MAX_FILESIZE_MB))
            await repo.add_download(session, user.id, platform, url, result.title, kind, success=False)
            return

        await status.edit_text(t(lang, "uploading"))
        file = FSInputFile(result.filepath, filename=os.path.basename(result.filepath))
        if result.kind == "audio":
            await bot.send_audio(chat_id, audio=file, title=result.title,
                                 performer=result.artist or "", duration=round(result.duration) or 0)
        else:
            send_kwargs = dict(
                video=file, caption=result.title[:1024],
                supports_streaming=True, duration=round(result.duration) or 0,
            )
            if result.width and result.height:
                send_kwargs["width"] = result.width
                send_kwargs["height"] = result.height
            await bot.send_video(chat_id, **send_kwargs)

        await repo.add_download(session, user.id, platform, url, result.title, kind, success=True)
        await _maybe_reward_referral(session, user, lang, bot, chat_id)

        subscribed = await is_subscribed(session, user)
        if subscribed:
            days = await days_remaining(session, user)
            await status.delete()
            await bot.send_message(chat_id, t(lang, "download_complete", days=days))
        else:
            remaining = await repo.get_daily_uses_remaining(session, user.id, settings.DAILY_FREE_USES)
            await status.delete()
            if remaining == 0:
                await bot.send_message(
                    chat_id,
                    f"✅ Done!\n\n{t(lang, 'free_uses_exhausted_title')}\n\n"
                    f"{t(lang, 'free_uses_exhausted_body', limit=settings.DAILY_FREE_USES, stars=settings.SUBSCRIPTION_STARS)}",
                    parse_mode="HTML",
                    reply_markup=upgrade_kb(lang, settings.SUBSCRIPTION_STARS),
                )
            else:
                notice = (
                    t(lang, "free_uses_remaining_one")
                    if remaining == 1
                    else t(lang, "free_uses_remaining_plural", count=remaining)
                )
                await bot.send_message(chat_id, f"✅ Done!\n\n{notice}", parse_mode="HTML")
    finally:
        result.cleanup()


@router.callback_query(F.data.startswith("dl:"))
async def cb_download(cb: CallbackQuery, session: AsyncSession, user, lang: str) -> None:
    parts = cb.data.split(":")
    # dl:platform:kind[:quality]:token
    if len(parts) < 4:
        await cb.answer(); return
    platform = parts[1]; kind = parts[2]
    if platform == "youtube" and kind == "video" and len(parts) == 5:
        quality = parts[3]; token = parts[4]
    else:
        quality = None; token = parts[-1]

    if not await _guard_daily_usage(cb, session, user, lang):
        return
    payload = await kv.get(token)
    if not payload or not payload.get("url"):
        await cb.answer("Expired", show_alert=True); return
    await cb.answer()
    await _run_download(cb.bot, cb.message.chat.id, payload["url"],
                        kind, quality, session, user, lang, platform)


@router.callback_query(F.data.startswith("yt:video:"))
async def cb_yt_pick_quality(cb: CallbackQuery, lang: str) -> None:
    token = cb.data.split(":", 2)[2]
    await cb.message.edit_reply_markup(reply_markup=youtube_quality_kb(lang, token))
    await cb.answer()


@router.callback_query(F.data.startswith("mus:"))
async def cb_music_pick(cb: CallbackQuery, session: AsyncSession, user, lang: str) -> None:
    _, token, idx = cb.data.split(":")
    payload = await kv.get(token)
    if not payload or "results" not in payload:
        await cb.answer("Expired", show_alert=True); return
    try:
        item = payload["results"][int(idx)]
    except (ValueError, IndexError):
        await cb.answer(); return
    if not await _guard_daily_usage(cb, session, user, lang):
        return
    await cb.answer()
    await _run_download(cb.bot, cb.message.chat.id, item["url"],
                        kind="audio", quality=None,
                        session=session, user=user, lang=lang, platform="music")
