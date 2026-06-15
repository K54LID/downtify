from __future__ import annotations
from datetime import datetime, timedelta, timezone, date
import secrets
import string
from typing import Iterable
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import (
    User, Subscription, Payment, Download, SearchHistory,
    AdminAction, Broadcast, AuditLog, ErrorLog, Referral, DailyUsage,
    SpinHistory, BonusSpin,
)


# ---------- Users ----------
async def get_or_create_user(session: AsyncSession, tg_id: int, **kwargs) -> User:
    res = await session.execute(select(User).where(User.telegram_id == tg_id))
    user = res.scalar_one_or_none()
    if user:
        changed = False
        for k, v in kwargs.items():
            if k == "language":
                # Never overwrite an already-persisted language preference
                # with the Telegram client's locale; only set it if the
                # user has no language stored yet.
                if v is not None and not user.language:
                    setattr(user, k, v); changed = True
                continue
            if v is not None and getattr(user, k, None) != v:
                setattr(user, k, v); changed = True
        user.last_seen_at = datetime.now(timezone.utc)
        if changed:
            await session.flush()
        return user
    user = User(telegram_id=tg_id, **kwargs)
    session.add(user)
    await session.flush()
    return user


async def set_language(session: AsyncSession, user_id: int, lang: str) -> None:
    await session.execute(update(User).where(User.id == user_id).values(language=lang))


async def list_users(session: AsyncSession, limit: int = 50, offset: int = 0) -> list[User]:
    res = await session.execute(select(User).order_by(User.created_at.desc()).limit(limit).offset(offset))
    return list(res.scalars().all())


async def count_users(session: AsyncSession) -> int:
    return (await session.execute(select(func.count(User.id)))).scalar_one()


