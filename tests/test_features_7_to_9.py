"""
Comprehensive test suite for features 7–9:
  - Language switching & persistence
  - Usage counting & daily reset
  - Subscription restrictions
  - Referral rewards
  - Localization coverage
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest
from app.locales import t, I18n, SUPPORTED, DEFAULT
from app.repositories import repo


# ─────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────

async def _make_user(session, tg_id: int):
    return await repo.get_or_create_user(session, tg_id=tg_id, username=f"u{tg_id}")


# ─────────────────────────────────────────
# Feature 7 · Localization / i18n
# ─────────────────────────────────────────

class TestLocalizationCoverage:
    """Every locale file must contain exactly the same keys as English (the fallback)."""

    def _load(self, lang: str) -> dict:
        path = Path(__file__).parent.parent / "app" / "locales" / f"{lang}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def test_all_locales_have_identical_key_set(self):
        en_keys = set(self._load("en").keys())
        for lang in SUPPORTED:
            if lang == "en":
                continue
            other_keys = set(self._load(lang).keys())
            missing = en_keys - other_keys
            extra = other_keys - en_keys
            assert not missing, f"{lang}.json is missing keys: {missing}"
            assert not extra, f"{lang}.json has unexpected extra keys: {extra}"

    def test_no_empty_values_in_english(self):
        en = self._load("en")
        empty = [k for k, v in en.items() if not v or not v.strip()]
        assert not empty, f"English locale has empty values: {empty}"

    def test_fallback_to_english_on_missing_key(self):
        result = t("ru", "THIS_KEY_DOES_NOT_EXIST")
        assert result == "THIS_KEY_DOES_NOT_EXIST"

    def test_fallback_language_is_english(self):
        assert DEFAULT == "en"

    def test_unknown_language_falls_back_to_english(self):
        i18n = I18n("zz")
        assert i18n.language == DEFAULT
        assert i18n.t("choose_language") == t("en", "choose_language")

    def test_format_kwargs_applied(self):
        result = t("en", "free_uses_remaining_plural", count=5)
        assert "5" in result


class TestLanguageSwitching:
    @pytest.mark.asyncio
    async def test_set_language_persists(self, session):
        user = await _make_user(session, 10_001)
        assert user.language == "en"
        await repo.set_language(session, user.id, "ru")
        await session.refresh(user)
        assert user.language == "ru"

    @pytest.mark.asyncio
    async def test_language_switches_multiple_times(self, session):
        user = await _make_user(session, 10_002)
        for lang in ["tr", "ar", "en", "ru"]:
            await repo.set_language(session, user.id, lang)
            await session.refresh(user)
            assert user.language == lang

    @pytest.mark.asyncio
    async def test_language_persists_across_user_fetch(self, session):
        user = await _make_user(session, 10_003)
        await repo.set_language(session, user.id, "tr")
        fetched = await repo.get_user_by_tg(session, 10_003)
        assert fetched.language == "tr"


# ─────────────────────────────────────────
# Feature 8 · Usage counting & daily reset
# ─────────────────────────────────────────

class TestUsageCounting:
    @pytest.mark.asyncio
    async def test_initial_count_is_zero(self, session):
        user = await _make_user(session, 20_001)
        count = await repo.get_daily_uses_count(session, user.id)
        assert count == 0

    @pytest.mark.asyncio
    async def test_increment_increases_count(self, session):
        user = await _make_user(session, 20_002)
        c1 = await repo.increment_daily_usage(session, user.id)
        c2 = await repo.increment_daily_usage(session, user.id)
        assert c1 == 1
        assert c2 == 2

    @pytest.mark.asyncio
    async def test_remaining_decreases_with_usage(self, session):
        user = await _make_user(session, 20_003)
        limit = 3
        assert await repo.get_daily_uses_remaining(session, user.id, limit) == 3
        await repo.increment_daily_usage(session, user.id)
        assert await repo.get_daily_uses_remaining(session, user.id, limit) == 2
        await repo.increment_daily_usage(session, user.id)
        assert await repo.get_daily_uses_remaining(session, user.id, limit) == 1
        await repo.increment_daily_usage(session, user.id)
        assert await repo.get_daily_uses_remaining(session, user.id, limit) == 0

    @pytest.mark.asyncio
    async def test_remaining_never_negative(self, session):
        user = await _make_user(session, 20_004)
        for _ in range(10):
            await repo.increment_daily_usage(session, user.id)
        remaining = await repo.get_daily_uses_remaining(session, user.id, 3)
        assert remaining == 0


class TestDailyReset:
    @pytest.mark.asyncio
    async def test_separate_dates_treated_as_separate_rows(self, session):
        """
        Simulate a reset by creating daily_usage rows for two different dates
        and confirming the today() row always starts at 0.
        The actual reset is implicit: each calendar day gets its own row.
        """
        from app.database.models import DailyUsage
        from datetime import date

        user = await _make_user(session, 30_001)
        yesterday = date.today() - timedelta(days=1)

        # Manually insert a "yesterday" row with 5 uses
        old_row = DailyUsage(user_id=user.id, usage_count=5, reset_date=yesterday)
        session.add(old_row)
        await session.flush()

        # Today's count should still be 0
        count_today = await repo.get_daily_uses_count(session, user.id)
        assert count_today == 0

    @pytest.mark.asyncio
    async def test_increment_on_new_day_resets(self, session):
        from app.database.models import DailyUsage
        from datetime import date

        user = await _make_user(session, 30_002)
        yesterday = date.today() - timedelta(days=1)

        old_row = DailyUsage(user_id=user.id, usage_count=99, reset_date=yesterday)
        session.add(old_row)
        await session.flush()

        new_count = await repo.increment_daily_usage(session, user.id)
        assert new_count == 1


# ─────────────────────────────────────────
# Feature 8 · Subscription restrictions
# ─────────────────────────────────────────

class TestSubscriptionRestrictions:
    @pytest.mark.asyncio
    async def test_no_subscription_by_default(self, session):
        user = await _make_user(session, 40_001)
        sub = await repo.active_subscription(session, user.id)
        assert sub is None

    @pytest.mark.asyncio
    async def test_grant_subscription_creates_active_sub(self, session):
        user = await _make_user(session, 40_002)
        sub = await repo.grant_subscription(session, user.id, 30)
        assert sub is not None
        assert sub.active is True

    @pytest.mark.asyncio
    async def test_active_subscription_expires_in_future(self, session):
        from datetime import datetime, timezone
        user = await _make_user(session, 40_003)
        await repo.grant_subscription(session, user.id, 30)
        sub = await repo.active_subscription(session, user.id)
        assert sub.expires_at > datetime.now(timezone.utc)

    @pytest.mark.asyncio
    async def test_revoke_removes_active_sub(self, session):
        user = await _make_user(session, 40_004)
        await repo.grant_subscription(session, user.id, 30)
        await repo.revoke_subscription(session, user.id)
        sub = await repo.active_subscription(session, user.id)
        assert sub is None


# ─────────────────────────────────────────
# Feature 9 · Referral rewards
# ─────────────────────────────────────────

class TestReferralRewards:
    @pytest.mark.asyncio
    async def test_referral_reward_grants_subscription_to_both(self, session):
        from datetime import datetime, timezone
        from app.config import settings

        referrer = await _make_user(session, 50_001)
        referred = await _make_user(session, 50_002)

        ref = await repo.link_referral(
            session, referred_user=referred, referrer=referrer,
            reward_days=settings.REFERRAL_REWARD_DAYS,
        )
        assert ref is not None

        await repo.grant_subscription(session, referrer.id, settings.REFERRAL_REWARD_DAYS, source="referral")
        await repo.grant_subscription(session, referred.id, settings.REFERRAL_BONUS_DAYS, source="referral_bonus")
        await repo.mark_referral_rewarded(session, ref.id)

        referrer_sub = await repo.active_subscription(session, referrer.id)
        referred_sub = await repo.active_subscription(session, referred.id)
        assert referrer_sub is not None
        assert referred_sub is not None
        assert referrer_sub.source == "referral"
        assert referred_sub.source == "referral_bonus"

    @pytest.mark.asyncio
    async def test_referral_self_link_rejected(self, session):
        user = await _make_user(session, 50_003)
        ref = await repo.link_referral(session, referred_user=user, referrer=user, reward_days=3)
        assert ref is None

    @pytest.mark.asyncio
    async def test_double_referral_rejected(self, session):
        r1 = await _make_user(session, 50_004)
        r2 = await _make_user(session, 50_005)
        new_user = await _make_user(session, 50_006)

        ref1 = await repo.link_referral(session, referred_user=new_user, referrer=r1, reward_days=3)
        assert ref1 is not None
        ref2 = await repo.link_referral(session, referred_user=new_user, referrer=r2, reward_days=3)
        assert ref2 is None
