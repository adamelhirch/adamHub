"""add nullable user_id to note

Pure additive schema change: scopes the notes domain table to a user. No data
mutation — backfilling existing NULL rows is a separate operational step (see
scripts/backfill_owner_tenant.py).

Revision ID: q8g2d4f6a1c3
Revises: p7g9b2c4e6d8
Create Date: 2026-08-18 09:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "q8g2d4f6a1c3"
down_revision: Union[str, Sequence[str], None] = "p7g9b2c4e6d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("note", sa.Column("user_id", sa.Integer(), nullable=True))
    op.create_index(
        op.f("ix_note_user_id"),
        "note",
        ["user_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_note_user_id",
        "note",
        "user",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_note_user_id", "note", type_="foreignkey")
    op.drop_index(op.f("ix_note_user_id"), table_name="note")
    op.drop_column("note", "user_id")