from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi import HTTPException

from ai_company.adapters.database import StoryRepository, TaskRepository, initialize_lite_schema, make_session_factory
from ai_company.api.main import CampaignCreate, StoryCreate, create_app
from ai_company.application.capacity import ResourceSnapshot
from ai_company.application.mock_blueprint import DeterministicMockBlueprintProvider, validate_mock_blueprint
from ai_company.application.runtime import load_runtime_settings
from ai_company.domain.workflow import SourceType
from ai_company.worker.lite import make_mock_lite_worker


def endpoint(app, path: str, method: str):
    return next(route.endpoint for route in app.routes if route.path == path and method in route.methods)


def test_mock_blueprint_api_to_worker_checkpoint_without_production_ready(tmp_path) -> None:
    settings = load_runtime_settings({"AI_COMPANY_DATA_DIR": str(tmp_path)})
    sessions = make_session_factory(settings.database_url)
    initialize_lite_schema(sessions)
    app = create_app(StoryRepository(sessions))
    campaign = endpoint(app, "/campaigns", "POST")(
        CampaignCreate(name="Offline mock trial", source_type=SourceType.USER_IDEA, target_count=1)
    )
    story = endpoint(app, "/campaigns/{campaign_id}/stories", "POST")(
        UUID(campaign["id"]),
        StoryCreate(source_type=SourceType.USER_IDEA, idea="A fictional family secret"),
    )
    story_id = UUID(story["id"])

    queued = endpoint(app, "/stories/{story_id}/mock-blueprint", "POST")(story_id)
    task_id = UUID(queued["task_id"])
    with pytest.raises(HTTPException) as early:
        endpoint(app, "/stories/{story_id}/mock-chapters", "POST")(story_id)
    assert early.value.status_code == 409
    repeated = endpoint(app, "/stories/{story_id}/mock-blueprint", "POST")(story_id)
    assert repeated["task_id"] == str(task_id)
    assert repeated["status"] == "queued"
    pending = endpoint(app, "/stories/{story_id}/mock-blueprint/{task_id}", "GET")(
        story_id, task_id,
    )
    assert pending["status"] == "queued"
    assert pending["checkpoint"] is None

    worker = make_mock_lite_worker(
        sessions, "test-worker", lambda: ResourceSnapshot(4096, 900, 4),
    )
    assert worker.run_once(provider_slots=1, budget_slots=1) == "completed"
    assert worker.run_once(provider_slots=1, budget_slots=1) == "idle"

    result = endpoint(app, "/stories/{story_id}/mock-blueprint/{task_id}", "GET")(
        story_id, task_id,
    )
    assert result["status"] == "completed"
    validate_mock_blueprint(result["checkpoint"])
    assert len(result["checkpoint"]["chapter_plan"]) == 20
    assert "A fictional family secret" not in str(result["checkpoint"])

    chapter_task = endpoint(app, "/stories/{story_id}/mock-chapters", "POST")(story_id)
    chapter_task_id = UUID(chapter_task["task_id"])
    assert worker.run_once(provider_slots=1, budget_slots=1) == "completed"
    chapter_result = endpoint(app, "/stories/{story_id}/mock-chapters/{task_id}", "GET")(
        story_id, chapter_task_id,
    )
    assert chapter_result["status"] == "completed"
    chapter_checkpoint = chapter_result["checkpoint"]
    assert chapter_checkpoint["is_mock"] is True
    assert chapter_checkpoint["chapter_count"] == 20
    chapters = chapter_checkpoint["chapters"]
    assert [chapter["number"] for chapter in chapters] == list(range(1, 21))
    assert chapters[0]["recap"] is None
    for prior, current in zip(chapters, chapters[1:]):
        assert current["continuity_in"] == prior["continuity_out"]
        assert current["recap"]

    reopened = make_session_factory(settings.database_url)
    assert StoryRepository(reopened).get_story(story_id).production_ready_at is None
    assert TaskRepository(reopened).get_task_result(
        chapter_task_id, story_id, expected_type="mock_chapters",
    )["checkpoint"]["chapter_count"] == 20
    assert endpoint(app, "/stories/{story_id}", "GET")(story_id)["stage"] == "draft"

    unrelated = TaskRepository(sessions).create_task(
        story_id, "different_operation", "different:1", datetime.now(timezone.utc),
    )
    with pytest.raises(HTTPException) as error:
        endpoint(app, "/stories/{story_id}/mock-blueprint/{task_id}", "GET")(
            story_id, unrelated,
        )
    assert error.value.status_code == 404


def test_mock_provider_output_is_stable_and_marked_mock() -> None:
    provider = DeterministicMockBlueprintProvider()
    first = provider.generate(" A fictional family secret ")
    second = provider.generate("A fictional family secret")
    assert first == second
    assert first["is_mock"] is True
