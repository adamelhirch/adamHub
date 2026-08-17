"""add customer_uuid to supermarketconnection

Additive schema change: stores the Intermarché connected-customer id
separately from the cookies blob. It is not reliably present in cookies (it
arrives via the /loading?userId=... OAuth redirect), so deriving it from
cookies on every request means a routine extension cookie re-sync (which
never captures it) silently breaks the cart mirror. Persisting it once
recovered lets it survive future cookie-only re-imports.

Revision ID: n5e7f9a3c6d8
Revises: m1c4e8f2a6b9
Create Date: 2026-08-17 02:40:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "n5e7f9a3c6d8"
down_revision: Union[str, Sequence[str], None] = "m1c4e8f2a6b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "supermarketconnection",
        sa.Column("customer_uuid", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("supermarketconnection", "customer_uuid")
