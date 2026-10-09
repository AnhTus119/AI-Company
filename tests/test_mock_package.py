from pathlib import Path
from uuid import UUID

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from ai_company.adapters.database import (
    AuditEventRow, StoryRepository, TaskAttemptRow, TaskRepository,
    initialize_lite_schema, make_session_factory,
)
from ai_company.api.main import CampaignCreate, StoryCreate, create_app
from ai_company.application.capacity import ResourceSnapshot
from ai_company.application.mock_export import verified_mock_artifact
from ai_company.application.mock_media import inspect_mock_hook
from ai_company.application.mock_package import MockPackageHandler
from ai_company.application.runtime import load_runtime_settings
from ai_company.domain.workflow import REQUIRED_ARTIFACTS, SourceType
from ai_company.worker.lite import make_mock_lite_worker


def endpoint(app, path: str, method: str):
    return next(route.endpoint for route in app.routes if route.path == path and method in route.methods)


def test_mock_package_end_to_end_and_safe_retry(tmp_path: Path) -> None:
    pytest.importorskip("imageio_ffmpeg")
    pytest.importorskip("PIL")
    settings = load_runtime_settings({"AI_COMPANY_DATA_DIR": str(tmp_path)})
    sessions = make_session_factory(settings.database_url)
    initialize_lite_schema(sessions)
    stories = StoryRepository(sessions)
    tasks = TaskRepository(sessions)
    output_root = tmp_path / "artifacts"
    app = create_app(stories, artifact_root=output_root)
    campaign = endpoint(app, "/campaigns", "POST")(
        CampaignCreate(name="Package trial", source_type=SourceType.USER_IDEA, target_count=1)
    )
    story = endpoint(app, "/campaigns/{campaign_id}/stories", "POST")(
        UUID(campaign["id"]), StoryCreate(source_type=SourceType.USER_IDEA, idea="A fictional family secret"),
    )
    story_id = UUID(story["id"])
    available = [1200]
    worker = make_mock_lite_worker(
        sessions, "package-test-worker", lambda: ResourceSnapshot(4096, available[0], 4),
        output_root=output_root,
    )

    blueprint = endpoint(app, "/stories/{story_id}/mock-blueprint", "POST")(story_id)
    assert worker.run_once(provider_slots=1, budget_slots=1) == "completed"
    chapters = endpoint(app, "/stories/{story_id}/mock-chapters", "POST")(story_id)
    assert worker.run_once(provider_slots=1, budget_slots=1) == "completed"
    queued = endpoint(app, "/stories/{story_id}/mock-package", "POST")(story_id)
    task_id = UUID(queued["task_id"])
    available[0] = 700
    assert worker.run_once(provider_slots=1, budget_slots=1) == "deferred_capacity"
    assert not output_root.exists()
    available[0] = 1200
    original_handler = worker.handlers["mock_package"]

    def crash_after_publish(claimed_task_id: UUID) -> dict:
        original_handler(claimed_task_id)
        raise RuntimeError("simulated crash after publishing the mock folder")

    worker.handlers["mock_package"] = crash_after_publish
    assert worker.run_once(provider_slots=1, budget_slots=1) == "failed"
    failed = endpoint(app, "/stories/{story_id}/mock-package/{task_id}", "GET")(story_id, task_id)
    assert failed["status"] == "technical_failure"
    assert failed["checkpoint"] is None
    published = list((output_root / "MOCK_OUTPUT").iterdir())
    assert len(published) == 1
    with pytest.raises(HTTPException) as wrong_story:
        endpoint(app, "/stories/{story_id}/mock-package/{task_id}/retry", "POST")(
            UUID(int=0), task_id,
        )
    assert wrong_story.value.status_code == 409
    retried = endpoint(app, "/stories/{story_id}/mock-package/{task_id}/retry", "POST")(
        story_id, task_id,
    )
    assert retried["status"] == "queued"
    worker.handlers["mock_package"] = original_handler
    assert worker.run_once(provider_slots=1, budget_slots=1) == "completed"

    result = endpoint(app, "/stories/{story_id}/mock-package/{task_id}", "GET")(story_id, task_id)
    assert result["status"] == "completed"
    checkpoint = result["checkpoint"]
    assert checkpoint["is_mock"] is True
    directory = Path(checkpoint["directory"])
    assert directory.parent == output_root / "MOCK_OUTPUT"
    assert {file.name for file in directory.iterdir()} == REQUIRED_ARTIFACTS
    assert set(checkpoint["artifacts"]) == REQUIRED_ARTIFACTS
    assert all(item["verified"] and item["is_mock"] for item in checkpoint["artifacts"].values())
    assert 13 <= inspect_mock_hook(directory / "hook.mp4").duration_seconds <= 17
    assert 13 <= checkpoint["hook_duration_seconds"] <= 17
    file_route = endpoint(app, "/stories/{story_id}/mock-package/{task_id}/files/{filename}", "GET")
    preview = file_route(story_id, task_id, "hook.mp4")
    assert Path(preview.path) == directory / "hook.mp4"
    assert "inline" in preview.headers["content-disposition"]
    download = file_route(story_id, task_id, "story.txt", download=True)
    assert "attachment" in download.headers["content-disposition"]
    with pytest.raises(HTTPException) as wrong_file:
        file_route(story_id, task_id, "state.sqlite3")
    assert wrong_file.value.status_code == 409
    with pytest.raises(ValueError, match="outside"):
        verified_mock_artifact(tmp_path / "another-root", story_id, str(directory), "story.txt", checkpoint["artifacts"])

    # If the worker died after publishing the folder, rerun reuses its verified contents.
    assert MockPackageHandler(tasks, output_root)(task_id) == checkpoint
    assert endpoint(app, "/stories/{story_id}/mock-package", "POST")(story_id)["task_id"] == str(task_id)
    with pytest.raises(HTTPException) as repeated_retry:
        endpoint(app, "/stories/{story_id}/mock-package/{task_id}/retry", "POST")(
            story_id, task_id,
        )
    assert repeated_retry.value.status_code == 409
    with sessions() as session:
        attempts = session.scalars(select(TaskAttemptRow).where(TaskAttemptRow.task_id == task_id)).all()
        assert [(item.attempt_no, item.outcome) for item in attempts] == [
            (1, "technical_failure"), (2, "completed"),
        ]
        retries = session.scalars(select(AuditEventRow).where(
            AuditEventRow.entity_id == task_id,
            AuditEventRow.action == "mock_package_retry_requested",
        )).all()
        assert len(retries) == 1
    assert stories.get_story(story_id).production_ready_at is None
    assert endpoint(app, "/stories/{story_id}", "GET")(story_id)["stage"] == "draft"
    (directory / "caption.txt").write_text("changed", encoding="utf-8")
    with pytest.raises(HTTPException) as tampered:
        file_route(story_id, task_id, "caption.txt")
    assert tampered.value.status_code == 409
