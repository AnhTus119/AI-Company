"""Assemble the complete five-file mock package from durable checkpoints."""

from __future__ import annotations

import tempfile
from pathlib import Path
from uuid import UUID

from ai_company.adapters.database import TaskRepository
from ai_company.application.mock_chapters import mock_blueprint_key, mock_chapters_key
from ai_company.application.mock_export import (
    MockExportResult,
    export_mock_package,
    inspect_existing_mock_export,
    mock_export_destination,
)
from ai_company.application.mock_media import inspect_mock_hook, render_mock_hook
from ai_company.application.mock_text_assets import render_mock_text_assets


def mock_package_key(story_id: UUID) -> str:
    return f"mock-package:{story_id}:v1"


def _checkpoint(result: MockExportResult, duration: float) -> dict:
    return {
        "kind": "mock_package",
        "schema_version": 1,
        "is_mock": True,
        "output_profile_version": 1,
        "directory": str(result.directory),
        "hook_duration_seconds": duration,
        "artifacts": {
            name: {
                "sha256": item.sha256_hex,
                "byte_size": item.byte_size,
                "verified": item.verified,
                "is_mock": item.is_mock,
            }
            for name, item in result.evidence.items()
        },
    }


class MockPackageHandler:
    def __init__(self, tasks: TaskRepository, output_root: Path):
        self.tasks = tasks
        self.output_root = output_root

    def __call__(self, task_id: UUID) -> dict:
        story_id = self.tasks.get_task_story_id(task_id)
        blueprint = self.tasks.get_task_result_by_key(
            story_id, mock_blueprint_key(story_id), expected_type="mock_blueprint",
        )
        chapters = self.tasks.get_task_result_by_key(
            story_id, mock_chapters_key(story_id), expected_type="mock_chapters",
        )
        if blueprint["status"] != "completed" or chapters["status"] != "completed":
            raise ValueError("Mock blueprint and chapters must be complete before export.")
        plan = blueprint["checkpoint"]
        text_assets = render_mock_text_assets(plan, chapters["checkpoint"])
        at = self.tasks.get_task_created_at(task_id)
        destination = mock_export_destination(self.output_root, story_id, plan["title"], at)

        # A crash can occur after folder rename and before task completion.
        # Verify and reuse the existing result rather than replacing it.
        if destination.exists():
            result = inspect_existing_mock_export(destination)
            for name, data in text_assets.items():
                if (destination / name).read_bytes() != data:
                    raise ValueError("Existing mock export differs from the expected text assets.")
            duration = inspect_mock_hook(destination / "hook.mp4").duration_seconds
            return _checkpoint(result, duration)

        self.output_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".mock-build-", dir=self.output_root) as work_dir:
            work = Path(work_dir)
            sources = {}
            for name, data in text_assets.items():
                path = work / name
                path.write_bytes(data)
                sources[name] = path
            media = render_mock_hook(work / "hook.mp4")
            sources["hook.mp4"] = media.path
            result = export_mock_package(self.output_root, story_id, plan["title"], sources, at=at)
        return _checkpoint(result, media.duration_seconds)
