"""add supermarket carts and cart items

Additive schema change: introduces the per-(user, store) cart and its line
items. Items snapshot their store metadata from a SupermarketSearchCache row at
add time; the ``cache_id`` FK uses ``ondelete=SET NULL`` so the search cache can
keep purging expired rows without violating the reference.

Revision ID: m1c4e8f2a6b9
Revises: 70295b0183e8
Create Date: 2026-08-16 09:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "m1c4e8f2a6b9"
down_revision: Union[str, Sequence[str], None] = "70295b0183e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "supermarketcart",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column(
            "store",
            sa.Enum(
                "INTERMARCHE",
                "CARREFOUR",
                "LECLERC",
                "AUCHAN",
                name="supermarketstore",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("DRAFT", "VALIDATED", name="cartstatus"),
            nullable=False,
        ),
        sa.Column("validated_at", sa.DateTime(), nullable=True),
        sa.Column("external_cart_ref", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("user_id", "store", name="uq_supermarketcart_user_store"),
    )
    op.create_index(
        op.f("ix_supermarketcart_user_id"), "supermarketcart", ["user_id"], unique=False
    )

    op.create_table(
        "supermarketcartitem",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cart_id", sa.Integer(), nullable=False),
        sa.Column("cache_id", sa.Integer(), nullable=True),
        sa.Column("external_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("brand", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("packaging", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("price_amount", sa.Float(), nullable=True),
        sa.Column("price_text", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("image_url", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("product_url", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["cart_id"], ["supermarketcart.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cache_id"], ["supermarketsearchcache.id"], ondelete="SET NULL"),
    )
    op.create_index(
        op.f("ix_supermarketcartitem_cart_id"), "supermarketcartitem", ["cart_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_supermarketcartitem_cart_id"), table_name="supermarketcartitem")
    op.drop_table("supermarketcartitem")

    op.drop_index(op.f("ix_supermarketcart_user_id"), table_name="supermarketcart")
    op.drop_table("supermarketcart")

    sa.Enum(name="cartstatus").drop(op.get_bind(), checkfirst=False)
