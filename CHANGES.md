# Changes — Referral System & Premium Gifting

This delivery implements two of the requested systems end-to-end:
**Referral System** and **Gift Premium Feature**, fully integrated into the
existing Downtify bot (aiogram 3 + SQLAlchemy 2 + Alembic + Postgres).

The remaining requested systems (loyalty points, achievements, streaks, spin
wheel, statistics dashboard, broader UX/performance pass) are **not** included
in this delivery — see "Out of scope" at the bottom.

## 1. Database changes

**`app/database/models.py`**
- `User`: new `referral_code` (unique, indexed) and `referred_by_id`
  (self-referential FK, `SET NULL` on delete) columns.
- New `Referral` table: `referrer_id`, `referred_id` (unique — a user can be
  referred only once), `reward_days`, `rewarded`, `created_at`.
- New `Gift` table: `code` (unique, `GIFT-XXXXXXXXXX`), `sender_id`,
  `recipient_id` (nullable), `days`, `status`
  (`pending|claimed|expired|cancelled`), `created_at`, `claimed_at`,
  `expires_at`.

**`alembic/versions/0002_referral_gift.py`**
- Adds the above columns/tables and indexes/constraints, with a full
  `downgrade()`.

## 2. Configuration (`app/config.py`)

New settings:
- `REFERRAL_REWARD_DAYS` (default 3) — Premium days granted to the referrer.
- `REFERRAL_BONUS_DAYS` (default 1) — Premium days granted to the new user.
- `GIFT_EXPIRY_DAYS` (default 30) — gift code validity window.

## 3. Repository layer (`app/repositories/repo.py`)

**Referral**
- `get_or_create_referral_code` — generates a unique 8-char code (unambiguous
  alphabet, excludes `0/O/1/I/L`).
- `get_user_by_referral_code` — case-insensitive lookup.
- `link_referral` — links a new user to a referrer; rejects self-referral and
  re-referral (each user can only ever be referred once).
- `mark_referral_rewarded`, `count_referrals`, `count_rewarded_referrals`,
  `list_referrals`, `total_referral_count`.

**Gifting**
- `create_gift` — generates a unique `GIFT-XXXXXXXXXX` code with an expiry.
- `get_gift_by_code` — case-insensitive lookup.
- `claim_gift` — atomic claim with full anti-abuse checks; returns
  `(success, reason)` where `reason` is one of `ok`, `already_claimed`,
  `expired`, `self_gift`, `wrong_recipient`, `cancelled`.
- `list_sent_gifts`, `list_received_gifts`, `expire_stale_gifts`,
  `total_gifts_sent`, `total_gift_days_claimed`.

**Supporting helpers**
- `deduct_subscription_days` — shortens a user's active subscription by N
  days (used to "pay" for a gift); fails safely if the user doesn't have
  enough remaining days.
- `count_successful_downloads`, `get_user_by_id`.

## 4. Handlers

**`app/handlers/common.py`**
- `/start ref_<CODE>` deep link is now parsed via `CommandStart(deep_link=True)`.
  - Looks up the referrer by code, calls `link_referral`.
  - Sends `referral_applied` to new users, or `referral_self` /
    `referral_already_referred` for invalid attempts.
  - Falls through to the normal `/start` flow afterwards.

**`app/handlers/referral.py`** (new router)
- `/referral` — shows the user's referral code, shareable deep link (with a
  "Share" button that opens Telegram's native share sheet), and referral
  stats (total / rewarded).
- `/referrals` — paginated-style list (last 20) of referral history with
  status (rewarded / pending).

**`app/handlers/gifting.py`** (new router)
- `/gift` — shows a menu to gift 1 / 7 / 30 days.
- `gift:create:<days>` callback — validates the sender has enough remaining
  Premium days, deducts them, creates a gift code, and shows it to the
  sender.
- `/redeem <code>` — validates and claims a gift code, grants the days to the
  redeemer's subscription, and notifies the original sender (best-effort).
- `/gifts` — shows sent and received gift history with status.

