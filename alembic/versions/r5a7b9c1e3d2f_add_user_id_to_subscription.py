"""add nullable user_id to subscription

Pure additive schema change: scopes the subscriptions domain to a user,
matching the multi-tenant tables (groceryitem/pantryitem/recipe/mealplan/
note/account/savingsgoal/goal/...). No data mutation — backfilling existing
NULL rows is a separate operational step (see
scripts/backfill_owner_tenant.py).

Revision ID: r5a7b9c1e3d2f
Revises: q4e8e2f5a1d7
Create Date: 2026-08-18 14:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "r5a7b9c1e3d2f"
down_revision: Union[str, Sequence[str], None] = "q4e8e2f5a1d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("subscription", sa.Column("user_id", sa.Integer(), nullable=True))
    op.create_index(
        op.f("ix_subscription_user_id"),
        "subscription",
        ["user_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_subscription_user_id",
        "subscription",
        "user",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_subscription_user_id", "subscription", type_="foreignkey")
    op.drop_index(op.f("ix_subscription_user_id"), table_name="subscription")
    op.drop_column("subscription", "user_id")