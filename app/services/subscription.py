from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories import repo
from app.database.models import User


async def is_subscribed(session: AsyncSession, user: User) -> bool:
    sub = await repo.active_subscription(session, user.id)
    return sub is not None


async def days_remaining(session: AsyncSession, user: User) -> int:
    sub = await repo.active_subscription(session, user.id)
    if not sub:
        return 0
    delta = sub.expires_at - datetime.now(timezone.utc)
    return max(0, delta.days)


def premium_badge(subscribed: bool) -> str:
    """Return a ⭐ badge string for premium users, empty string otherwise."""
    return "⭐ " if subscribed else ""


async def get_subscription_badge(session: AsyncSession, user: User) -> str:
    """Return the premium badge for a user based on their subscription status."""
    subscribed = await is_subscribed(session, user)
    return premium_badge(subscribed)
