"""add store fields to recipe ingredients

Revision ID: b8d6f9c2e4a1
Revises: f1d2a8c4b7e1
Create Date: 2026-03-20 15:10:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b8d6f9c2e4a1"
down_revision = "f1d2a8c4b7e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("recipeingredient", sa.Column("store", sa.String(length=32), nullable=True))
    op.add_column("recipeingredient", sa.Column("store_label", sa.String(), nullable=True))
    op.add_column("recipeingredient", sa.Column("external_id", sa.String(), nullable=True))
    op.add_column("recipeingredient", sa.Column("category", sa.String(), nullable=True))
    op.add_column("recipeingredient", sa.Column("packaging", sa.String(), nullable=True))
    op.add_column("recipeingredient", sa.Column("price_text", sa.String(), nullable=True))
    op.add_column("recipeingredient", sa.Column("product_url", sa.String(), nullable=True))
    op.add_column("recipeingredient", sa.Column("image_url", sa.String(), nullable=True))
    op.create_index("ix_recipeingredient_external_id", "recipeingredient", ["external_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_recipeingredient_external_id", table_name="recipeingredient")
    op.drop_column("recipeingredient", "image_url")
    op.drop_column("recipeingredient", "product_url")
    op.drop_column("recipeingredient", "price_text")
    op.drop_column("recipeingredient", "packaging")
    op.drop_column("recipeingredient", "category")
    op.drop_column("recipeingredient", "external_id")
    op.drop_column("recipeingredient", "store_label")
    op.drop_column("recipeingredient", "store")
