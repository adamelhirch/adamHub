"""add item image urls

Revision ID: f1d2a8c4b7e1
Revises: ab92d3f41c10
Create Date: 2026-03-16 02:45:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f1d2a8c4b7e1"
down_revision: str | Sequence[str] | None = "ab92d3f41c10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("groceryitem", sa.Column("image_url", sa.String(), nullable=True))
    op.add_column("pantryitem", sa.Column("image_url", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("pantryitem", "image_url")
    op.drop_column("groceryitem", "image_url")
