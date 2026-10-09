"""Initial campaign, story, chapter, gate, artifact, and audit tables.

Revision ID: 0001_initial_core
Revises:
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001_initial_core"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "campaigns",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(48), nullable=False),
        sa.Column("target_count", sa.Integer(), nullable=False),
        sa.Column("kpi_timezone", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("target_count > 0"),
    )
    op.create_table(
        "stories",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("campaign_id", sa.Uuid(), sa.ForeignKey("campaigns.id"), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("idea", sa.Text(), nullable=True),
        sa.Column("stage", sa.String(48), nullable=False),
        sa.Column("planned_chapters", sa.Integer(), nullable=False),
        sa.Column("has_story_bible", sa.Boolean(), nullable=False),
        sa.Column("has_hook_contract", sa.Boolean(), nullable=False),
        sa.Column("production_ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_decision_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("row_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_stories_campaign_id", "stories", ["campaign_id"])
    op.create_index("ix_stories_ready_at", "stories", ["production_ready_at"])
    op.create_table(
        "chapters",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("story_id", sa.Uuid(), sa.ForeignKey("stories.id"), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("recap", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.CheckConstraint("number BETWEEN 1 AND 20"),
        sa.UniqueConstraint("story_id", "number"),
    )
    op.create_index("ix_chapters_story_id", "chapters", ["story_id"])
    op.create_table(
        "gate_decisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("story_id", sa.Uuid(), sa.ForeignKey("stories.id"), nullable=False),
        sa.Column("gate_name", sa.String(64), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("evidence", JSONB(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("story_id", "gate_name"),
    )
    op.create_index("ix_gate_decisions_story_id", "gate_decisions", ["story_id"])
    op.create_table(
        "artifacts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("story_id", sa.Uuid(), sa.ForeignKey("stories.id"), nullable=False),
        sa.Column("filename", sa.String(100), nullable=False),
        sa.Column("storage_uri", sa.Text(), nullable=False),
        sa.Column("sha256_hex", sa.String(64), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False),
        sa.Column("is_mock", sa.Boolean(), nullable=False),
        sa.CheckConstraint("byte_size > 0"),
        sa.UniqueConstraint("story_id", "filename"),
    )
    op.create_index("ix_artifacts_story_id", "artifacts", ["story_id"])
    op.create_table(
        "tasks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("story_id", sa.Uuid(), sa.ForeignKey("stories.id"), nullable=False),
        sa.Column("task_type", sa.String(80), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("eligible_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempt_limit", sa.Integer(), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("lease_owner", sa.String(200), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("checkpoint", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("attempt_limit > 0"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_tasks_story_id", "tasks", ["story_id"])
    op.create_index("ix_tasks_claim", "tasks", ["status", "eligible_at"])
    op.create_table(
        "task_attempts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("task_id", sa.Uuid(), sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.String(200), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome", sa.String(40), nullable=True),
        sa.Column("failure_class", sa.String(40), nullable=True),
        sa.UniqueConstraint("task_id", "attempt_no"),
    )
    op.create_index("ix_task_attempts_task_id", "task_attempts", ["task_id"])
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("entity_type", sa.String(60), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("outcome", sa.String(30), nullable=False),
        sa.Column("details", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_entity", "audit_events", ["entity_type", "entity_id", "created_at"])


def downgrade() -> None:
    raise RuntimeError("Automatic destructive downgrade is disabled; restore a verified backup instead.")
