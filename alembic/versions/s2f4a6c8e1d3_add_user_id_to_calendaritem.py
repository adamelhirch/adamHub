"""add nullable user_id to calendaritem

Pure additive schema change: scopes the calendar domain table (CalendarItem —
manual blocks AND the generated entries synced from tasks, events,
subscriptions, meal plans and fitness sessions) to a user, matching the
multi-tenant tables (groceryitem/pantryitem/recipe/mealplan/note/goal/...).
No data mutation — backfilling existing NULL rows is a separate operational
step (see scripts/backfill_owner_tenant.py).

Revision ID: s2f4a6c8e1d3
Revises: r2e4f6a8c1d3
Create Date: 2026-08-18 11:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "s2f4a6c8e1d3"
down_revision: Union[str, Sequence[str], None] = "r2e4f6a8c1d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("calendaritem", sa.Column("user_id", sa.Integer(), nullable=True))
    op.create_index(
        op.f("ix_calendaritem_user_id"),
        "calendaritem",
        ["user_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_calendaritem_user_id",
        "calendaritem",
        "user",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_calendaritem_user_id", "calendaritem", type_="foreignkey")
    op.drop_index(op.f("ix_calendaritem_user_id"), table_name="calendaritem")
    op.drop_column("calendaritem", "user_id")