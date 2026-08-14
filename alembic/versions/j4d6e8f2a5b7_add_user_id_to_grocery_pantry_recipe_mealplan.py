"""add nullable user_id to groceryitem/pantryitem/recipe/mealplan

Pure additive schema change: scopes the multi-tenant domain tables to a user.
No data mutation — backfilling existing NULL rows is a separate operational step
(see scripts/backfill_owner_tenant.py).

Revision ID: j4d6e8f2a5b7
Revises: i3a5b7c9d1e2f
Create Date: 2026-08-13 14:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "j4d6e8f2a5b7"
down_revision: Union[str, Sequence[str], None] = "i3a5b7c9d1e2f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TABLES = [
    ("groceryitem", "fk_groceryitem_user_id"),
    ("pantryitem", "fk_pantryitem_user_id"),
    ("recipe", "fk_recipe_user_id"),
    ("mealplan", "fk_mealplan_user_id"),
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
