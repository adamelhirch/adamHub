"""add habit schedule weekdays

Revision ID: f2b8c3d4e5a6
Revises: e6c4a9d2f1b7
Create Date: 2026-03-30 20:05:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "f2b8c3d4e5a6"
down_revision: str | Sequence[str] | None = "e6c4a9d2f1b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("habit") as batch_op:
        batch_op.add_column(
            sa.Column(
                "schedule_weekdays",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'::json"),
            )
        )

    op.execute(
        """
        UPDATE habit
        SET schedule_weekdays = json_build_array(schedule_weekday)
        WHERE schedule_weekday IS NOT NULL
        """
    )

    with op.batch_alter_table("habit") as batch_op:
        batch_op.alter_column("schedule_weekdays", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("habit") as batch_op:
        batch_op.drop_column("schedule_weekdays")
