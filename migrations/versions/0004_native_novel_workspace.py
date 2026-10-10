"""Native local novel workspace.

Revision ID: 0004_native_novel_workspace
Revises: 0003_budget_enforcement
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision = "0004_native_novel_workspace"
down_revision = "0003_budget_enforcement"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "novel_workspaces",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("story_id", sa.Uuid(), sa.ForeignKey("stories.id"), nullable=False),
        sa.Column("document", JSONB(), nullable=False),
        sa.Column("row_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_novel_workspaces_story_id", "novel_workspaces", ["story_id"], unique=True)


def downgrade() -> None:
    raise RuntimeError("Automatic destructive downgrade is disabled; restore a verified backup instead.")
