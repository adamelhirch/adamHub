"""task and habit scheduling

Revision ID: d4f7c1a2b8e9
Revises: 0c9e6a3b7c12, b8d6f9c2e4a1
Create Date: 2026-03-30 19:05:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "d4f7c1a2b8e9"
down_revision: str | Sequence[str] | None = ("0c9e6a3b7c12", "b8d6f9c2e4a1")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


task_schedule_mode = sa.Enum(
    "NONE",
    "ONCE",
    "DAILY",
    "WEEKLY",
    name="taskschedulemode",
)


def upgrade() -> None:
    task_schedule_mode.create(op.get_bind(), checkfirst=True)

    with op.batch_alter_table("task") as batch_op:
        batch_op.add_column(
            sa.Column(
                "schedule_mode",
                task_schedule_mode,
                nullable=False,
                server_default="NONE",
            )
        )
        batch_op.add_column(sa.Column("schedule_time", sa.String(length=5), nullable=True))
        batch_op.add_column(sa.Column("schedule_weekday", sa.Integer(), nullable=True))

    with op.batch_alter_table("habit") as batch_op:
        batch_op.add_column(sa.Column("schedule_time", sa.String(length=5), nullable=True))
        batch_op.add_column(sa.Column("schedule_weekday", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "duration_minutes",
                sa.Integer(),
                nullable=False,
                server_default="30",
            )
        )

    op.execute("UPDATE task SET schedule_mode = 'ONCE' WHERE due_at IS NOT NULL")
    op.execute("UPDATE task SET schedule_mode = 'NONE' WHERE due_at IS NULL")

    with op.batch_alter_table("task") as batch_op:
        batch_op.alter_column("schedule_mode", server_default=None)

    with op.batch_alter_table("habit") as batch_op:
        batch_op.alter_column("duration_minutes", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("habit") as batch_op:
        batch_op.drop_column("duration_minutes")
        batch_op.drop_column("schedule_weekday")
        batch_op.drop_column("schedule_time")

    with op.batch_alter_table("task") as batch_op:
        batch_op.drop_column("schedule_weekday")
        batch_op.drop_column("schedule_time")
        batch_op.drop_column("schedule_mode")

    task_schedule_mode.drop(op.get_bind(), checkfirst=True)
