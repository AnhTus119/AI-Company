"""Daily budget policies and provider-call reservations.

Revision ID: 0003_budget_enforcement
Revises: 0002_governance_ledgers
"""

import sqlalchemy as sa
from alembic import op


revision = "0003_budget_enforcement"
down_revision = "0002_governance_ledgers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "budget_policies",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("version", sa.String(100), nullable=False, unique=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("daily_limit_minor", sa.Integer(), nullable=False),
        sa.Column("timezone_name", sa.String(64), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("daily_limit_minor > 0"),
    )
    op.create_table(
        "daily_budgets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("policy_id", sa.Uuid(), sa.ForeignKey("budget_policies.id"), nullable=False),
        sa.Column("local_day", sa.Date(), nullable=False),
        sa.Column("reserved_minor", sa.Integer(), nullable=False),
        sa.Column("spent_minor", sa.Integer(), nullable=False),
        sa.CheckConstraint("reserved_minor >= 0"),
        sa.CheckConstraint("spent_minor >= 0"),
        sa.UniqueConstraint("policy_id", "local_day"),
    )
    op.create_table(
        "budget_reservations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("daily_budget_id", sa.Uuid(), sa.ForeignKey("daily_budgets.id"), nullable=False),
        sa.Column("task_attempt_id", sa.Uuid(), sa.ForeignKey("task_attempts.id"), nullable=False),
        sa.Column("workload", sa.String(100), nullable=False),
        sa.Column("estimated_minor", sa.Integer(), nullable=False),
        sa.Column("actual_minor", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("estimated_minor >= 0"),
        sa.CheckConstraint("actual_minor IS NULL OR actual_minor >= 0"),
    )
    op.create_index("ix_budget_reservations_daily_budget_id", "budget_reservations", ["daily_budget_id"])
    op.create_index("ix_budget_reservations_task_attempt_id", "budget_reservations", ["task_attempt_id"])


def downgrade() -> None:
    raise RuntimeError("Automatic destructive downgrade is disabled; restore a verified backup instead.")
