"""add nullable user_id to habit/habitlog

Pure additive schema change: scopes the habits domain (habit + habitlog) to a
user, matching the multi-tenant tables (groceryitem/pantryitem/recipe/mealplan/
goal/…). Logs carry their own user_id because habit.log list/create routes can
then be scoped independently of the parent habit's FK. No data mutation —
backfilling existing NULL rows is a separate operational step
(see scripts/backfill_owner_tenant.py).

Chains onto q4e8e2f5a1d7 (goal) — the current single head.

Revision ID: r5a7c9e2b4d6f
Revises: q4e8e2f5a1d7
Create Date: 2026-08-18 14:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "r5a7c9e2b4d6f"
down_revision: Union[str, Sequence[str], None] = "q4e8e2f5a1d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TABLES = [
    ("habit", "fk_habit_user_id"),
    ("habitlog", "fk_habitlog_user_id"),
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