async def get_user_by_tg(session: AsyncSession, tg_id: int) -> User | None:
    return (await session.execute(select(User).where(User.telegram_id == tg_id))).scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    return (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()


async def all_user_tg_ids(session: AsyncSession) -> list[int]:
    res = await session.execute(select(User.telegram_id).where(User.is_banned.is_(False)))
    return [row[0] for row in res.all()]


# ---------- Subscription ----------
async def active_subscription(session: AsyncSession, user_id: int) -> Subscription | None:
    now = datetime.now(timezone.utc)
    res = await session.execute(
        select(Subscription)
        .where(Subscription.user_id == user_id, Subscription.active.is_(True), Subscription.expires_at > now)
        .order_by(Subscription.expires_at.desc())
    )
    return res.scalars().first()


async def grant_subscription(session: AsyncSession, user_id: int, days: int, source: str = "stars") -> Subscription:
    current = await active_subscription(session, user_id)
    base = current.expires_at if current else datetime.now(timezone.utc)
    if current:
        current.expires_at = base + timedelta(days=days)
        await session.flush()
        return current
    sub = Subscription(
        user_id=user_id,
        started_at=datetime.now(timezone.utc),
        expires_at=base + timedelta(days=days),
        source=source,
        active=True,
    )
    session.add(sub)
    await session.flush()
    return sub


async def revoke_subscription(session: AsyncSession, user_id: int) -> int:
    res = await session.execute(
        update(Subscription).where(Subscription.user_id == user_id, Subscription.active.is_(True)).values(active=False)
    )
    return res.rowcount or 0


async def count_active_subscriptions(session: AsyncSession) -> int:
    now = datetime.now(timezone.utc)
    return (await session.execute(
        select(func.count(Subscription.id)).where(Subscription.active.is_(True), Subscription.expires_at > now)
    )).scalar_one()


async def count_expired_subscriptions(session: AsyncSession) -> int:
    now = datetime.now(timezone.utc)
    return (await session.execute(
        select(func.count(Subscription.id)).where(Subscription.expires_at <= now)
    )).scalar_one()


# ---------- Payments ----------
async def add_payment(session: AsyncSession, user_id: int, charge_id: str, stars: int, payload: str) -> Payment:
    p = Payment(user_id=user_id, charge_id=charge_id, stars=stars, payload=payload)
    session.add(p)
    await session.flush()
    return p


async def total_revenue_stars(session: AsyncSession) -> int:
    return (await session.execute(select(func.coalesce(func.sum(Payment.stars), 0)))).scalar_one()


# ---------- Downloads ----------
async def add_download(session: AsyncSession, user_id: int, platform: str, url: str,
                       title: str | None, kind: str, success: bool = True) -> Download:
    d = Download(user_id=user_id, platform=platform, url=url, title=title, kind=kind, success=success)
    session.add(d)
    await session.flush()
    return d


async def count_successful_downloads(session: AsyncSession, user_id: int) -> int:
    return (await session.execute(
        select(func.count(Download.id)).where(Download.user_id == user_id, Download.success.is_(True))
    )).scalar_one()


async def recent_downloads(session: AsyncSession, user_id: int, limit: int = 20) -> list[Download]:
    res = await session.execute(
        select(Download).where(Download.user_id == user_id).order_by(Download.created_at.desc()).limit(limit)
    )
    return list(res.scalars().all())


async def count_downloads_since(session: AsyncSession, since: datetime) -> int:
    return (await session.execute(
        select(func.count(Download.id)).where(Download.created_at >= since)
    )).scalar_one()


async def top_platforms(session: AsyncSession) -> list[tuple[str, int]]:
    res = await session.execute(
        select(Download.platform, func.count(Download.id)).group_by(Download.platform).order_by(func.count(Download.id).desc())
    )
    return [(r[0], r[1]) for r in res.all()]


async def top_countries(session: AsyncSession, limit: int = 5) -> list[tuple[str, int]]:
    res = await session.execute(
        select(User.country, func.count(User.id))
        .where(User.country.is_not(None)).group_by(User.country)
        .order_by(func.count(User.id).desc()).limit(limit)
    )
    return [(r[0], r[1]) for r in res.all()]


async def count_new_users_since(session: AsyncSession, since: datetime) -> int:
    return (await session.execute(
        select(func.count(User.id)).where(User.created_at >= since)
    )).scalar_one()


# ---------- Search ----------
async def add_search(session: AsyncSession, user_id: int, query: str) -> None:
    session.add(SearchHistory(user_id=user_id, query=query))
    await session.flush()


async def count_searches(session: AsyncSession, user_id: int) -> int:
    return (await session.execute(
        select(func.count(SearchHistory.id)).where(SearchHistory.user_id == user_id)
    )).scalar_one()


# ---------- Admin ----------
async def log_admin_action(session: AsyncSession, admin_id: int, action: str,
                           target_user_id: int | None = None, payload: str | None = None) -> None:
    session.add(AdminAction(admin_id=admin_id, action=action, target_user_id=target_user_id, payload=payload))
    await session.flush()


async def add_broadcast(session: AsyncSession, admin_id: int, message: str,
                        total: int, success: int, failed: int) -> Broadcast:
    b = Broadcast(admin_id=admin_id, message=message, total=total, success=success, failed=failed)
    session.add(b)
    await session.flush()
    return b


async def log_audit(session: AsyncSession, user_id: int | None, event: str, data: str | None = None) -> None:
    session.add(AuditLog(user_id=user_id, event=event, data=data))
    await session.flush()


async def log_error(session: AsyncSession, user_id: int | None, error: str, context: str | None = None) -> None:
    session.add(ErrorLog(user_id=user_id, error=error[:4000], context=(context or "")[:4000]))
    await session.flush()


# ---------- Referral system ----------
_CODE_ALPHABET = string.ascii_uppercase + string.digits
_AMBIGUOUS = set("0O1IL")
_CODE_ALPHABET = "".join(c for c in _CODE_ALPHABET if c not in _AMBIGUOUS)


async def get_or_create_referral_code(session: AsyncSession, user_id: int, length: int = 8) -> str:
    """Return the user's referral code, generating a unique one if absent."""
    res = await session.execute(select(User.referral_code).where(User.id == user_id))
    existing = res.scalar_one_or_none()
    if existing:
        return existing

    for _ in range(20):
        candidate = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(length))
        clash = await session.execute(select(User.id).where(User.referral_code == candidate))
        if clash.scalar_one_or_none() is None:
            await session.execute(
                update(User).where(User.id == user_id).values(referral_code=candidate)
            )
            await session.flush()
            return candidate
    raise RuntimeError("Failed to generate a unique referral code")


