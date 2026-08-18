"""add nullable user_id to account/savingsgoal

Pure additive schema change: scopes the patrimony domain tables to a user.
No data mutation — backfilling existing NULL rows is a separate operational step
(see scripts/backfill_owner_tenant.py).

Revision ID: q1e2d3c4b5a6
Revises: p7g9b2c4e6d8
Create Date: 2026-08-18 09:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "q1e2d3c4b5a6"
down_revision: Union[str, Sequence[str], None] = "p7g9b2c4e6d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TABLES = [
    ("account", "fk_account_user_id"),
    ("savingsgoal", "fk_savingsgoal_user_id"),
]


def upgrade() -> None:
    for table, fk_name in _TABLES:
        op.add_column(table, sa.Column("user_id", sa.Integer(), nullable=True))
        op.create_index(
            op.f(f"ix_{table}_user_id"),
            table,
            ["user_id"],
            unique=False,
        )
        op.create_foreign_key(
            fk_name,
            table,
            "user",
            ["user_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    for table, fk_name in reversed(_TABLES):
        op.drop_constraint(fk_name, table, type_="foreignkey")
        op.drop_index(op.f(f"ix_{table}_user_id"), table_name=table)
        op.drop_column(table, "user_id")