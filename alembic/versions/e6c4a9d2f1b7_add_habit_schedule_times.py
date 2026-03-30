"""add habit schedule times

Revision ID: e6c4a9d2f1b7
Revises: d4f7c1a2b8e9
Create Date: 2026-03-30 19:45:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "e6c4a9d2f1b7"
down_revision: str | Sequence[str] | None = "d4f7c1a2b8e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("habit") as batch_op:
        batch_op.add_column(
            sa.Column(
                "schedule_times",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'::json"),
            )
        )

    op.execute(
        """
        UPDATE habit
        SET schedule_times = json_build_array(schedule_time)
        WHERE schedule_time IS NOT NULL
        """
    )

    with op.batch_alter_table("habit") as batch_op:
        batch_op.alter_column("schedule_times", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("habit") as batch_op:
        batch_op.drop_column("schedule_times")