async def get_user_by_referral_code(session: AsyncSession, code: str) -> User | None:
    code = code.strip().upper()
    if not code:
        return None
    res = await session.execute(select(User).where(User.referral_code == code))
    return res.scalar_one_or_none()


async def link_referral(
    session: AsyncSession, referred_user: User, referrer: User, reward_days: int
) -> Referral | None:
    """
    Link `referred_user` as referred by `referrer`, and record a Referral row.

    Anti-abuse:
    - A user cannot refer themselves.
    - A user can only ever be referred once (referred_id is unique).
    - A referral chain loop (A -> B -> A) is prevented implicitly because
      `referred_by_id` can only be set once, on a brand-new account.
    Returns the created Referral row, or None if the link was rejected
    (self-referral or the user was already referred).
    """
    if referred_user.id == referrer.id:
        return None
    if referred_user.referred_by_id is not None:
        return None

    existing = await session.execute(
        select(Referral).where(Referral.referred_id == referred_user.id)
    )
    if existing.scalar_one_or_none() is not None:
        return None

    referred_user.referred_by_id = referrer.id
    ref = Referral(
        referrer_id=referrer.id,
        referred_id=referred_user.id,
        reward_days=reward_days,
        rewarded=False,
    )
    session.add(ref)
    await session.flush()
    return ref


async def mark_referral_rewarded(session: AsyncSession, referral_id: int) -> None:
    await session.execute(
        update(Referral).where(Referral.id == referral_id).values(rewarded=True)
    )


async def count_referrals(session: AsyncSession, user_id: int) -> int:
    return (await session.execute(
        select(func.count(Referral.id)).where(Referral.referrer_id == user_id)
    )).scalar_one()


async def count_rewarded_referrals(session: AsyncSession, user_id: int) -> int:
    return (await session.execute(
        select(func.count(Referral.id)).where(
            Referral.referrer_id == user_id, Referral.rewarded.is_(True)
        )
    )).scalar_one()


async def list_referrals(session: AsyncSession, user_id: int, limit: int = 20) -> list[Referral]:
    res = await session.execute(
        select(Referral)
        .where(Referral.referrer_id == user_id)
        .order_by(Referral.created_at.desc())
        .limit(limit)
    )
    return list(res.scalars().all())


async def total_referral_count(session: AsyncSession) -> int:
    return (await session.execute(select(func.count(Referral.id)))).scalar_one()


# ---------- Daily Usage ----------

def _today_utc() -> date:
    return datetime.now(timezone.utc).date()


async def _get_or_create_daily_usage(session: AsyncSession, user_id: int) -> DailyUsage:
    today = _today_utc()
    row = (await session.execute(
        select(DailyUsage).where(
            DailyUsage.user_id == user_id,
            DailyUsage.reset_date == today,
        )
    )).scalar_one_or_none()
    if row is None:
        row = DailyUsage(user_id=user_id, usage_count=0, reset_date=today)
        session.add(row)
        await session.flush()
    return row


async def get_daily_uses_count(session: AsyncSession, user_id: int) -> int:
    """Return how many free uses the user has consumed today."""
    row = await _get_or_create_daily_usage(session, user_id)
    return row.usage_count


async def increment_daily_usage(session: AsyncSession, user_id: int) -> int:
    """Increment today's usage count and return the NEW count."""
    row = await _get_or_create_daily_usage(session, user_id)
    row.usage_count += 1
    await session.flush()
    return row.usage_count


async def get_daily_uses_remaining(session: AsyncSession, user_id: int, daily_limit: int) -> int:
    """Return how many free uses remain today (never negative)."""
    used = await get_daily_uses_count(session, user_id)
    return max(0, daily_limit - used)


