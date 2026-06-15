"""remove daily streaks, premium gifting, loyalty points, user badges (profile/streak/gift/loyalty removal)

Revision ID: 0007_remove_streak_gift_loyalty
Revises: 0006_loyalty_points_profile
Create Date: 2026-06-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "0007_remove_streak_gift_loyalty"
down_revision = "0006_loyalty_points_profile"
branch_labels = None
depends_on = None


def _table_exists(conn, name: str) -> bool:
    return bool(conn.execute(
        text("SELECT 1 FROM information_schema.tables WHERE table_name=:n"),
        {"n": name},
    ).fetchone())


def upgrade() -> None:
    conn = op.get_bind()

    # ---- Loyalty points ledger / redemptions / balances ----
    if _table_exists(conn, "points_ledger"):
        op.drop_index("ix_points_ledger_created_at", table_name="points_ledger")
        op.drop_index("ix_points_ledger_user_id", table_name="points_ledger")
        op.drop_table("points_ledger")

    if _table_exists(conn, "points_redemptions"):
        op.drop_index("ix_points_redemptions_user_id", table_name="points_redemptions")
        op.drop_table("points_redemptions")

    if _table_exists(conn, "loyalty_points"):
        op.drop_index("ix_loyalty_points_user_id", table_name="loyalty_points")
        op.drop_table("loyalty_points")

    # ---- User badges (only ever awarded via points redemption) ----
    if _table_exists(conn, "user_badges"):
        op.drop_index("ix_user_badges_user_id", table_name="user_badges")
        op.drop_table("user_badges")

    # ---- Premium gifting ----
    if _table_exists(conn, "gifts"):
        op.drop_table("gifts")

    # ---- Daily streak tracking ----
    if _table_exists(conn, "daily_streaks"):
        op.drop_index("ix_daily_streaks_user_id", table_name="daily_streaks")
        op.drop_table("daily_streaks")


def downgrade() -> None:
    conn = op.get_bind()

    if not _table_exists(conn, "daily_streaks"):
        op.create_table(
            "daily_streaks",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
            sa.Column("current_streak", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("longest_streak", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_active_date", sa.Date(), nullable=True),
            sa.Column("rewards_granted", sa.String(64), nullable=False, server_default=""),
        )
        op.create_index("ix_daily_streaks_user_id", "daily_streaks", ["user_id"])

    if not _table_exists(conn, "gifts"):
        op.create_table(
            "gifts",
            sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
            sa.Column("code", sa.String(24), nullable=False, unique=True, index=True),
            sa.Column("sender_id", sa.BigInteger, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("recipient_id", sa.BigInteger, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("days", sa.Integer, nullable=False),
            sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        )

    if not _table_exists(conn, "user_badges"):
        op.create_table(
            "user_badges",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("badge_key", sa.String(32), nullable=False),
            sa.Column("awarded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("user_id", "badge_key", name="uq_user_badge"),
        )
        op.create_index("ix_user_badges_user_id", "user_badges", ["user_id"])

    if not _table_exists(conn, "loyalty_points"):
        op.create_table(
            "loyalty_points",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
            sa.Column("points", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_loyalty_points_user_id", "loyalty_points", ["user_id"])

    if not _table_exists(conn, "points_redemptions"):
        op.create_table(
            "points_redemptions",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("item_key", sa.String(32), nullable=False),
            sa.Column("cost", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_points_redemptions_user_id", "points_redemptions", ["user_id"])

    if not _table_exists(conn, "points_ledger"):
        op.create_table(
            "points_ledger",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("delta", sa.Integer(), nullable=False),
            sa.Column("balance_after", sa.Integer(), nullable=False),
            sa.Column("reason", sa.String(64), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_points_ledger_user_id", "points_ledger", ["user_id"])
        op.create_index("ix_points_ledger_created_at", "points_ledger", ["created_at"])
