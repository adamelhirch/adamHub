"""add nullable user_id to calendarfeed

Pure additive schema change: scopes calendar feeds (the private CRUD router
plus the public token-authenticated .ics export) to their owner user, matching
the multi-tenant tables (groceryitem/pantryitem/recipe/mealplan/note/goal/...).
No data mutation — backfilling existing NULL rows is a separate operational
step (see scripts/backfill_owner_tenant.py).

Revision ID: t2b4d6f8a1c3
Revises: s2f4a6c8e1d3
Create Date: 2026-08-18 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "t2b4d6f8a1c3"
down_revision: Union[str, Sequence[str], None] = "s2f4a6c8e1d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("calendarfeed", sa.Column("user_id", sa.Integer(), nullable=True))
    op.create_index(
        op.f("ix_calendarfeed_user_id"),
        "calendarfeed",
        ["user_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_calendarfeed_user_id",
        "calendarfeed",
        "user",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_calendarfeed_user_id", "calendarfeed", type_="foreignkey")
    op.drop_index(op.f("ix_calendarfeed_user_id"), table_name="calendarfeed")
    op.drop_column("calendarfeed", "user_id")