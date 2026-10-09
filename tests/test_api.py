from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ai_company.adapters.database import Base, StoryRepository, TaskRepository
from ai_company.api.main import CampaignCreate, ReviewCreate, StoryCreate, create_app
from ai_company.domain.workflow import SourceType


def endpoint(app, path: str, method: str):
    return next(route.endpoint for route in app.routes if route.path == path and method in route.methods)


def test_local_api_command_handlers(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    Base.metadata.create_all(engine)
    repository = StoryRepository(sessionmaker(engine, expire_on_commit=False))
    app = create_app(repository)

    assert endpoint(app, "/health", "GET")() == {"status": "ok"}
    campaign = endpoint(app, "/campaigns", "POST")(
        CampaignCreate(name="Prototype", source_type=SourceType.USER_IDEA, target_count=1)
    )
    story = endpoint(app, "/campaigns/{campaign_id}/stories", "POST")(
        UUID(campaign["id"]), StoryCreate(source_type=SourceType.USER_IDEA, idea="A fictional premise")
    )
    view = endpoint(app, "/stories/{story_id}", "GET")(UUID(story["id"]))
    assert view["stage"] == "draft"
    with pytest.raises(HTTPException) as error:
        endpoint(app, "/stories/{story_id}/final-review", "POST")(
            UUID(story["id"]), ReviewCreate(approved=True)
        )
    assert error.value.status_code == 409


def test_vietnamese_operator_dashboard_lists_persisted_drafts(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'dashboard.db'}")
    Base.metadata.create_all(engine)
    stories = StoryRepository(sessionmaker(engine, expire_on_commit=False))
    app = create_app(stories)
    page = endpoint(app, "/", "GET")()
    assert "Story mới" in page.body.decode("utf-8")
    assert "textContent" in page.body.decode("utf-8")
    assert endpoint(app, "/operator/stories", "GET")() == {"stories": []}

    campaign = endpoint(app, "/campaigns", "POST")(
        CampaignCreate(name="Dashboard", source_type=SourceType.USER_IDEA, target_count=1)
    )
    story = endpoint(app, "/campaigns/{campaign_id}/stories", "POST")(
        UUID(campaign["id"]), StoryCreate(source_type=SourceType.USER_IDEA, idea="A fictional premise"),
    )
    listed = endpoint(app, "/operator/stories", "GET")()["stories"]
    assert len(listed) == 1
    assert listed[0]["id"] == story["id"]
    assert listed[0]["idea"] == "A fictional premise"
    assert listed[0]["tasks"] == {}
    queued = endpoint(app, "/stories/{story_id}/mock-blueprint", "POST")(UUID(story["id"]))
    assert endpoint(app, "/operator/stories", "GET")()["stories"][0]["tasks"]["mock_blueprint"] == {
        "task_id": queued["task_id"], "status": "queued", "attempt_no": 0,
        "attempt_limit": 1, "directory": None,
    }


@pytest.mark.parametrize("cloud_flag,value", [("RENDER", "true"), ("VERCEL", "1")])
def test_unauthenticated_prototype_cannot_start_on_public_hosting(tmp_path, monkeypatch, cloud_flag, value) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'cloud-guard.db'}")
    Base.metadata.create_all(engine)
    stories = StoryRepository(sessionmaker(engine, expire_on_commit=False))
    monkeypatch.setenv(cloud_flag, value)
    with pytest.raises(RuntimeError, match="Public deployment is disabled"):
        create_app(stories)


def test_api_startup_requires_recovery_confirmation(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'recovery.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    stories = StoryRepository(sessions)
    campaign_id = stories.create_campaign("Recovery", SourceType.USER_IDEA, 1)
    story_id = stories.create_story(campaign_id, SourceType.USER_IDEA, "A fictional premise")
    tasks = TaskRepository(sessions)
    now = datetime.now(timezone.utc)
    task_id = tasks.create_task(
        story_id, "story_bible", "recovery-test", now - timedelta(seconds=601), attempt_limit=2,
    )
    assert tasks.claim_task(task_id, "old-worker", now - timedelta(seconds=601), lease_seconds=600)

    app = create_app(stories)
    pending = endpoint(app, "/recovery/tasks", "GET")()
    assert pending == {"task_ids": [str(task_id)]}
    assert not tasks.claim_task(task_id, "new-worker", now)
    endpoint(app, "/recovery/tasks/{task_id}/confirm", "POST")(task_id)
    assert tasks.claim_task(task_id, "new-worker", now)


def test_api_restart_does_not_interrupt_a_valid_live_lease(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'live-lease.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    stories = StoryRepository(sessions)
    campaign_id = stories.create_campaign("Live", SourceType.USER_IDEA, 1)
    story_id = stories.create_story(campaign_id, SourceType.USER_IDEA, "A fictional premise")
    tasks = TaskRepository(sessions)
    now = datetime.now(timezone.utc)
    task_id = tasks.create_task(story_id, "story_bible", "live-lease", now, attempt_limit=2)
    assert tasks.claim_task(task_id, "active-worker", now, lease_seconds=600)

    app = create_app(stories)
    assert endpoint(app, "/recovery/tasks", "GET")() == {"task_ids": []}
    tasks.complete_task(task_id, "active-worker", now)


