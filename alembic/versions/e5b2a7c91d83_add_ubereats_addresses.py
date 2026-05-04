"""add ubereats saved addresses

Revision ID: e5b2a7c91d83
Revises: d8a3f5e2c41a
Create Date: 2026-05-02 13:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = "e5b2a7c91d83"
down_revision: Union[str, Sequence[str], None] = "d8a3f5e2c41a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ubereatsaddress",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("label", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("formatted_address", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("subtitle", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("reference", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("reference_type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ubereatsaddress_is_active"), "ubereatsaddress", ["is_active"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ubereatsaddress_is_active"), table_name="ubereatsaddress")
    op.drop_table("ubereatsaddress")
