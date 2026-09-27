"""initial_core_schema

Revision ID: da1365f53d1a
Revises: 
Create Date: 2026-09-27 18:36:26.920665

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlmodel import SQLModel
import app.models.entities  # noqa: F401


# revision identifiers, used by Alembic.
revision: str = 'da1365f53d1a'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - creates all core food and supermarket tables."""
    bind = op.get_bind()
    SQLModel.metadata.create_all(bind=bind)


def downgrade() -> None:
    """Downgrade schema - drops all core food and supermarket tables."""
    bind = op.get_bind()
    SQLModel.metadata.drop_all(bind=bind)
