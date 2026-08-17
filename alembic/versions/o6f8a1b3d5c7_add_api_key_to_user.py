"""add api_key fields to user

Additive schema change: a per-user MCP/API key, stored Fernet-encrypted
(always-visible in Settings, not show-once) alongside a sha256 hash column
for O(1) auth lookup without decrypting every user's key per request.

Revision ID: o6f8a1b3d5c7
Revises: n5e7f9a3c6d8
Create Date: 2026-08-17 19:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "o6f8a1b3d5c7"
down_revision: Union[str, Sequence[str], None] = "n5e7f9a3c6d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user", sa.Column("api_key_encrypted", sa.String(), nullable=True))
    op.add_column("user", sa.Column("api_key_hash", sa.String(), nullable=True))
    op.add_column("user", sa.Column("api_key_created_at", sa.DateTime(), nullable=True))
    op.create_index(op.f("ix_user_api_key_hash"), "user", ["api_key_hash"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_user_api_key_hash"), table_name="user")
    op.drop_column("user", "api_key_created_at")
    op.drop_column("user", "api_key_hash")
    op.drop_column("user", "api_key_encrypted")
