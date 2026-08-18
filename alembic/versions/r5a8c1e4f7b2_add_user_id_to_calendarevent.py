"""add nullable user_id to calendarevent

Pure additive schema change: scopes the events domain table (CalendarEvent —
distinct from the calendar domain's CalendarItem, which stays shared) to a
user, matching the multi-tenant tables (groceryitem/pantryitem/recipe/mealplan/
note/account/savingsgoal/financetransaction/budget/goal). No data mutation —
backfilling existing NULL rows is a separate operational step
(see scripts/backfill_owner_tenant.py).

Revision ID: r5a8c1e4f7b2
Revises: q4e8e2f5a1d7
Create Date: 2026-08-18 10:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "r5a8c1e4f7b2"
down_revision: Union[str, Sequence[str], None] = "q4e8e2f5a1d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("calendarevent", sa.Column("user_id", sa.Integer(), nullable=True))
    op.create_index(
        op.f("ix_calendarevent_user_id"),
        "calendarevent",
        ["user_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_calendarevent_user_id",
        "calendarevent",
        "user",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_calendarevent_user_id", "calendarevent", type_="foreignkey")
    op.drop_index(op.f("ix_calendarevent_user_id"), table_name="calendarevent")
    op.drop_column("calendarevent", "user_id")