# ---------- Analytics ----------

async def count_all_downloads(session: AsyncSession) -> int:
    """Total successful downloads across all users and all time."""
    return (await session.execute(
        select(func.count(Download.id)).where(Download.success.is_(True))
    )).scalar_one()


async def count_distinct_active_users_since(session: AsyncSession, since: datetime) -> int:
    """
    Count users who were active (sent at least one update) since `since`.
    Uses last_seen_at which is updated on every middleware call.
    """
    return (await session.execute(
        select(func.count(User.id)).where(User.last_seen_at >= since)
    )).scalar_one()


async def count_rewarded_referrals_all(session: AsyncSession) -> int:
    """Total referrals that have been rewarded (i.e. converted) across all users."""
    return (await session.execute(
        select(func.count(Referral.id)).where(Referral.rewarded.is_(True))
    )).scalar_one()


async def count_free_users_active_today(session: AsyncSession) -> int:
    """
    Number of distinct non-premium users who consumed at least one free use today.
    Joins daily_usage to subscriptions: a user is 'free' here if they had no
    active subscription as of today (best-effort: checks current state).
    """
    today = _today_utc()
    # All users who have a daily_usage row for today with count > 0
    active_free_subq = (
        select(DailyUsage.user_id)
        .where(DailyUsage.reset_date == today, DailyUsage.usage_count > 0)
        .subquery()
    )
    now = datetime.now(timezone.utc)
    # Exclude users who currently have an active subscription
    active_sub_subq = (
        select(Subscription.user_id)
        .where(Subscription.active.is_(True), Subscription.expires_at > now)
        .subquery()
    )
    from sqlalchemy import not_, exists
    result = await session.execute(
        select(func.count()).select_from(active_free_subq).where(
            ~active_free_subq.c.user_id.in_(
                select(active_sub_subq.c.user_id)
            )
        )
    )
    return result.scalar_one()


async def sum_free_uses_today(session: AsyncSession) -> int:
    """Total free uses consumed today across all non-premium users."""
    today = _today_utc()
    return (await session.execute(
        select(func.coalesce(func.sum(DailyUsage.usage_count), 0))
        .where(DailyUsage.reset_date == today)
    )).scalar_one()


# ---------- Bonus Free Uses ----------

async def add_streak_bonus_uses(session: AsyncSession, user_id: int, count: int) -> None:
    """Add `count` bonus free uses to today's daily usage row by reducing usage_count."""
    row = await _get_or_create_daily_usage(session, user_id)
    # Reduce count (can go below 0; get_daily_uses_remaining clamps to 0)
    row.usage_count = max(0, row.usage_count - count)
    await session.flush()


# ---------- Daily Spin Wheel ----------

# Reward catalog: code -> (i18n label key, weight for random selection)
SPIN_REWARDS: list[dict] = [
    {"code": "free_use_1", "label_key": "spin_reward_free_use_1", "weight": 30},
    {"code": "free_use_2", "label_key": "spin_reward_free_use_2", "weight": 20},
    {"code": "free_use_5", "label_key": "spin_reward_free_use_5", "weight": 8},
    {"code": "premium_1day", "label_key": "spin_reward_premium_1day", "weight": 6},
    {"code": "premium_3day", "label_key": "spin_reward_premium_3day", "weight": 2},
]


async def last_spin(session: AsyncSession, user_id: int) -> SpinHistory | None:
    res = await session.execute(
        select(SpinHistory).where(SpinHistory.user_id == user_id)
        .order_by(SpinHistory.spun_at.desc()).limit(1)
    )
    return res.scalars().first()


async def can_spin(session: AsyncSession, user_id: int, cooldown_hours: int = 24) -> tuple[bool, datetime | None]:
    """
    Returns (can_spin, next_available_at). next_available_at is None if the
    user can spin right now.
    """
    last = await last_spin(session, user_id)
    if last is None:
        return True, None
    next_at = last.spun_at + timedelta(hours=cooldown_hours)
    now = datetime.now(timezone.utc)
    if now >= next_at:
        return True, None
    return False, next_at


