from datetime import datetime, timezone
from uuid import UUID

import pytest
from sqlalchemy import create_engine, inspect

from ai_company.adapters.database import (
    Base, NovelWorkspaceRepository, NovelWorkspaceRow, StoryRepository, TaskRepository,
    initialize_lite_schema, make_session_factory,
)
from ai_company.api.main import create_app
from ai_company.application.novel_workspace import (
    ChapterDraftInput, NovelWorkspace, apply_chapter_draft, materialize_workspace,
)
from ai_company.application.real_blueprint import real_blueprint_key
from ai_company.domain.workflow import DomainError, SourceType


def blueprint() -> dict:
    return {
        "kind": "story_blueprint", "schema_version": 1, "is_mock": False,
        "title": "The Door She Never Opened",
        "story_bible": {
            "setting": "A coastal town", "timeline": "Three weeks",
            "core_conflict": "A family lie", "emotional_arc": "Distrust to truth",
            "ending": "The lie is exposed",
            "characters": [
                {"name": "Mara", "role": "lead", "motivation": "find truth", "secret": "a letter"},
                {"name": "Eli", "role": "brother", "motivation": "repair harm", "secret": "the sender"},
            ],
        },
        "chapter_plan": [
            {"number": n, "objective": f"Objective {n}", "reveal_or_turn": f"Turn {n}"}
            for n in range(1, 21)
        ],
        "hook_contract": {
            "hook_event": "A letter appears under the door.",
            "stakes": "The family may fracture.", "open_loop": "Who sent the letter?",
            "chapter_one_handoff": "Begin before the delivery.", "planned_payoff_chapter": 18,
        },
        "audit": {"provider": "openai", "model": "gpt-test"},
    }


def make_story(tmp_path):
    sessions = make_session_factory(f"sqlite:///{tmp_path / 'workspace.sqlite3'}")
    initialize_lite_schema(sessions)
    stories = StoryRepository(sessions)
    campaign_id = stories.create_campaign("Native workspace", SourceType.USER_IDEA, 1)
    story_id = stories.create_story(campaign_id, SourceType.USER_IDEA, "A family receives a letter.")
    return sessions, stories, story_id


def test_workspace_materializes_and_updates_chapter_with_continuity(tmp_path) -> None:
    sessions, _, story_id = make_story(tmp_path)
    repository = NovelWorkspaceRepository(sessions)
    workspace = materialize_workspace(story_id, blueprint())
    created = repository.create_or_get(story_id, workspace.model_dump(mode="json"))
    assert created["row_version"] == 1
    assert len(created["workspace"]["outlines"]) == 20
    current = NovelWorkspace.model_validate(created["workspace"])
    updated = apply_chapter_draft(current, 1, ChapterDraftInput(
        expected_version=1, title="The Letter", content="Mara finds the letter and calls Eli.",
        status="reviewed", continuity_notes=["Mara now distrusts Eli."],
        new_open_loops=["Why was the seal broken?"],
    ))
    saved = repository.save(
        story_id, 1, updated.model_dump(mode="json"),
        action="chapter_saved", details={"chapter_number": 1},
    )
    assert saved["row_version"] == 2
    assert saved["workspace"]["chapters"][0]["word_count"] == 7
    assert saved["workspace"]["continuity"]["last_completed_chapter"] == 1
    with pytest.raises(DomainError, match="changed"):
        repository.save(
            story_id, 1, updated.model_dump(mode="json"), action="chapter_saved",
        )


def test_lite_schema_three_upgrades_to_native_workspace_table(tmp_path) -> None:
    database = tmp_path / "upgrade.sqlite3"
    engine = create_engine(f"sqlite:///{database}")
    for table in Base.metadata.sorted_tables:
        if table.name != NovelWorkspaceRow.__tablename__:
            table.create(engine, checkfirst=True)
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA user_version=3")
    sessions = make_session_factory(f"sqlite:///{database}")
    initialize_lite_schema(sessions)
    assert "novel_workspaces" in inspect(sessions.kw["bind"]).get_table_names()
    with sessions.kw["bind"].connect() as connection:
        assert connection.exec_driver_sql("PRAGMA user_version").scalar() == 4


def test_local_api_materializes_workspace_without_login(tmp_path) -> None:
    sessions, stories, story_id = make_story(tmp_path)
    tasks = TaskRepository(sessions)
    now = datetime.now(timezone.utc)
    task_id = tasks.create_task(story_id, "real_blueprint", real_blueprint_key(story_id), now)
    assert tasks.claim_task(task_id, "test-worker", now)
    tasks.complete_task(task_id, "test-worker", now, checkpoint=blueprint())
    app = create_app(stories)

    def endpoint(path, method):
        return next(route.endpoint for route in app.routes if route.path == path and method in route.methods)

    created = endpoint("/stories/{story_id}/novel-workspace", "POST")(story_id)
    assert created["row_version"] == 1
    fetched = endpoint("/stories/{story_id}/novel-workspace", "GET")(story_id)
    assert fetched["workspace"]["title"] == "The Door She Never Opened"
    saved = endpoint(
        "/stories/{story_id}/novel-workspace/chapters/{chapter_number}", "PUT",
    )(story_id, 1, ChapterDraftInput(
        expected_version=1, title="The Letter", content="Mara reads the letter.",
    ))
    assert saved["row_version"] == 2
    assert saved["workspace"]["chapters"][0]["chapter_number"] == 1
