"""add ntfy_topic to user

Pure additive schema change: a nullable per-user ntfy push topic on the user
table. When unset, the notification jobs keep the shared ADAMHUB_NTFY_TOPIC as
the default, so existing single-topic deployments are unaffected.

Revision ID: t1a3c5e7g9b2
Revises: s2f4a6c8e1d3
Create Date: 2026-08-18 13:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "t1a3c5e7g9b2"
down_revision: Union[str, Sequence[str], None] = "s2f4a6c8e1d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user", sa.Column("ntfy_topic", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("user", "ntfy_topic")