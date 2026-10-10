"""Explicit per-campaign final approval mode.

Revision ID: 0006_campaign_approval_mode
Revises: 0005_task_request_payload
"""

import sqlalchemy as sa
from alembic import op


revision = "0006_campaign_approval_mode"
down_revision = "0005_task_request_payload"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "campaigns",
        sa.Column("approval_mode", sa.String(16), nullable=False, server_default="manual"),
    )


def downgrade() -> None:
    raise RuntimeError("Automatic destructive downgrade is disabled; restore a verified backup instead.")
