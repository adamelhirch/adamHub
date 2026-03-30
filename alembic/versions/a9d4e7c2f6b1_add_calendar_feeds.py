"""add calendar feeds

Revision ID: a9d4e7c2f6b1
Revises: f2b8c3d4e5a6
Create Date: 2026-03-30 20:40:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "a9d4e7c2f6b1"
down_revision: str | Sequence[str] | None = "f2b8c3d4e5a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "calendarfeed" not in tables:
        op.create_table(
            "calendarfeed",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("token", sa.String(), nullable=False),
            sa.Column("sources", sa.JSON(), nullable=False),
            sa.Column("include_completed", sa.Boolean(), nullable=False),
            sa.Column("active", sa.Boolean(), nullable=False),
            sa.Column("last_accessed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("token"),
        )

    existing_indexes = {index["name"] for index in inspector.get_indexes("calendarfeed")}
    if "ix_calendarfeed_token" not in existing_indexes:
        op.create_index("ix_calendarfeed_token", "calendarfeed", ["token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_calendarfeed_token", table_name="calendarfeed")
    op.drop_table("calendarfeed")
