"""add ubereats store and selection table

Revision ID: d8a3f5e2c41a
Revises: c8e1f6a4d2b3
Create Date: 2026-05-02 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = "d8a3f5e2c41a"
down_revision: Union[str, Sequence[str], None] = "c8e1f6a4d2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # ALTER TYPE ... ADD VALUE cannot run inside a transaction block in PG.
        op.execute("COMMIT")
        op.execute("ALTER TYPE supermarketstore ADD VALUE IF NOT EXISTS 'UBEREATS'")

    op.create_table(
        "supermarketstoreselection",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "store",
            sa.Enum("INTERMARCHE", "UBEREATS", name="supermarketstore", create_type=False),
            nullable=False,
        ),
        sa.Column("external_store_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("store_label", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("location_label", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_supermarketstoreselection_store"),
        "supermarketstoreselection",
        ["store"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_supermarketstoreselection_store"),
        table_name="supermarketstoreselection",
    )
    op.drop_table("supermarketstoreselection")
    # Postgres does not support removing an enum value cleanly without recreating the type.
    # Leaving the UBEREATS value in place is safe because no rows reference it after the drop.
