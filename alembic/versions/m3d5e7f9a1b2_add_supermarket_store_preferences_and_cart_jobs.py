"""add supermarket store preferences and cart jobs

Revision ID: m3d5e7f9a1b2
Revises: m2c1a9f4e8b0
Create Date: 2026-09-13 12:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg


# revision identifiers, used by Alembic.
revision: str = "m3d5e7f9a1b2"
down_revision: Union[str, Sequence[str], None] = "m2c1a9f4e8b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    store_enum = (
        pg.ENUM("INTERMARCHE", "CARREFOUR", "LECLERC", "AUCHAN", name="supermarketstore", create_type=False)
        if bind.dialect.name == "postgresql"
        else sa.Enum("INTERMARCHE", "CARREFOUR", "LECLERC", "AUCHAN", name="supermarketstore", create_type=False)
    )

    # 1. userstorepreference
    op.create_table(
        "userstorepreference",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("store", store_enum, nullable=False),
        sa.Column("external_store_id", sa.String(length=256), nullable=False),
        sa.Column("store_label", sa.String(length=256), nullable=False),
        sa.Column("location_label", sa.String(length=512), nullable=True),
        sa.Column("pickup_type", sa.String(length=32), nullable=False, server_default="quai"),
        sa.Column("optimization_strategy", sa.String(length=32), nullable=False, server_default="mdd"),
        sa.Column("channel", sa.String(length=64), nullable=True),
        sa.Column("raw_context", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "store", name="uq_user_store_preference"),
    )
    op.create_index(op.f("ix_userstorepreference_user_id"), "userstorepreference", ["user_id"], unique=False)
    op.create_index(op.f("ix_userstorepreference_store"), "userstorepreference", ["store"], unique=False)

    # 2. grocerytocartjob
    op.create_table(
        "grocerytocartjob",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("store", store_enum, nullable=False),
        sa.Column("external_store_id", sa.String(length=256), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("optimization_strategy", sa.String(length=32), nullable=False, server_default="mdd"),
        sa.Column("items_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("matched_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("substitutes_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unmatched_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_total_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("synced_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_grocerytocartjob_user_id"), "grocerytocartjob", ["user_id"], unique=False)
    op.create_index(op.f("ix_grocerytocartjob_store"), "grocerytocartjob", ["store"], unique=False)
    op.create_index(op.f("ix_grocerytocartjob_status"), "grocerytocartjob", ["status"], unique=False)

    # 3. matchedcartitem
    op.create_table(
        "matchedcartitem",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("grocery_item_id", sa.Integer(), nullable=True),
        sa.Column("cache_id", sa.Integer(), nullable=True),
        sa.Column("external_id", sa.String(length=256), nullable=True),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("brand", sa.String(length=256), nullable=True),
        sa.Column("packaging", sa.String(length=256), nullable=True),
        sa.Column("image_url", sa.String(length=1024), nullable=True),
        sa.Column("product_url", sa.String(length=1024), nullable=True),
        sa.Column("quantity", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("unit_price_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_price_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("match_type", sa.String(length=32), nullable=False, server_default="mdd"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="staged"),
        sa.Column("custom_note", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["grocerytocartjob.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["grocery_item_id"], ["groceryitem.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["cache_id"], ["supermarketsearchcache.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_matchedcartitem_job_id"), "matchedcartitem", ["job_id"], unique=False)
    op.create_index(op.f("ix_matchedcartitem_grocery_item_id"), "matchedcartitem", ["grocery_item_id"], unique=False)
    op.create_index(op.f("ix_matchedcartitem_cache_id"), "matchedcartitem", ["cache_id"], unique=False)

    # 4. substituteproposal
    op.create_table(
        "substituteproposal",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("matched_item_id", sa.Integer(), nullable=False),
        sa.Column("alternative_cache_id", sa.Integer(), nullable=False),
        sa.Column("alternative_name", sa.String(length=512), nullable=False),
        sa.Column("alternative_brand", sa.String(length=256), nullable=True),
        sa.Column("alternative_unit_price_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("price_difference_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reason", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["matched_item_id"], ["matchedcartitem.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["alternative_cache_id"], ["supermarketsearchcache.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_substituteproposal_matched_item_id"), "substituteproposal", ["matched_item_id"], unique=False)
    op.create_index(op.f("ix_substituteproposal_alternative_cache_id"), "substituteproposal", ["alternative_cache_id"], unique=False)

    # 5. groceryitem.in_cart
    op.add_column("groceryitem", sa.Column("in_cart", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_index(op.f("ix_groceryitem_in_cart"), "groceryitem", ["in_cart"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_groceryitem_in_cart"), table_name="groceryitem")
    op.drop_column("groceryitem", "in_cart")

    op.drop_index(op.f("ix_substituteproposal_alternative_cache_id"), table_name="substituteproposal")
    op.drop_index(op.f("ix_substituteproposal_matched_item_id"), table_name="substituteproposal")
    op.drop_table("substituteproposal")

    op.drop_index(op.f("ix_matchedcartitem_cache_id"), table_name="matchedcartitem")
    op.drop_index(op.f("ix_matchedcartitem_grocery_item_id"), table_name="matchedcartitem")
    op.drop_index(op.f("ix_matchedcartitem_job_id"), table_name="matchedcartitem")
    op.drop_table("matchedcartitem")

    op.drop_index(op.f("ix_grocerytocartjob_status"), table_name="grocerytocartjob")
    op.drop_index(op.f("ix_grocerytocartjob_store"), table_name="grocerytocartjob")
    op.drop_index(op.f("ix_grocerytocartjob_user_id"), table_name="grocerytocartjob")
    op.drop_table("grocerytocartjob")

    op.drop_index(op.f("ix_userstorepreference_store"), table_name="userstorepreference")
    op.drop_index(op.f("ix_userstorepreference_user_id"), table_name="userstorepreference")
    op.drop_table("userstorepreference")
