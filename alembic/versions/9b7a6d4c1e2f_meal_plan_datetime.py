"""meal plan datetime scheduling

Revision ID: 9b7a6d4c1e2f
Revises: 73b49b673d54
Create Date: 2026-03-06 05:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9b7a6d4c1e2f"
down_revision: Union[str, Sequence[str], None] = "73b49b673d54"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("mealplan") as batch_op:
        batch_op.add_column(sa.Column("planned_at", sa.DateTime(), nullable=True))

    op.execute("UPDATE mealplan SET planned_at = COALESCE(planned_at, created_at)")

    with op.batch_alter_table("mealplan") as batch_op:
        batch_op.alter_column("planned_at", existing_type=sa.DateTime(), nullable=False)
        batch_op.alter_column("planned_for", existing_type=sa.Date(), nullable=True)
        batch_op.alter_column("slot", existing_type=sa.Enum("BREAKFAST", "LUNCH", "DINNER", name="mealslot"), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("mealplan") as batch_op:
        batch_op.alter_column("planned_for", existing_type=sa.Date(), nullable=False)
        batch_op.alter_column("slot", existing_type=sa.Enum("BREAKFAST", "LUNCH", "DINNER", name="mealslot"), nullable=False)
        batch_op.drop_column("planned_at")
