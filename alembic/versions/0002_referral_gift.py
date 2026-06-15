"""referral system and premium gifting

Revision ID: 0002_referral_gift
Revises: 0001_initial
Create Date: 2026-06-11
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_referral_gift"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- users: referral code + who referred them ---
    op.add_column("users", sa.Column("referral_code", sa.String(16), nullable=True))
    op.create_unique_constraint("uq_users_referral_code", "users", ["referral_code"])
    op.create_index("ix_users_referral_code", "users", ["referral_code"])

    op.add_column("users", sa.Column("referred_by_id", sa.BigInteger, nullable=True))
    op.create_index("ix_users_referred_by_id", "users", ["referred_by_id"])
    op.create_foreign_key(
        "fk_users_referred_by_id_users",
        "users", "users",
        ["referred_by_id"], ["id"],
        ondelete="SET NULL",
    )

    # --- referrals ---
    op.create_table(
        "referrals",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("referrer_id", sa.BigInteger, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("referred_id", sa.BigInteger, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True),
        sa.Column("reward_days", sa.Integer, nullable=False, server_default="0"),
        sa.Column("rewarded", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # --- gifts ---
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


def downgrade() -> None:
    op.drop_table("gifts")
    op.drop_table("referrals")

    op.drop_constraint("fk_users_referred_by_id_users", "users", type_="foreignkey")
    op.drop_index("ix_users_referred_by_id", table_name="users")
    op.drop_column("users", "referred_by_id")

    op.drop_index("ix_users_referral_code", table_name="users")
    op.drop_constraint("uq_users_referral_code", "users", type_="unique")
    op.drop_column("users", "referral_code")
