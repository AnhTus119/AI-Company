"""Durable non-secret task request payloads.

Revision ID: 0005_task_request_payload
Revises: 0004_native_novel_workspace
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision = "0005_task_request_payload"
down_revision = "0004_native_novel_workspace"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("request_payload", JSONB(), nullable=True))


def downgrade() -> None:
    raise RuntimeError("Automatic destructive downgrade is disabled; restore a verified backup instead.")
