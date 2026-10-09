from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from ai_company.adapters.database import (
    BudgetPolicyRow, BudgetRepository, BudgetReservationRow, DailyBudgetRow,
    StoryRepository, TaskAttemptRow, TaskRepository,
    initialize_lite_schema, make_session_factory,
)
from ai_company.application.runtime import load_runtime_settings
from ai_company.domain.workflow import DomainError, SourceType


def claimed_attempt(tmp_path):
    settings = load_runtime_settings({"AI_COMPANY_DATA_DIR": str(tmp_path)})
    sessions = make_session_factory(settings.database_url)
    initialize_lite_schema(sessions)
    stories = StoryRepository(sessions)
    campaign_id = stories.create_campaign("Budget", SourceType.USER_IDEA, 1)
    story_id = stories.create_story(campaign_id, SourceType.USER_IDEA, "A fictional premise")
    tasks = TaskRepository(sessions)
    now = datetime.now(timezone.utc)
    task_id = tasks.create_task(story_id, "story_bible", "budget-task", now)
    assert tasks.claim_task(task_id, "worker", now)
    with sessions() as session:
        attempt_id = session.scalar(select(TaskAttemptRow.id).where(TaskAttemptRow.task_id == task_id))
    assert attempt_id is not None
    return sessions, attempt_id, now


def test_budget_reserves_before_call_and_never_exceeds_daily_cap(tmp_path) -> None:
    sessions, attempt_id, now = claimed_attempt(tmp_path)
    budgets = BudgetRepository(sessions)
    budgets.create_policy("budget-v1", "USD", 10, "Asia/Ho_Chi_Minh")
    budgets.activate_policy("budget-v1", "owner", now)
    first = budgets.reserve("budget-v1", attempt_id, "story_bible", 7, now)
    with pytest.raises(DomainError, match="would be exceeded"):
        budgets.reserve("budget-v1", attempt_id, "story_bible", 4, now)
    budgets.settle(first, 5, now)
    second = budgets.reserve("budget-v1", attempt_id, "story_bible", 5, now)
    with pytest.raises(DomainError, match="upper bound"):
        budgets.settle(second, 6, now)
    budgets.release(second, now)
    with sessions() as session:
        daily = session.scalar(select(DailyBudgetRow))
        reservations = session.scalars(select(BudgetReservationRow).order_by(BudgetReservationRow.created_at)).all()
        assert (daily.spent_minor, daily.reserved_minor) == (5, 0)
        assert [item.status for item in reservations] == ["settled", "released"]
        assert session.scalar(select(BudgetPolicyRow)).status == "active"


def test_budget_policy_requires_explicit_activation(tmp_path) -> None:
    sessions, attempt_id, now = claimed_attempt(tmp_path)
    budgets = BudgetRepository(sessions)
    budgets.create_policy("budget-v1", "USD", 10, "Asia/Ho_Chi_Minh")
    with pytest.raises(DomainError, match="active budget"):
        budgets.reserve("budget-v1", attempt_id, "story_bible", 1, now)
    budgets.activate_policy("budget-v1", "owner", now)
    with pytest.raises(DomainError, match="immutable"):
        budgets.activate_policy("budget-v1", "owner", now)
