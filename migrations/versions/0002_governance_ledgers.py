"""Approved policy/model snapshots and provider/cost ledgers.

Revision ID: 0002_governance_ledgers
Revises: 0001_initial_core
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision = "0002_governance_ledgers"
down_revision = "0001_initial_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "policy_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("version", sa.String(100), nullable=False, unique=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.String(200), nullable=True),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "model_assignment_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("version", sa.String(100), nullable=False, unique=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.String(200), nullable=True),
        sa.Column("assignments", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "provider_call_ledger",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("task_attempt_id", sa.Uuid(), sa.ForeignKey("task_attempts.id"), nullable=False),
        sa.Column(
            "assignment_version_id", sa.Uuid(),
            sa.ForeignKey("model_assignment_versions.id"), nullable=False,
        ),
        sa.Column("policy_version_id", sa.Uuid(), sa.ForeignKey("policy_versions.id"), nullable=False),
        sa.Column("provider_key", sa.String(100), nullable=False),
        sa.Column("model_key", sa.String(200), nullable=False),
        sa.Column("workload", sa.String(100), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("usage", JSONB(), nullable=False),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("used_fallback", sa.Boolean(), nullable=False),
        sa.Column("route_reason", sa.String(100), nullable=False),
    )
    op.create_index(
        "ix_provider_call_task_attempt", "provider_call_ledger", ["task_attempt_id", "requested_at"]
    )
    op.create_table(
        "cost_ledger",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("provider_call_id", sa.Uuid(), sa.ForeignKey("provider_call_ledger.id"), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("estimated_minor", sa.Integer(), nullable=False),
        sa.Column("actual_minor", sa.Integer(), nullable=True),
        sa.Column("rate_card_version", sa.String(100), nullable=False),
        sa.Column("budget_decision_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("estimated_minor >= 0"),
        sa.CheckConstraint("actual_minor IS NULL OR actual_minor >= 0"),
        sa.UniqueConstraint("provider_call_id"),
    )


def downgrade() -> None:
    raise RuntimeError("Automatic destructive downgrade is disabled; restore a verified backup instead.")
