"""add nullable cache_id to supermarketmapping and recipeingredient

Pure additive schema change: persists the SupermarketSearchCache id a mapping or
recipe ingredient was resolved from, so store-backed metadata can be restored on
read instead of relying on client-supplied fields.

Revision ID: k1c3e5f7a2b4
Revises: j4d6e8f2a5b7
Create Date: 2026-08-14 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "k1c3e5f7a2b4"
down_revision: Union[str, Sequence[str], None] = "j4d6e8f2a5b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "supermarketmapping",
        sa.Column("cache_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_supermarketmapping_cache_id"),
        "supermarketmapping",
        ["cache_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_supermarketmapping_cache_id",
        "supermarketmapping",
        "supermarketsearchcache",
        ["cache_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "recipeingredient",
        sa.Column("cache_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_recipeingredient_cache_id",
        "recipeingredient",
        "supermarketsearchcache",
        ["cache_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_recipeingredient_cache_id",
        "recipeingredient",
        type_="foreignkey",
    )
    op.drop_column("recipeingredient", "cache_id")

    op.drop_constraint(
        "fk_supermarketmapping_cache_id",
        "supermarketmapping",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_supermarketmapping_cache_id"), table_name="supermarketmapping")
    op.drop_column("supermarketmapping", "cache_id")
