"""loyalty points ledger, redemptions, bonus spins, user badges

Revision ID: 0006_loyalty_points_profile
Revises: 0005_achievements_spin
Create Date: 2026-06-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "0006_loyalty_points_profile"
down_revision = "0005_achievements_spin"
branch_labels = None
depends_on = None


def _table_exists(conn, name: str) -> bool:
    return bool(conn.execute(
        text("SELECT 1 FROM information_schema.tables WHERE table_name=:n"),
        {"n": name},
    ).fetchone())


def _index_exists(conn, name: str) -> bool:
    return bool(conn.execute(
        text("SELECT 1 FROM pg_indexes WHERE indexname=:n"),
        {"n": name},
    ).fetchone())


def upgrade() -> None:
    conn = op.get_bind()

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
    if not _index_exists(conn, "ix_points_ledger_user_id"):
        op.create_index("ix_points_ledger_user_id", "points_ledger", ["user_id"])
    if not _index_exists(conn, "ix_points_ledger_created_at"):
        op.create_index("ix_points_ledger_created_at", "points_ledger", ["created_at"])

    if not _table_exists(conn, "points_redemptions"):
        op.create_table(
            "points_redemptions",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("item_key", sa.String(32), nullable=False),
            sa.Column("cost", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
    if not _index_exists(conn, "ix_points_redemptions_user_id"):
        op.create_index("ix_points_redemptions_user_id", "points_redemptions", ["user_id"])

    if not _table_exists(conn, "bonus_spins"):
        op.create_table(
            "bonus_spins",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        )
    if not _index_exists(conn, "ix_bonus_spins_user_id"):
        op.create_index("ix_bonus_spins_user_id", "bonus_spins", ["user_id"])

    if not _table_exists(conn, "user_badges"):
        op.create_table(
            "user_badges",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("badge_key", sa.String(32), nullable=False),
            sa.Column("awarded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("user_id", "badge_key", name="uq_user_badge"),
        )
    if not _index_exists(conn, "ix_user_badges_user_id"):
        op.create_index("ix_user_badges_user_id", "user_badges", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_user_badges_user_id", table_name="user_badges")
    op.drop_table("user_badges")

    op.drop_index("ix_bonus_spins_user_id", table_name="bonus_spins")
    op.drop_table("bonus_spins")

    op.drop_index("ix_points_redemptions_user_id", table_name="points_redemptions")
    op.drop_table("points_redemptions")

    op.drop_index("ix_points_ledger_created_at", table_name="points_ledger")
    op.drop_index("ix_points_ledger_user_id", table_name="points_ledger")
    op.drop_table("points_ledger")
