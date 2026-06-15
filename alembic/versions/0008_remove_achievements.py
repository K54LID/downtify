"""remove achievements

Revision ID: 0008_remove_achievements
Revises: 0007_remove_streak_gift_loyalty
Create Date: 2026-06-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "0008_remove_achievements"
down_revision = "0007_remove_streak_gift_loyalty"
branch_labels = None
depends_on = None


def _table_exists(conn, name: str) -> bool:
    return bool(conn.execute(
        text("SELECT 1 FROM information_schema.tables WHERE table_name=:n"),
        {"n": name},
    ).fetchone())


def upgrade() -> None:
    conn = op.get_bind()

    if _table_exists(conn, "user_achievements"):
        op.drop_index("ix_user_achievements_code", table_name="user_achievements")
        op.drop_index("ix_user_achievements_user_id", table_name="user_achievements")
        op.drop_table("user_achievements")


def downgrade() -> None:
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
        op.create_index("ix_user_achievements_user_id", "user_achievements", ["user_id"])
        op.create_index("ix_user_achievements_code", "user_achievements", ["code"])
