from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from ai_company.adapters.database import Base, StoryRepository, TaskRepository, TaskRow
from ai_company.domain.workflow import DomainError, SourceType


@pytest.fixture
def repositories(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'tasks.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    story_repo = StoryRepository(sessions)
    campaign_id = story_repo.create_campaign("Task trial", SourceType.USER_IDEA, 1)
    story_id = story_repo.create_story(campaign_id, SourceType.USER_IDEA, "A fictional premise")
    return TaskRepository(sessions), story_id


def test_duplicate_delivery_claims_only_once(repositories) -> None:
    tasks, story_id = repositories
    now = datetime.now(timezone.utc)
    task_id = tasks.create_task(story_id, "story_bible", "story-bible:1", now)
    assert tasks.create_task(story_id, "story_bible", "story-bible:1", now) == task_id
    assert tasks.claim_task(task_id, "worker-a", now)
    assert not tasks.claim_task(task_id, "worker-b", now)
    with pytest.raises(DomainError, match="active task lease"):
        tasks.complete_task(task_id, "worker-b", now)
    tasks.complete_task(task_id, "worker-a", now, checkpoint={"bible_id": "synthetic"})
    assert not tasks.claim_task(task_id, "worker-b", now)


def test_idempotency_key_cannot_cross_task_type(repositories) -> None:
    tasks, story_id = repositories
    now = datetime.now(timezone.utc)
    tasks.create_task(story_id, "mock_blueprint", "shared-key", now)
    with pytest.raises(DomainError, match="already used"):
        tasks.create_task(story_id, "mock_chapters", "shared-key", now)


def test_restart_holds_expired_task_for_human_confirmation(repositories) -> None:
    tasks, story_id = repositories
    now = datetime.now(timezone.utc)
    task_id = tasks.create_task(story_id, "chapter", "chapter:1", now, attempt_limit=2)
    assert tasks.claim_task(task_id, "worker-a", now, lease_seconds=10)
    assert tasks.hold_interrupted_tasks(now + timedelta(seconds=11)) == 1
    assert not tasks.claim_task(task_id, "worker-b", now + timedelta(seconds=12))
    tasks.confirm_recovery(task_id)
    assert tasks.claim_task(task_id, "worker-b", now + timedelta(seconds=12))


def test_exhausted_attempt_cannot_resume(repositories) -> None:
    tasks, story_id = repositories
    now = datetime.now(timezone.utc)
    task_id = tasks.create_task(story_id, "chapter", "chapter:2", now, attempt_limit=1)
    assert tasks.claim_task(task_id, "worker-a", now, lease_seconds=1)
    tasks.hold_interrupted_tasks(now + timedelta(seconds=2))
    tasks.confirm_recovery(task_id)
    with tasks.sessions() as session:
        row = session.scalar(select(TaskRow).where(TaskRow.id == task_id))
        assert row.status == "technical_failure"


def test_failed_mock_retry_is_bounded_and_cannot_retry_other_types(repositories) -> None:
    tasks, story_id = repositories
    now = datetime.now(timezone.utc)
    package_id = tasks.create_task(story_id, "mock_package", "mock-package:retry", now, attempt_limit=1)
    assert tasks.claim_task(package_id, "worker-a", now)
    tasks.fail_task(package_id, "worker-a", now, "handler_error")
    with pytest.raises(DomainError, match="no eligible"):
        tasks.retry_failed_mock_package(package_id, now)

    other_id = tasks.create_task(story_id, "mock_chapters", "mock-chapters:retry", now, attempt_limit=2)
    assert tasks.claim_task(other_id, "worker-a", now)
    tasks.fail_task(other_id, "worker-a", now, "handler_error")
    with pytest.raises(DomainError, match="Only a mock package"):
        tasks.retry_failed_mock_package(other_id, now)
