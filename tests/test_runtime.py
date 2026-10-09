from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from ai_company.adapters.database import CampaignRow, StoryRepository, TaskRepository, initialize_lite_schema, make_session_factory
from ai_company.application.capacity import ResourceSnapshot, safe_worker_count
from ai_company.application.lite_backup import backup_lite_database
from ai_company.application.runtime import RuntimeProfile, load_runtime_settings
from ai_company.domain.workflow import DomainError, SourceType


def test_lite_profile_uses_local_wal_and_reopens(tmp_path: Path) -> None:
    settings = load_runtime_settings({"LOCALAPPDATA": str(tmp_path)})
    assert settings.profile == RuntimeProfile.LITE
    assert settings.transport == "database_polling"
    assert settings.max_local_workers == 1
    assert settings.data_dir == tmp_path / "AIContentCompany"
    settings.data_dir.mkdir()
    sessions = make_session_factory(settings.database_url)
    initialize_lite_schema(sessions)
    with sessions() as session:
        assert session.execute(text("PRAGMA journal_mode")).scalar() == "wal"
        assert session.execute(text("PRAGMA foreign_keys")).scalar() == 1
    campaign_id = StoryRepository(sessions).create_campaign("Lite", SourceType.USER_IDEA, 1)
    reopened = make_session_factory(settings.database_url)
    initialize_lite_schema(reopened)
    with reopened() as session:
        assert session.get(CampaignRow, campaign_id)


def test_lite_database_backup_is_readable_and_never_overwrites(tmp_path: Path) -> None:
    settings = load_runtime_settings({"AI_COMPANY_DATA_DIR": str(tmp_path)})
    sessions = make_session_factory(settings.database_url)
    initialize_lite_schema(sessions)
    campaign_id = StoryRepository(sessions).create_campaign("Backup", SourceType.USER_IDEA, 1)
    destination = tmp_path / "snapshot.sqlite3"
    assert backup_lite_database(tmp_path / "state.sqlite3", destination) == destination
    snapshot = make_session_factory(f"sqlite:///{destination}")
    with snapshot() as session:
        assert session.get(CampaignRow, campaign_id)
    with pytest.raises(FileExistsError):
        backup_lite_database(tmp_path / "state.sqlite3", destination)


def test_standard_profile_requires_separate_services() -> None:
    with pytest.raises(DomainError, match="PostgreSQL"):
        load_runtime_settings({"AI_COMPANY_PROFILE": "standard"})
    settings = load_runtime_settings({
        "AI_COMPANY_PROFILE": "standard",
        "DATABASE_URL": "postgresql+psycopg://user:password@localhost/content",
        "RABBITMQ_URL": "amqp://guest:guest@localhost/",
    })
    assert settings.transport == "rabbitmq" and settings.max_local_workers is None


def test_lite_capacity_pauses_when_ram_is_exhausted() -> None:
    assert safe_worker_count(RuntimeProfile.LITE, ResourceSnapshot(4096, 110, 4), 5, 5, 5) == 0
    assert safe_worker_count(RuntimeProfile.LITE, ResourceSnapshot(4096, 900, 4), 5, 5, 5) == 1
    assert safe_worker_count(RuntimeProfile.LITE, ResourceSnapshot(8192, 2048, 8), 5, 5, 5) == 1
    assert safe_worker_count(RuntimeProfile.STANDARD, ResourceSnapshot(16384, 8000, 8), 5, 3, 2) == 2
    assert safe_worker_count(RuntimeProfile.STANDARD, ResourceSnapshot(16384, 800, 8), 5, 5, 5) == 0
    assert safe_worker_count(RuntimeProfile.STANDARD, ResourceSnapshot(16384, 1600, 8), 5, 5, 5) == 2


def test_two_lite_workers_cannot_claim_same_task(tmp_path: Path) -> None:
    settings = load_runtime_settings({"AI_COMPANY_DATA_DIR": str(tmp_path)})
    sessions = make_session_factory(settings.database_url)
    initialize_lite_schema(sessions)
    stories = StoryRepository(sessions)
    campaign_id = stories.create_campaign("Claim", SourceType.USER_IDEA, 1)
    story_id = stories.create_story(campaign_id, SourceType.USER_IDEA, "A fictional premise")
    tasks = TaskRepository(sessions)
    now = datetime.now(timezone.utc)
    task_id = tasks.create_task(story_id, "story_bible", "claim-once", now)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda worker: tasks.claim_task(task_id, worker, now), ("a", "b")))
    assert sorted(results) == [False, True]


def test_concurrent_task_creation_reuses_one_idempotency_key(tmp_path: Path) -> None:
    settings = load_runtime_settings({"AI_COMPANY_DATA_DIR": str(tmp_path)})
    sessions = make_session_factory(settings.database_url)
    initialize_lite_schema(sessions)
    stories = StoryRepository(sessions)
    campaign_id = stories.create_campaign("Concurrent", SourceType.USER_IDEA, 1)
    story_id = stories.create_story(campaign_id, SourceType.USER_IDEA, "A fictional premise")
    tasks = TaskRepository(sessions)
    now = datetime.now(timezone.utc)
    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(
            lambda _: tasks.create_task(story_id, "mock_blueprint", "same-key", now),
            range(2),
        ))
    assert ids[0] == ids[1]


def test_lite_global_active_task_cap(tmp_path: Path) -> None:
    settings = load_runtime_settings({"AI_COMPANY_DATA_DIR": str(tmp_path)})
    sessions = make_session_factory(settings.database_url)
    initialize_lite_schema(sessions)
    stories = StoryRepository(sessions)
    campaign_id = stories.create_campaign("Capacity", SourceType.USER_IDEA, 2)
    story_a = stories.create_story(campaign_id, SourceType.USER_IDEA, "First premise")
    story_b = stories.create_story(campaign_id, SourceType.USER_IDEA, "Second premise")
    tasks = TaskRepository(sessions)
    now = datetime.now(timezone.utc)
    task_a = tasks.create_task(story_a, "story_bible", "a", now)
    task_b = tasks.create_task(story_b, "story_bible", "b", now)
    assert tasks.claim_task(task_a, "worker-a", now, max_active_tasks=1)
    assert not tasks.claim_task(task_b, "worker-b", now, max_active_tasks=1)
    tasks.complete_task(task_a, "worker-a", now)
    assert tasks.claim_task(task_b, "worker-b", now, max_active_tasks=1)
