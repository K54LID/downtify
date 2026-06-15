"""daily streak system

Revision ID: 0004_daily_streak
Revises: 0003_daily_usage
Create Date: 2026-06-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "0004_daily_streak"
down_revision = "0003_daily_usage"
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

    if not _table_exists(conn, "daily_streaks"):
        op.create_table(
            "daily_streaks",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column(
                "user_id",
                sa.BigInteger(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
                unique=True,
            ),
            sa.Column("current_streak", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("longest_streak", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_active_date", sa.Date(), nullable=True),
            sa.Column("rewards_granted", sa.String(64), nullable=False, server_default=""),
        )

    if not _index_exists(conn, "ix_daily_streaks_user_id"):
        op.create_index("ix_daily_streaks_user_id", "daily_streaks", ["user_id"])


def downgrade() -> None:
    op.drop_table("daily_streaks")
