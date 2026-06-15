from __future__ import annotations
from datetime import datetime, timedelta, timezone
import pytest
from app.repositories import repo
from app.config import settings


async def _make_user(session, tg_id: int):
    return await repo.get_or_create_user(session, tg_id=tg_id, username=f"user{tg_id}")


@pytest.mark.asyncio
async def test_create_gift_generates_unique_code(session):
    sender = await _make_user(session, 1000)
    g1 = await repo.create_gift(session, sender_id=sender.id, days=1)
    g2 = await repo.create_gift(session, sender_id=sender.id, days=7)
    assert g1.code != g2.code
    assert g1.code.startswith("GIFT-")
    assert g1.status == "pending"
    assert g1.recipient_id is None


@pytest.mark.asyncio
async def test_get_gift_by_code_case_insensitive(session):
    sender = await _make_user(session, 1001)
    gift = await repo.create_gift(session, sender_id=sender.id, days=7)

    found = await repo.get_gift_by_code(session, gift.code)
    assert found is not None
    assert found.id == gift.id

    found_lower = await repo.get_gift_by_code(session, gift.code.lower())
    assert found_lower is not None
    assert found_lower.id == gift.id

    assert await repo.get_gift_by_code(session, "GIFT-NOPE") is None


@pytest.mark.asyncio
async def test_claim_gift_success(session):
    sender = await _make_user(session, 1100)
    recipient = await _make_user(session, 1101)
    gift = await repo.create_gift(session, sender_id=sender.id, days=7)

    success, reason = await repo.claim_gift(session, gift, claimer_id=recipient.id)
    assert success is True
    assert reason == "ok"
    assert gift.status == "claimed"
    assert gift.recipient_id == recipient.id
    assert gift.claimed_at is not None


@pytest.mark.asyncio
async def test_claim_gift_rejects_self_claim(session):
    sender = await _make_user(session, 1200)
    gift = await repo.create_gift(session, sender_id=sender.id, days=7)

    success, reason = await repo.claim_gift(session, gift, claimer_id=sender.id)
    assert success is False
    assert reason == "self_gift"
    assert gift.status == "pending"


@pytest.mark.asyncio
async def test_claim_gift_rejects_double_claim(session):
    sender = await _make_user(session, 1300)
    recipient1 = await _make_user(session, 1301)
    recipient2 = await _make_user(session, 1302)
    gift = await repo.create_gift(session, sender_id=sender.id, days=7)

    ok1, _ = await repo.claim_gift(session, gift, claimer_id=recipient1.id)
    assert ok1 is True

    ok2, reason2 = await repo.claim_gift(session, gift, claimer_id=recipient2.id)
    assert ok2 is False
    assert reason2 == "already_claimed"
    # original recipient is preserved
    assert gift.recipient_id == recipient1.id


@pytest.mark.asyncio
async def test_claim_gift_rejects_expired(session):
    sender = await _make_user(session, 1400)
    recipient = await _make_user(session, 1401)
    gift = await repo.create_gift(session, sender_id=sender.id, days=7, expires_in_days=30)

    # force expiry
    gift.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    await session.flush()

    success, reason = await repo.claim_gift(session, gift, claimer_id=recipient.id)
    assert success is False
    assert reason == "expired"
    assert gift.status == "expired"


@pytest.mark.asyncio
async def test_claim_gift_rejects_wrong_recipient(session):
    sender = await _make_user(session, 1500)
    intended = await _make_user(session, 1501)
    other = await _make_user(session, 1502)
    gift = await repo.create_gift(session, sender_id=sender.id, days=7, recipient_id=intended.id)

    success, reason = await repo.claim_gift(session, gift, claimer_id=other.id)
    assert success is False
    assert reason == "wrong_recipient"

    success2, reason2 = await repo.claim_gift(session, gift, claimer_id=intended.id)
    assert success2 is True
    assert reason2 == "ok"


@pytest.mark.asyncio
async def test_deduct_subscription_days_requires_enough_balance(session):
    sender = await _make_user(session, 1600)

    # no subscription yet
    ok = await repo.deduct_subscription_days(session, sender.id, 1)
    assert ok is False

    await repo.grant_subscription(session, sender.id, 5, source="stars")
    ok2 = await repo.deduct_subscription_days(session, sender.id, 7)
    assert ok2 is False  # not enough days

    ok3 = await repo.deduct_subscription_days(session, sender.id, 3)
    assert ok3 is True

    sub = await repo.active_subscription(session, sender.id)
    expires_at = sub.expires_at if sub.expires_at.tzinfo else sub.expires_at.replace(tzinfo=timezone.utc)
    remaining = (expires_at - datetime.now(timezone.utc)).days
    assert remaining <= 2  # 5 - 3 = 2 days left


@pytest.mark.asyncio
async def test_full_gift_flow_deduct_create_redeem(session):
    sender = await _make_user(session, 1700)
    recipient = await _make_user(session, 1701)

    await repo.grant_subscription(session, sender.id, 30, source="stars")

    deducted = await repo.deduct_subscription_days(session, sender.id, 7)
    assert deducted is True

    gift = await repo.create_gift(session, sender_id=sender.id, days=7, expires_in_days=settings.GIFT_EXPIRY_DAYS)

    success, reason = await repo.claim_gift(session, gift, claimer_id=recipient.id)
    assert success and reason == "ok"

    sub = await repo.grant_subscription(session, recipient.id, gift.days, source="gift")
    assert sub is not None
    expires_at = sub.expires_at if sub.expires_at.tzinfo else sub.expires_at.replace(tzinfo=timezone.utc)
    days = (expires_at - datetime.now(timezone.utc)).days
    assert days >= 6

    sent = await repo.list_sent_gifts(session, sender.id)
    received = await repo.list_received_gifts(session, recipient.id)
    assert len(sent) == 1 and sent[0].id == gift.id
    assert len(received) == 1 and received[0].id == gift.id


@pytest.mark.asyncio
async def test_expire_stale_gifts(session):
    sender = await _make_user(session, 1800)
    gift1 = await repo.create_gift(session, sender_id=sender.id, days=1, expires_in_days=30)
    gift2 = await repo.create_gift(session, sender_id=sender.id, days=1, expires_in_days=30)

    gift1.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    await session.flush()

    count = await repo.expire_stale_gifts(session)
    assert count == 1

    refreshed1 = await repo.get_gift_by_code(session, gift1.code)
    refreshed2 = await repo.get_gift_by_code(session, gift2.code)
    assert refreshed1.status == "expired"
    assert refreshed2.status == "pending"
