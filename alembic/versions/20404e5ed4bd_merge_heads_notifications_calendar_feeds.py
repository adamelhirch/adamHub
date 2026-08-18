"""merge heads (notifications + calendar_feeds)

Revision ID: 20404e5ed4bd
Revises: t1a3c5e7g9b2, t2b4d6f8a1c3
Create Date: 2026-08-18 12:28:31.338940

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20404e5ed4bd'
down_revision: Union[str, Sequence[str], None] = ('t1a3c5e7g9b2', 't2b4d6f8a1c3')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
