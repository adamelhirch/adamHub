"""supermarket category snapshot

Revision ID: ab92d3f41c10
Revises: c3c6f8b5a9ab
Create Date: 2026-03-14 10:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = "ab92d3f41c10"
down_revision: Union[str, Sequence[str], None] = "c3c6f8b5a9ab"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("supermarketsearchcache") as batch_op:
        batch_op.add_column(sa.Column("category", sqlmodel.sql.sqltypes.AutoString(), nullable=True))

    with op.batch_alter_table("supermarketmapping") as batch_op:
        batch_op.add_column(sa.Column("category_snapshot", sqlmodel.sql.sqltypes.AutoString(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("supermarketmapping") as batch_op:
        batch_op.drop_column("category_snapshot")

    with op.batch_alter_table("supermarketsearchcache") as batch_op:
        batch_op.drop_column("category")
