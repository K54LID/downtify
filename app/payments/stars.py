from __future__ import annotations
from aiogram import Bot
from aiogram.types import LabeledPrice
from app.config import settings
from app.locales import t

SUB_PAYLOAD_PREFIX = "sub:monthly:"
DONATE_PAYLOAD_PREFIX = "donate:"


async def send_subscription_invoice(bot: Bot, chat_id: int, user_id: int, lang: str) -> None:
    payload = f"{SUB_PAYLOAD_PREFIX}{user_id}"
    await bot.send_invoice(
        chat_id=chat_id,
        title=t(lang, "payment_invoice_title"),
        description=t(lang, "payment_invoice_desc"),
        payload=payload,
        currency="XTR",  # Telegram Stars
        prices=[LabeledPrice(label="Unlimited Monthly", amount=settings.SUBSCRIPTION_STARS)],
        provider_token="",  # empty for Stars
        start_parameter="subscribe",
    )


async def send_donation_invoice(bot: Bot, chat_id: int, user_id: int, lang: str, amount: int) -> None:
    """Send a Telegram Stars invoice for a one-off donation of `amount` Stars."""
    payload = f"{DONATE_PAYLOAD_PREFIX}{amount}:{user_id}"
    await bot.send_invoice(
        chat_id=chat_id,
        title=t(lang, "donate_invoice_title"),
        description=t(lang, "donate_invoice_desc"),
        payload=payload,
        currency="XTR",  # Telegram Stars
        prices=[LabeledPrice(label=t(lang, "donate_invoice_label"), amount=amount)],
        provider_token="",  # empty for Stars
        start_parameter="donate",
    )
