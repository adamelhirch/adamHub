"""add nullable user_id to task

Pure additive schema change: scopes the tasks domain to a user, matching the
multi-tenant tables (groceryitem/pantryitem/recipe/mealplan/note/account/
savingsgoal/financetransaction/budget/goal). App/services/calendar_hub.py is
NOT touched by this migration — scoping its calendar projection/slot validation
to the acting user is a follow-up change that depends on this user_id. No data
mutation — backfilling existing NULL rows is a separate operational step
(see scripts/backfill_owner_tenant.py).

Revision ID: r3e5g7i9k2m4
Revises: r5a7c9e2b4d6f
Create Date: 2026-08-18 10:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "r3e5g7i9k2m4"
down_revision: Union[str, Sequence[str], None] = "r5a7c9e2b4d6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("task", sa.Column("user_id", sa.Integer(), nullable=True))
    op.create_index(
        op.f("ix_task_user_id"),
        "task",
        ["user_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_task_user_id",
        "task",
        "user",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_task_user_id", "task", type_="foreignkey")
    op.drop_index(op.f("ix_task_user_id"), table_name="task")
    op.drop_column("task", "user_id")