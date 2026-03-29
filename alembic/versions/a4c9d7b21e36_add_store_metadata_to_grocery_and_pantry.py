"""add store metadata to grocery and pantry

Revision ID: a4c9d7b21e36
Revises: f1d2a8c4b7e1
Create Date: 2026-03-18 17:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a4c9d7b21e36"
down_revision = "f1d2a8c4b7e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table_name in ("groceryitem", "pantryitem"):
        op.add_column(table_name, sa.Column("store_label", sa.String(), nullable=True))
        op.add_column(table_name, sa.Column("external_id", sa.String(), nullable=True))
        op.add_column(table_name, sa.Column("packaging", sa.String(), nullable=True))
        op.add_column(table_name, sa.Column("price_text", sa.String(), nullable=True))
        op.add_column(table_name, sa.Column("product_url", sa.String(), nullable=True))
        op.create_index(op.f(f"ix_{table_name}_external_id"), table_name, ["external_id"], unique=False)


def downgrade() -> None:
    for table_name in ("pantryitem", "groceryitem"):
        op.drop_index(op.f(f"ix_{table_name}_external_id"), table_name=table_name)
        op.drop_column(table_name, "product_url")
        op.drop_column(table_name, "price_text")
        op.drop_column(table_name, "packaging")
        op.drop_column(table_name, "external_id")
        op.drop_column(table_name, "store_label")
