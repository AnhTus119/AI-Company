"""Minimal local operator API for durable campaign/story intake and review."""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field

from ai_company.adapters.database import TaskRepository, StoryRepository, initialize_lite_schema, make_session_factory
from ai_company.application.mock_chapters import mock_blueprint_key, mock_chapters_key
from ai_company.application.mock_export import verified_mock_artifact
from ai_company.application.mock_package import mock_package_key
from ai_company.application.runtime import RuntimeProfile, load_runtime_settings
from ai_company.domain.workflow import DomainError, SourceType, StorySnapshot


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    source_type: SourceType
    target_count: int = Field(default=60, gt=0)


class StoryCreate(BaseModel):
    source_type: SourceType
    idea: str | None = None


class ReviewCreate(BaseModel):
    approved: bool


def _story_view(story: StorySnapshot) -> dict:
    return {
        "id": str(story.id),
        "stage": story.stage.value,
        "source_type": story.source_type.value,
        "accepted_chapters": len(story.chapters),
        "production_ready_at": story.production_ready_at,
        "review_decision_at": story.review_decision_at,
    }


def create_app(
    repository: StoryRepository | None = None, *, artifact_root: Path | None = None,
) -> FastAPI:
    if os.environ.get("VERCEL") == "1" or os.environ.get("RENDER") == "true":
        raise RuntimeError("Public deployment is disabled; run this prototype locally.")
    if repository is None:
        settings = load_runtime_settings()
        if settings.data_dir is None:
            raise RuntimeError("The Standard profile is not available for the local web yet.")
        if settings.profile == RuntimeProfile.LITE:
            settings.data_dir.mkdir(parents=True, exist_ok=True)
        sessions = make_session_factory(settings.database_url)
        if settings.profile == RuntimeProfile.LITE:
            initialize_lite_schema(sessions)
        repository = StoryRepository(sessions)

    if artifact_root is None:
        configured_root = os.environ.get("ARTIFACT_ROOT")
        if configured_root:
            artifact_root = Path(configured_root)
        else:
            data_dir = load_runtime_settings().data_dir
            artifact_root = data_dir / "artifacts" if data_dir is not None else None

    tasks = TaskRepository(repository.sessions)
    # API and worker may be separate processes; do not interrupt a live worker.
    tasks.hold_interrupted_tasks(datetime.now(timezone.utc))

    app = FastAPI(title="AI Content Company — local operator API", version="0.1.0")
    # Local prototype must not silently become a public service.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def operator_dashboard() -> HTMLResponse:
        return HTMLResponse(Path(__file__).with_name("dashboard.html").read_text(encoding="utf-8"))

    @app.get("/operator/stories")
    def operator_stories() -> dict:
        stories = repository.list_mock_drafts()
        statuses = tasks.list_mock_task_statuses(tuple(UUID(item["id"]) for item in stories))
        return {"stories": [{**item, "tasks": statuses.get(item["id"], {})} for item in stories]}

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok" if repository.health() else "unavailable"}

    @app.post("/campaigns", status_code=201)
    def create_campaign(body: CampaignCreate) -> dict:
        try:
            campaign_id = repository.create_campaign(body.name, body.source_type, body.target_count)
        except DomainError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {"id": str(campaign_id), "status": "draft"}

    @app.post("/campaigns/{campaign_id}/stories", status_code=201)
    def create_story(campaign_id: UUID, body: StoryCreate) -> dict:
        try:
            story_id = repository.create_story(campaign_id, body.source_type, body.idea)
        except DomainError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {"id": str(story_id), "status": "draft"}

    @app.get("/stories/{story_id}")
    def get_story(story_id: UUID) -> dict:
        try:
            return _story_view(repository.get_story(story_id))
        except DomainError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.post("/stories/{story_id}/mock-blueprint", status_code=202)
    def queue_mock_blueprint(story_id: UUID) -> dict:
        try:
            story = repository.get_story(story_id)
            if story.stage.value != "draft" or story.source_type != SourceType.USER_IDEA:
                raise DomainError("Mock blueprint accepts user-idea drafts only.")
            task_id = tasks.create_task(
                story_id, "mock_blueprint", mock_blueprint_key(story_id),
                datetime.now(timezone.utc),
            )
        except DomainError as exc:
            raise HTTPException(409, str(exc)) from exc
        result = tasks.get_task_result(task_id, story_id, expected_type="mock_blueprint")
        return {"task_id": str(task_id), "status": result["status"], "is_mock": True}

    @app.get("/stories/{story_id}/mock-blueprint/{task_id}")
    def get_mock_blueprint(story_id: UUID, task_id: UUID) -> dict:
        try:
            result = tasks.get_task_result(task_id, story_id, expected_type="mock_blueprint")
        except DomainError as exc:
            raise HTTPException(404, str(exc)) from exc
        return result

    @app.post("/stories/{story_id}/mock-chapters", status_code=202)
    def queue_mock_chapters(story_id: UUID) -> dict:
        try:
            story = repository.get_story(story_id)
            if story.stage.value != "draft" or story.source_type != SourceType.USER_IDEA:
                raise DomainError("Mock chapters accept user-idea drafts only.")
            blueprint = tasks.get_task_result_by_key(
                story_id, mock_blueprint_key(story_id), expected_type="mock_blueprint",
            )
            if blueprint["status"] != "completed":
                raise DomainError("Complete the mock blueprint before chapters.")
            task_id = tasks.create_task(
                story_id, "mock_chapters", mock_chapters_key(story_id),
                datetime.now(timezone.utc),
            )
            result = tasks.get_task_result(task_id, story_id, expected_type="mock_chapters")
        except DomainError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"task_id": str(task_id), "status": result["status"], "is_mock": True}

    @app.get("/stories/{story_id}/mock-chapters/{task_id}")
    def get_mock_chapters(story_id: UUID, task_id: UUID) -> dict:
        try:
            return tasks.get_task_result(task_id, story_id, expected_type="mock_chapters")
        except DomainError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.post("/stories/{story_id}/mock-package", status_code=202)
    def queue_mock_package(story_id: UUID) -> dict:
        try:
            story = repository.get_story(story_id)
            if story.stage.value != "draft" or story.source_type != SourceType.USER_IDEA:
                raise DomainError("Mock package accepts user-idea drafts only.")
            chapters = tasks.get_task_result_by_key(
                story_id, mock_chapters_key(story_id), expected_type="mock_chapters",
            )
            if chapters["status"] != "completed":
                raise DomainError("Complete the mock chapters before packaging.")
            task_id = tasks.create_task(
                story_id, "mock_package", mock_package_key(story_id),
                datetime.now(timezone.utc), attempt_limit=2,
            )
            result = tasks.get_task_result(task_id, story_id, expected_type="mock_package")
        except DomainError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"task_id": str(task_id), "status": result["status"], "is_mock": True}

    @app.get("/stories/{story_id}/mock-package/{task_id}")
    def get_mock_package(story_id: UUID, task_id: UUID) -> dict:
        try:
            return tasks.get_task_result(task_id, story_id, expected_type="mock_package")
        except DomainError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.get("/stories/{story_id}/mock-package/{task_id}/files/{filename}")
    def get_mock_package_file(story_id: UUID, task_id: UUID, filename: str, download: bool = False) -> FileResponse:
        try:
            result = tasks.get_task_result(task_id, story_id, expected_type="mock_package")
        except DomainError as exc:
            raise HTTPException(404, "Mock package not found.") from exc
        if result["status"] != "completed" or artifact_root is None:
            raise HTTPException(409, "Mock package is not available.")
        checkpoint = result["checkpoint"] or {}
        if checkpoint.get("is_mock") is not True:
            raise HTTPException(409, "Only verified mock packages can be opened.")
        try:
            path = verified_mock_artifact(
                artifact_root, story_id, checkpoint["directory"], filename,
                checkpoint["artifacts"],
            )
        except (KeyError, OSError, ValueError, TypeError) as exc:
            raise HTTPException(409, "Mock file is missing or failed integrity validation.") from exc
        media_type = "video/mp4" if filename == "hook.mp4" else "text/plain; charset=utf-8"
        return FileResponse(
            path, media_type=media_type, filename=filename,
            content_disposition_type="attachment" if download else "inline",
        )

    @app.post("/stories/{story_id}/mock-package/{task_id}/retry", status_code=202)
    def retry_mock_package(story_id: UUID, task_id: UUID) -> dict:
        try:
            story = repository.get_story(story_id)
            if story.stage.value != "draft" or story.source_type != SourceType.USER_IDEA:
                raise DomainError("Only a user-idea mock draft can be retried.")
            tasks.get_task_result(task_id, story_id, expected_type="mock_package")
            tasks.retry_failed_mock_package(task_id, datetime.now(timezone.utc))
            return tasks.get_task_result(task_id, story_id, expected_type="mock_package")
        except DomainError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/stories/{story_id}/final-review")
    def final_review(story_id: UUID, body: ReviewCreate) -> dict:
        try:
            result = repository.record_final_review(story_id, body.approved, datetime.now(timezone.utc))
        except DomainError as exc:
            raise HTTPException(409, str(exc)) from exc
        return _story_view(result)

    @app.get("/recovery/tasks")
    def recovery_tasks() -> dict:
        tasks.hold_interrupted_tasks(datetime.now(timezone.utc))
        return {"task_ids": [str(task_id) for task_id in tasks.list_recovery_tasks()]}

    @app.post("/recovery/tasks/{task_id}/confirm")
    def confirm_recovery(task_id: UUID) -> dict:
        try:
            tasks.confirm_recovery(task_id)
        except DomainError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"task_id": str(task_id), "status": "confirmed"}

    return app
