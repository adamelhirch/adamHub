"""add supermarket connections (DB-backed encrypted cookies)

Revision ID: g8d2e9f4a1b3
Revises: f7c1d8a3b2e4
Create Date: 2026-05-03 14:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = "g8d2e9f4a1b3"
down_revision: Union[str, Sequence[str], None] = "f7c1d8a3b2e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "supermarketconnection",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "store",
            sa.Enum(
                "INTERMARCHE",
                "UBEREATS",
                "CARREFOUR",
                name="supermarketstore",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("label", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("cookies_encrypted", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_supermarketconnection_store"), "supermarketconnection", ["store"], unique=False
    )
    op.create_index(
        op.f("ix_supermarketconnection_is_active"),
        "supermarketconnection",
        ["is_active"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_supermarketconnection_is_active"), table_name="supermarketconnection")
    op.drop_index(op.f("ix_supermarketconnection_store"), table_name="supermarketconnection")
    op.drop_table("supermarketconnection")
