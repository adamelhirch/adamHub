"""add user profile and memory

Revision ID: m2c1a9f4e8b0
Revises: 20404e5ed4bd
Create Date: 2026-09-12 13:39:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "m2c1a9f4e8b0"
down_revision = "20404e5ed4bd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "userprofile",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("dietary_preferences", sa.JSON(), nullable=False),
        sa.Column("fitness_goals", sa.String(length=500), nullable=False),
        sa.Column("lifestyle_notes", sa.String(length=1000), nullable=False),
        sa.Column("ai_tone", sa.String(length=50), nullable=False),
        sa.Column("onboarding_completed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(op.f("ix_userprofile_user_id"), "userprofile", ["user_id"], unique=True)
    op.create_index(op.f("ix_userprofile_onboarding_completed"), "userprofile", ["onboarding_completed"], unique=False)

    op.create_table(
        "usermemory",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("fact", sa.String(length=1000), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_usermemory_user_id"), "usermemory", ["user_id"], unique=False)
    op.create_index(op.f("ix_usermemory_category"), "usermemory", ["category"], unique=False)
    op.create_index(op.f("ix_usermemory_is_active"), "usermemory", ["is_active"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_usermemory_is_active"), table_name="usermemory")
    op.drop_index(op.f("ix_usermemory_category"), table_name="usermemory")
    op.drop_index(op.f("ix_usermemory_user_id"), table_name="usermemory")
    op.drop_table("usermemory")

    op.drop_index(op.f("ix_userprofile_onboarding_completed"), table_name="userprofile")
    op.drop_index(op.f("ix_userprofile_user_id"), table_name="userprofile")
    op.drop_table("userprofile")
