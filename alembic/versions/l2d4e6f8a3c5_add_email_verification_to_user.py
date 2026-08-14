"""add email verification fields to user

Additive schema change: tracks whether a user verified their email and stores
the (hashed) verification token plus when it was issued, so the Resend-based
verification flow can be implemented without a frontend.

Revision ID: l2d4e6f8a3c5
Revises: k1c3e5f7a2b4
Create Date: 2026-08-14 13:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "l2d4e6f8a3c5"
down_revision: Union[str, Sequence[str], None] = "k1c3e5f7a2b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "user",
        sa.Column("email_verification_token_hash", sa.String(), nullable=True),
    )
    op.add_column(
        "user",
        sa.Column("email_verification_sent_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        op.f("ix_user_email_verified"),
        "user",
        ["email_verified"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_user_email_verified"), table_name="user")
    op.drop_column("user", "email_verification_sent_at")
    op.drop_column("user", "email_verification_token_hash")
    op.drop_column("user", "email_verified")
