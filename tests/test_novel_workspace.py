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
    render_complete_story,
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
        assert connection.exec_driver_sql("PRAGMA user_version").scalar() == 5


def test_twenty_reviewed_chapters_complete_and_export_in_order() -> None:
    story_id = UUID("00000000-0000-0000-0000-000000000001")
    workspace = materialize_workspace(story_id, blueprint())
    for chapter_number in range(1, 21):
        workspace = apply_chapter_draft(workspace, chapter_number, ChapterDraftInput(
            expected_version=chapter_number,
            title=f"Part {chapter_number}",
            content=f"Reviewed content for chapter {chapter_number}.",
            status="reviewed",
        ))
    assert workspace.status == "complete"
    exported = render_complete_story(workspace)
    assert exported.startswith("The Door She Never Opened\n\nChapter 1: Part 1")
    assert exported.index("Chapter 19: Part 19") < exported.index("Chapter 20: Part 20")


def test_local_api_materializes_workspace_without_login(tmp_path, monkeypatch) -> None:
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

    provider_environment = {
        "AI_COMPANY_REAL_AI_ENABLED": "true",
        "GEMINI_API_KEY": "local-test-key",
        "GEMINI_MODEL": "gemini-test",
        "AI_COMPANY_POLICY_VERSION": "policy-v1",
        "AI_COMPANY_ASSIGNMENT_VERSION": "models-v1",
        "AI_COMPANY_BUDGET_VERSION": "budget-v1",
        "AI_COMPANY_DAILY_BUDGET_MINOR": "100",
        "AI_COMPANY_BUDGET_CURRENCY": "USD",
        "AI_COMPANY_GEMINI_RATE_CARD_VERSION": "rate-v1",
        "AI_COMPANY_GEMINI_INPUT_MINOR_PER_MILLION": "100",
        "AI_COMPANY_GEMINI_OUTPUT_MINOR_PER_MILLION": "500",
        "AI_COMPANY_GEMINI_MAX_OUTPUT_TOKENS": "6000",
        "AI_COMPANY_GEMINI_TIMEOUT_SECONDS": "60",
    }
    for key, value in provider_environment.items():
        monkeypatch.setenv(key, value)
    queued = endpoint(
        "/stories/{story_id}/novel-workspace/chapters/{chapter_number}/generate", "POST",
    )(story_id, 1)
    assert queued["status"] == "queued" and queued["chapter_number"] == 1
    request = tasks.get_task_request(UUID(queued["task_id"]))
    assert request == {
        "chapter_number": 1, "workspace_version": 2, "auto_continue": False,
    }
