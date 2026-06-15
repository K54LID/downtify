from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import update
from app.database import SessionLocal
from app.database.models import Subscription
from app.utils.logging import log


async def expire_subscriptions() -> None:
    async with SessionLocal() as session:
        now = datetime.now(timezone.utc)
        res = await session.execute(
            update(Subscription)
            .where(Subscription.active.is_(True), Subscription.expires_at <= now)
            .values(active=False)
        )
        await session.commit()
        if res.rowcount:
            log.info("subscriptions.expired", count=res.rowcount)
