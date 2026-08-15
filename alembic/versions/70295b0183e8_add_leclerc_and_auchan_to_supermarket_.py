"""add leclerc and auchan to supermarket store enum

Revision ID: 70295b0183e8
Revises: l2d4e6f8a3c5
Create Date: 2026-08-15 05:52:17.092352

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '70295b0183e8'
down_revision: Union[str, Sequence[str], None] = 'l2d4e6f8a3c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # Fix the prod bug where only UBEREATS and CARREFOUR were added to the
        # supermarketstore enum: writing store='leclerc'/'auchan' failed with
        # "invalid input value for enum supermarketstore".
        op.execute("COMMIT")
        op.execute("ALTER TYPE supermarketstore ADD VALUE IF NOT EXISTS 'LECLERC'")
        op.execute("ALTER TYPE supermarketstore ADD VALUE IF NOT EXISTS 'AUCHAN'")


def downgrade() -> None:
    # Postgres does not support removing an enum value cleanly; leave in place.
    pass
