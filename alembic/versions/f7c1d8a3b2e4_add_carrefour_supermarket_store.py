"""add carrefour to supermarket store enum

Revision ID: f7c1d8a3b2e4
Revises: e5b2a7c91d83
Create Date: 2026-05-03 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "f7c1d8a3b2e4"
down_revision: Union[str, Sequence[str], None] = "e5b2a7c91d83"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("COMMIT")
        op.execute("ALTER TYPE supermarketstore ADD VALUE IF NOT EXISTS 'CARREFOUR'")


def downgrade() -> None:
    # Postgres does not support removing an enum value cleanly; leave in place.
    pass
