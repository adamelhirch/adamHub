"""supermarket cache and mappings

Revision ID: c3c6f8b5a9ab
Revises: 856a11daf439
Create Date: 2026-03-14 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "c3c6f8b5a9ab"
down_revision: Union[str, Sequence[str], None] = "856a11daf439"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "supermarketsearchcache",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("store", sa.Enum("INTERMARCHE", name="supermarketstore"), nullable=False),
        sa.Column("query", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("external_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("brand", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("packaging", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("price_amount", sa.Float(), nullable=True),
        sa.Column("price_text", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("image_url", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("product_url", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_supermarketsearchcache_store"), "supermarketsearchcache", ["store"], unique=False)
    op.create_index(op.f("ix_supermarketsearchcache_query"), "supermarketsearchcache", ["query"], unique=False)
    op.create_index(op.f("ix_supermarketsearchcache_external_id"), "supermarketsearchcache", ["external_id"], unique=False)
    op.create_index(op.f("ix_supermarketsearchcache_fetched_at"), "supermarketsearchcache", ["fetched_at"], unique=False)
    op.create_index(op.f("ix_supermarketsearchcache_expires_at"), "supermarketsearchcache", ["expires_at"], unique=False)

    op.create_table(
        "supermarketmapping",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("target_type", sa.Enum("RECIPE_INGREDIENT", "PANTRY_ITEM", name="supermarkettargettype"), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("store", sa.Enum("INTERMARCHE", name="supermarketstore"), nullable=False),
        sa.Column("external_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("store_label", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("name_snapshot", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("packaging_snapshot", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("price_snapshot", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("product_url", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("image_url", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("last_verified_at", sa.DateTime(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_supermarketmapping_target_type"), "supermarketmapping", ["target_type"], unique=False)
    op.create_index(op.f("ix_supermarketmapping_target_id"), "supermarketmapping", ["target_id"], unique=False)
    op.create_index(op.f("ix_supermarketmapping_store"), "supermarketmapping", ["store"], unique=False)
    op.create_index(op.f("ix_supermarketmapping_active"), "supermarketmapping", ["active"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_supermarketmapping_active"), table_name="supermarketmapping")
    op.drop_index(op.f("ix_supermarketmapping_store"), table_name="supermarketmapping")
    op.drop_index(op.f("ix_supermarketmapping_target_id"), table_name="supermarketmapping")
    op.drop_index(op.f("ix_supermarketmapping_target_type"), table_name="supermarketmapping")
    op.drop_table("supermarketmapping")

    op.drop_index(op.f("ix_supermarketsearchcache_expires_at"), table_name="supermarketsearchcache")
    op.drop_index(op.f("ix_supermarketsearchcache_fetched_at"), table_name="supermarketsearchcache")
    op.drop_index(op.f("ix_supermarketsearchcache_external_id"), table_name="supermarketsearchcache")
    op.drop_index(op.f("ix_supermarketsearchcache_query"), table_name="supermarketsearchcache")
    op.drop_index(op.f("ix_supermarketsearchcache_store"), table_name="supermarketsearchcache")
    op.drop_table("supermarketsearchcache")

    sa.Enum(name="supermarkettargettype").drop(op.get_bind(), checkfirst=False)
    sa.Enum(name="supermarketstore").drop(op.get_bind(), checkfirst=False)
