"""drop linear integration tables

The Linear integration (linearprojectcache, linearissuecache) was scope
creep from a different project (CandiGO, tracked in Linear) — this project
is tracked via GitHub issues and never had any legitimate use for it. Drops
the tables entirely rather than leaving them dead.

Revision ID: p7g9b2c4e6d8
Revises: o6f8a1b3d5c7
Create Date: 2026-08-18 01:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "p7g9b2c4e6d8"
down_revision: Union[str, Sequence[str], None] = "o6f8a1b3d5c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index(op.f("ix_linearprojectcache_linear_id"), table_name="linearprojectcache")
    op.drop_table("linearprojectcache")
    op.drop_index(op.f("ix_linearissuecache_project_linear_id"), table_name="linearissuecache")
    op.drop_index(op.f("ix_linearissuecache_linear_id"), table_name="linearissuecache")
    op.drop_index(op.f("ix_linearissuecache_identifier"), table_name="linearissuecache")
    op.drop_table("linearissuecache")


def downgrade() -> None:
    op.create_table(
        "linearissuecache",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("linear_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("identifier", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("state", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("assignee_name", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("project_linear_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("url", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("synced_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_linearissuecache_identifier"), "linearissuecache", ["identifier"], unique=False)
    op.create_index(op.f("ix_linearissuecache_linear_id"), "linearissuecache", ["linear_id"], unique=False)
    op.create_index(
        op.f("ix_linearissuecache_project_linear_id"), "linearissuecache", ["project_linear_id"], unique=False
    )
    op.create_table(
        "linearprojectcache",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("linear_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("key", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("state", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("url", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("synced_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_linearprojectcache_linear_id"), "linearprojectcache", ["linear_id"], unique=False)
