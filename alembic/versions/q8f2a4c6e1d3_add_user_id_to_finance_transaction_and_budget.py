"""add nullable user_id to financetransaction/budget

Pure additive schema change: scopes the finance domain tables to a user.
No data mutation — backfilling existing NULL rows is a separate operational step
(see scripts/backfill_owner_tenant.py).

Chains onto BOTH sibling tenant-scoping heads (q1e2d3c4b5a6 = account/savingsgoal,
q8g2d4f6a1c3 = note), so after this migration lands the graph has a single head.

Revision ID: q8f2a4c6e1d3
Revises: q1e2d3c4b5a6, q8g2d4f6a1c3
Create Date: 2026-08-18 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "q8f2a4c6e1d3"
down_revision: Union[str, Sequence[str], None] = ["q1e2d3c4b5a6", "q8g2d4f6a1c3"]
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TABLES = [
    ("financetransaction", "fk_financetransaction_user_id"),
    ("budget", "fk_budget_user_id"),
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