def pick_spin_reward() -> dict:
    """Pick a random reward from SPIN_REWARDS, weighted."""
    import random
    total = sum(r["weight"] for r in SPIN_REWARDS)
    roll = random.uniform(0, total)
    upto = 0.0
    for r in SPIN_REWARDS:
        upto += r["weight"]
        if roll <= upto:
            return r
    return SPIN_REWARDS[-1]


async def record_spin(session: AsyncSession, user_id: int, reward_code: str, reward_label: str) -> SpinHistory:
    row = SpinHistory(user_id=user_id, reward_code=reward_code, reward_label=reward_label)
    session.add(row)
    await session.flush()
    return row


# ---------- Leaderboards ----------

def _period_start(period: str) -> datetime | None:
    """Return the start datetime for 'weekly' / 'monthly' / 'all_time' periods."""
    now = datetime.now(timezone.utc)
    if period == "weekly":
        start = now - timedelta(days=7)
        return start
    if period == "monthly":
        start = now - timedelta(days=30)
        return start
    return None  # all_time


async def leaderboard_most_downloads(session: AsyncSession, period: str, limit: int = 10) -> list[tuple[int, int]]:
    """Returns list of (user_id, count) ordered by download count desc."""
    since = _period_start(period)
    stmt = select(Download.user_id, func.count(Download.id).label("cnt")).where(
        Download.success.is_(True)
    )
    if since is not None:
        stmt = stmt.where(Download.created_at >= since)
    stmt = stmt.group_by(Download.user_id).order_by(func.count(Download.id).desc()).limit(limit)
    res = await session.execute(stmt)
    return [(r[0], r[1]) for r in res.all()]


async def leaderboard_most_referrals(session: AsyncSession, period: str, limit: int = 10) -> list[tuple[int, int]]:
    """Returns list of (referrer_user_id, rewarded_referral_count) ordered desc."""
    since = _period_start(period)
    stmt = select(Referral.referrer_id, func.count(Referral.id).label("cnt")).where(
        Referral.rewarded.is_(True)
    )
    if since is not None:
        stmt = stmt.where(Referral.created_at >= since)
    stmt = stmt.group_by(Referral.referrer_id).order_by(func.count(Referral.id).desc()).limit(limit)
    res = await session.execute(stmt)
    return [(r[0], r[1]) for r in res.all()]


async def user_rank_in_leaderboard(
    session: AsyncSession, category: str, period: str, user_id: int, top_n: int = 100
) -> tuple[int | None, int]:
    """
    Returns (rank, value) for `user_id` within the given category/period,
    where rank is 1-based, or (None, 0) if the user has no qualifying entries.
    Looks within the top `top_n` entries for efficiency.
    """
    fetchers = {
        "downloads": leaderboard_most_downloads,
        "referrals": leaderboard_most_referrals,
    }
    fetcher = fetchers[category]
    rows = await fetcher(session, period, limit=top_n)
    for i, (uid, value) in enumerate(rows, 1):
        if uid == user_id:
            return i, value
    return None, 0

# ---------- Bonus Spins ----------

async def claim_bonus_spin(session: AsyncSession, user_id: int) -> BonusSpin | None:
    """Mark the oldest unused bonus spin as used. Returns it, or None if none available."""
    now = datetime.now(timezone.utc)
    res = await session.execute(
        select(BonusSpin)
        .where(BonusSpin.user_id == user_id, BonusSpin.used_at.is_(None))
        .order_by(BonusSpin.granted_at.asc())
        .limit(1)
    )
    row = res.scalars().first()
    if row:
        row.used_at = now
        await session.flush()
    return row


async def count_unused_bonus_spins(session: AsyncSession, user_id: int) -> int:
    return (await session.execute(
        select(func.count(BonusSpin.id))
        .where(BonusSpin.user_id == user_id, BonusSpin.used_at.is_(None))
    )).scalar_one()
