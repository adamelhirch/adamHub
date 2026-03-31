"""add task subtasks

Revision ID: c8e1f6a4d2b3
Revises: a9d4e7c2f6b1
Create Date: 2026-03-31 00:55:00.000000
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "c8e1f6a4d2b3"
down_revision: str | Sequence[str] | None = "a9d4e7c2f6b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

task_table = sa.table(
    "task",
    sa.column("id", sa.Integer()),
    sa.column("description", sa.Text()),
    sa.column("subtasks", sa.JSON()),
)


def upgrade() -> None:
    with op.batch_alter_table("task") as batch_op:
        batch_op.add_column(
            sa.Column(
                "subtasks",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'"),
            )
        )

    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, description FROM task")).fetchall()
    for row in rows:
        description = row.description
        if not description:
            continue
        try:
            payload = json.loads(description)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue

        raw_subtasks = payload.get("subtasks")
        if not isinstance(raw_subtasks, list):
            continue

        normalized_subtasks = []
        for entry in raw_subtasks:
            if not isinstance(entry, dict):
                continue
            title = str(entry.get("title", "")).strip()
            if not title:
                continue
            normalized_subtasks.append(
                {
                    "id": str(entry.get("id") or uuid4().hex),
                    "title": title,
                    "completed": bool(entry.get("completed", False)),
                }
            )

        text_description = payload.get("text")
        if text_description is not None:
            text_description = str(text_description).strip() or None

        bind.execute(
            task_table.update()
            .where(task_table.c.id == row.id)
            .values(
                description=text_description,
                subtasks=normalized_subtasks,
            )
        )

    with op.batch_alter_table("task") as batch_op:
        batch_op.alter_column("subtasks", server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, description, subtasks FROM task")).fetchall()
    for row in rows:
        description = row.description or ""
        subtasks = row.subtasks if isinstance(row.subtasks, list) else []
        if not description and not subtasks:
            continue

        payload = {
            "text": description,
            "subtasks": subtasks,
        }
        bind.execute(
            task_table.update()
            .where(task_table.c.id == row.id)
            .values(description=json.dumps(payload, ensure_ascii=True))
        )

    with op.batch_alter_table("task") as batch_op:
        batch_op.drop_column("subtasks")
