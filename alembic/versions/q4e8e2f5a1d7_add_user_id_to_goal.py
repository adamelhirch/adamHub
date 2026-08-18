"""add nullable user_id to goal

Pure additive schema change: scopes the goals domain to a user, matching the
multi-tenant tables (groceryitem/pantryitem/recipe/mealplan). Goal milestones
stay as-is: they inherit their owner through the goal_id FK — every milestone
route/handler resolves the parent goal and requires ownership before touching
the milestone, so no column is added to goalmilestone. No data mutation —
backfilling existing NULL rows is a separate operational step
(see scripts/backfill_owner_tenant.py).

Revision ID: q4e8e2f5a1d7
Revises: q8f2a4c6e1d3
Create Date: 2026-08-18 09:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "q4e8e2f5a1d7"
down_revision: Union[str, Sequence[str], None] = "q8f2a4c6e1d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("goal", sa.Column("user_id", sa.Integer(), nullable=True))
    op.create_index(
        op.f("ix_goal_user_id"),
        "goal",
        ["user_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_goal_user_id",
        "goal",
        "user",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_goal_user_id", "goal", type_="foreignkey")
    op.drop_index(op.f("ix_goal_user_id"), table_name="goal")
    op.drop_column("goal", "user_id")