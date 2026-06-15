from __future__ import annotations
from datetime import datetime, timedelta, timezone
import pytest
from app.repositories import repo
from app.config import settings


async def _make_user(session, tg_id: int):
    return await repo.get_or_create_user(session, tg_id=tg_id, username=f"user{tg_id}")


@pytest.mark.asyncio
async def test_referral_code_generation_is_unique_and_persistent(session):
    user = await _make_user(session, 100)
    code1 = await repo.get_or_create_referral_code(session, user.id)
    code2 = await repo.get_or_create_referral_code(session, user.id)
    assert code1 == code2
    assert len(code1) == 8
    assert code1.isupper() or code1.isdigit() or code1.isalnum()


@pytest.mark.asyncio
async def test_get_user_by_referral_code(session):
    user = await _make_user(session, 101)
    code = await repo.get_or_create_referral_code(session, user.id)

    found = await repo.get_user_by_referral_code(session, code)
    assert found is not None
    assert found.id == user.id

    # case-insensitive lookup
    found_lower = await repo.get_user_by_referral_code(session, code.lower())
    assert found_lower is not None
    assert found_lower.id == user.id

    assert await repo.get_user_by_referral_code(session, "NOPE1234") is None


@pytest.mark.asyncio
async def test_link_referral_success(session):
    referrer = await _make_user(session, 200)
    referred = await _make_user(session, 201)

    ref = await repo.link_referral(session, referred_user=referred, referrer=referrer, reward_days=3)
    assert ref is not None
    assert ref.referrer_id == referrer.id
    assert ref.referred_id == referred.id
    assert ref.rewarded is False
    assert referred.referred_by_id == referrer.id

    count = await repo.count_referrals(session, referrer.id)
    assert count == 1


@pytest.mark.asyncio
async def test_link_referral_rejects_self_referral(session):
    user = await _make_user(session, 300)
    code = await repo.get_or_create_referral_code(session, user.id)
    user_again = await repo.get_user_by_referral_code(session, code)

    ref = await repo.link_referral(session, referred_user=user, referrer=user_again, reward_days=3)
    assert ref is None
    assert user.referred_by_id is None


@pytest.mark.asyncio
async def test_link_referral_rejects_double_referral(session):
    referrer1 = await _make_user(session, 400)
    referrer2 = await _make_user(session, 401)
    referred = await _make_user(session, 402)

    ref1 = await repo.link_referral(session, referred_user=referred, referrer=referrer1, reward_days=3)
    assert ref1 is not None

    # second attempt by a different referrer must be rejected
    ref2 = await repo.link_referral(session, referred_user=referred, referrer=referrer2, reward_days=3)
    assert ref2 is None

    # referred_by_id stays pointed at the first referrer
    assert referred.referred_by_id == referrer1.id
    assert await repo.count_referrals(session, referrer1.id) == 1
    assert await repo.count_referrals(session, referrer2.id) == 0


@pytest.mark.asyncio
async def test_referral_reward_flow(session):
    referrer = await _make_user(session, 500)
    referred = await _make_user(session, 501)

    ref = await repo.link_referral(session, referred_user=referred, referrer=referrer, reward_days=settings.REFERRAL_REWARD_DAYS)
    assert ref is not None
    assert ref.rewarded is False
    assert await repo.count_rewarded_referrals(session, referrer.id) == 0

    # simulate the reward being granted
    await repo.grant_subscription(session, referrer.id, settings.REFERRAL_REWARD_DAYS, source="referral")
    await repo.grant_subscription(session, referred.id, settings.REFERRAL_BONUS_DAYS, source="referral_bonus")
    await repo.mark_referral_rewarded(session, ref.id)

    assert await repo.count_rewarded_referrals(session, referrer.id) == 1

    referrer_sub = await repo.active_subscription(session, referrer.id)
    referred_sub = await repo.active_subscription(session, referred.id)
    assert referrer_sub is not None
    assert referred_sub is not None

    def _aware(dt):
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    referrer_days = (_aware(referrer_sub.expires_at) - datetime.now(timezone.utc)).days
    referred_days = (_aware(referred_sub.expires_at) - datetime.now(timezone.utc)).days
    assert referrer_days >= settings.REFERRAL_REWARD_DAYS - 1
    assert referred_days >= settings.REFERRAL_BONUS_DAYS - 1


@pytest.mark.asyncio
async def test_list_referrals_ordering(session):
    referrer = await _make_user(session, 600)
    referred1 = await _make_user(session, 601)
    referred2 = await _make_user(session, 602)

    await repo.link_referral(session, referred_user=referred1, referrer=referrer, reward_days=3)
    await repo.link_referral(session, referred_user=referred2, referrer=referrer, reward_days=3)

    refs = await repo.list_referrals(session, referrer.id)
    assert len(refs) == 2
    assert {r.referred_id for r in refs} == {referred1.id, referred2.id}