**`app/handlers/downloads.py`**
- `_maybe_reward_referral` — on a referred user's **first successful
  download**, grants `REFERRAL_REWARD_DAYS` to the referrer and
  `REFERRAL_BONUS_DAYS` to the referred user, marks the referral as rewarded,
  logs an audit event, and sends both users a notification.

## 5. Keyboards (`app/keyboards/keyboards.py`)
- `referral_kb` — inline "Share invite link" button using Telegram's
  `t.me/share/url` deep link with a pre-filled message.
- `gift_menu_kb` — 1 / 7 / 30 day gift options.

## 6. Scheduler (`app/services/scheduler_jobs.py`, `app/main.py`)
- New `expire_gifts` job, run hourly, marks overdue `pending` gifts as
  `expired`.

## 7. Localization
- 42 new keys added to **all four** locale files (`en`, `ru`, `tr`, `ar`),
  covering referral and gift UX, errors, and statuses. Placeholder names
  verified consistent across all languages.

## 8. Bot wiring (`app/bot.py`, `app/main.py`)
- New routers `h_referral` and `h_gifting` registered in the dispatcher
  (before the catch-all download handler).
- New bot commands added to the Telegram command menu: `/referral`,
  `/referrals`, `/gift`, `/redeem`, `/gifts`.

## 9. Tests (`tests/`)
- `tests/conftest.py` — in-memory SQLite fixture (via `aiosqlite`).
- `tests/test_referral.py` — code generation/uniqueness, lookup, successful
  link, self-referral rejection, double-referral rejection, full reward
  flow, listing/ordering.
- `tests/test_gifting.py` — code generation/uniqueness, lookup, successful
  claim, self-claim rejection, double-claim rejection, expired-gift
  rejection, wrong-recipient rejection, subscription-balance deduction
  (insufficient/sufficient), full end-to-end gift flow, stale-gift expiry.
- `requirements.txt` updated with `pytest`, `pytest-asyncio`, `aiosqlite`.
- `pytest.ini` added (`asyncio_mode = auto`).

> Note: tests could not be executed in this sandbox (no network access to
> install `aiogram`/`pytest`/etc.), but all new/modified files pass
> `python -m py_compile`, all locale JSON files validate, and all
> translation key/placeholder usages were cross-checked programmatically.
> Run `pip install -r requirements.txt && pytest` in the project's normal
> environment to execute the suite.

## 10. Anti-abuse summary
- **Referral loops**: a user's `referred_by_id` can only be set once
  (enforced both by a unique constraint on `referrals.referred_id` and an
  application-level check), so A→B→A chains and repeated re-referrals are
  impossible.
- **Self-referral**: rejected if `referred_user.id == referrer.id`.
- **Reward gating**: referral rewards only fire once, on the referred user's
  first *successful* download, and `mark_referral_rewarded` prevents
  re-triggering.
- **Self-gifting**: a sender cannot redeem their own gift code.
- **Double-claiming**: gift status transitions are one-way
  (`pending → claimed/expired/cancelled`); a claimed/expired/cancelled gift
  can never be reclaimed.
- **Targeted gifts**: if a gift specifies a `recipient_id`, only that user can
  redeem it.
- **Expiry**: gifts auto-expire after `GIFT_EXPIRY_DAYS`, enforced both at
  claim-time and via an hourly background sweep.
- **Audit trail**: gift creation, gift claims, referral links, and referral
  rewards are all written to `audit_logs`.

## Out of scope (not delivered in this pass)
- Loyalty points system (#14)
- Personal statistics dashboard (#15)
- Achievements system
- Streak rewards system
- Spin wheel
- General UX improvements (#17) and performance/scalability review (#18)
- Admin dashboard additions for the new systems (referral/gift admin views)

These were deferred due to the scope of a single delivery; the data model
additions here (notably `Referral` and `Gift`, and the `audit_logs` table
already present) are designed to compose cleanly with a future loyalty-points
layer (e.g. awarding points for referrals/gifts) without rework.
