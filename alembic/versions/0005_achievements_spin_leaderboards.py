"""achievements, spin wheel, loyalty points

Revision ID: 0005_achievements_spin
Revises: 0004_daily_streak
Create Date: 2026-06-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "0005_achievements_spin"
down_revision = "0004_daily_streak"
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

    if not _table_exists(conn, "user_achievements"):
        op.create_table(
            "user_achievements",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("code", sa.String(32), nullable=False),
            sa.Column("unlocked_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("user_id", "code", name="uq_user_achievement"),
        )
    if not _index_exists(conn, "ix_user_achievements_user_id"):
        op.create_index("ix_user_achievements_user_id", "user_achievements", ["user_id"])
    if not _index_exists(conn, "ix_user_achievements_code"):
        op.create_index("ix_user_achievements_code", "user_achievements", ["code"])

    if not _table_exists(conn, "loyalty_points"):
        op.create_table(
            "loyalty_points",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
            sa.Column("points", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
    if not _index_exists(conn, "ix_loyalty_points_user_id"):
        op.create_index("ix_loyalty_points_user_id", "loyalty_points", ["user_id"])

    if not _table_exists(conn, "spin_history"):
        op.create_table(
            "spin_history",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("reward_code", sa.String(32), nullable=False),
            sa.Column("reward_label", sa.String(64), nullable=False),
            sa.Column("spun_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
    if not _index_exists(conn, "ix_spin_history_user_id"):
        op.create_index("ix_spin_history_user_id", "spin_history", ["user_id"])
    if not _index_exists(conn, "ix_spin_history_spun_at"):
        op.create_index("ix_spin_history_spun_at", "spin_history", ["spun_at"])


def downgrade() -> None:
    op.drop_index("ix_spin_history_spun_at", table_name="spin_history")
    op.drop_index("ix_spin_history_user_id", table_name="spin_history")
    op.drop_table("spin_history")

    op.drop_index("ix_loyalty_points_user_id", table_name="loyalty_points")
    op.drop_table("loyalty_points")

    op.drop_index("ix_user_achievements_code", table_name="user_achievements")
    op.drop_index("ix_user_achievements_user_id", table_name="user_achievements")
    op.drop_table("user_achievements")
