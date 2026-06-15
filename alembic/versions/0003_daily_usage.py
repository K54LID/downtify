"""daily free usage tracking

Revision ID: 0003_daily_usage
Revises: 0002_referral_gift
Create Date: 2026-06-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "0003_daily_usage"
down_revision = "0002_referral_gift"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # Create table only if it doesn't already exist
    table_exists = conn.execute(
        text("SELECT 1 FROM information_schema.tables WHERE table_name='daily_usage'")
    ).fetchone()

    if not table_exists:
        op.create_table(
            "daily_usage",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column(
                "user_id",
                sa.BigInteger(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("reset_date", sa.Date(), nullable=False),
            sa.UniqueConstraint("user_id", "reset_date", name="uq_daily_usage_user_date"),
        )

    # Create index only if it doesn't already exist
    index_exists = conn.execute(
        text("SELECT 1 FROM pg_indexes WHERE indexname='ix_daily_usage_user_id'")
    ).fetchone()

    if not index_exists:
        op.create_index("ix_daily_usage_user_id", "daily_usage", ["user_id"])


def downgrade() -> None:
    op.drop_table("daily_usage")
