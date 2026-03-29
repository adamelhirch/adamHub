"""recipe steps utensils source

Revision ID: 0c9e6a3b7c12
Revises: a4c9d7b21e36
Create Date: 2026-03-19 15:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "0c9e6a3b7c12"
down_revision: Union[str, Sequence[str], None] = "a4c9d7b21e36"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("recipe", sa.Column("steps", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    op.add_column("recipe", sa.Column("utensils", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    op.add_column("recipe", sa.Column("source_url", sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column("recipe", sa.Column("source_platform", sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column("recipe", sa.Column("source_title", sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column("recipe", sa.Column("source_description", sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column("recipe", sa.Column("source_transcript", sqlmodel.sql.sqltypes.AutoString(), nullable=True))


def downgrade() -> None:
    op.drop_column("recipe", "source_transcript")
    op.drop_column("recipe", "source_description")
    op.drop_column("recipe", "source_title")
    op.drop_column("recipe", "source_platform")
    op.drop_column("recipe", "source_url")
    op.drop_column("recipe", "utensils")
    op.drop_column("recipe", "steps")

