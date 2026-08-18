"""add nullable user_id to fitnesssession and fitnessmeasurement

Pure additive schema change: scopes the fitness domain (sessions and
measurements) to a user, matching the multi-tenant tables
(groceryitem/pantryitem/recipe/mealplan/note/goal/...). No data mutation —
backfilling existing NULL rows is a separate operational step
(see scripts/backfill_owner_tenant.py).

Revision ID: r2e4f6a8c1d3
Revises: q4e8e2f5a1d7
Create Date: 2026-08-18 09:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "r2e4f6a8c1d3"
down_revision: Union[str, Sequence[str], None] = "q4e8e2f5a1d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("fitnesssession", sa.Column("user_id", sa.Integer(), nullable=True))
    op.create_index(
        op.f("ix_fitnesssession_user_id"),
        "fitnesssession",
        ["user_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_fitnesssession_user_id",
        "fitnesssession",
        "user",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("fitnessmeasurement", sa.Column("user_id", sa.Integer(), nullable=True))
    op.create_index(
        op.f("ix_fitnessmeasurement_user_id"),
        "fitnessmeasurement",
        ["user_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_fitnessmeasurement_user_id",
        "fitnessmeasurement",
        "user",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_fitnessmeasurement_user_id", "fitnessmeasurement", type_="foreignkey")
    op.drop_index(op.f("ix_fitnessmeasurement_user_id"), table_name="fitnessmeasurement")
    op.drop_column("fitnessmeasurement", "user_id")

    op.drop_constraint("fk_fitnesssession_user_id", "fitnesssession", type_="foreignkey")
    op.drop_index(op.f("ix_fitnesssession_user_id"), table_name="fitnesssession")
    op.drop_column("fitnesssession", "user_id")