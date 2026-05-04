"""add users table and user_id FK on supermarketconnection

Revision ID: h2c5e8f1d4a7
Revises: g8d2e9f4a1b3
Create Date: 2026-05-03 18:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = "h2c5e8f1d4a7"
down_revision: Union[str, Sequence[str], None] = "g8d2e9f4a1b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("password_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("display_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_email"), "user", ["email"], unique=True)

    op.add_column(
        "supermarketconnection",
        sa.Column("user_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_supermarketconnection_user_id"),
        "supermarketconnection",
        ["user_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_supermarketconnection_user_id",
        "supermarketconnection",
        "user",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_supermarketconnection_user_id",
        "supermarketconnection",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_supermarketconnection_user_id"), table_name="supermarketconnection")
    op.drop_column("supermarketconnection", "user_id")
    op.drop_index(op.f("ix_user_email"), table_name="user")
    op.drop_table("user")
