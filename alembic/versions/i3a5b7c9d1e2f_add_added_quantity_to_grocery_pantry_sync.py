"""add added_quantity to grocerypantrysync

Revision ID: i3a5b7c9d1e2f
Revises: h2c5e8f1d4a7
Create Date: 2026-08-13 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "i3a5b7c9d1e2f"
down_revision = "h2c5e8f1d4a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "grocerypantrysync",
        sa.Column("added_quantity", sa.Float(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("grocerypantrysync", "added_quantity")
