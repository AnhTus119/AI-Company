"""Offline sequential chapter fixtures for workflow validation."""

from __future__ import annotations

from uuid import UUID

from ai_company.adapters.database import TaskRepository
from ai_company.application.mock_blueprint import validate_mock_blueprint
from ai_company.domain.workflow import Chapter, SourceType, StorySnapshot, StoryStage, accept_chapter


def mock_blueprint_key(story_id: UUID) -> str:
    return f"mock-blueprint:{story_id}:v1"


def mock_chapters_key(story_id: UUID) -> str:
    return f"mock-chapters:{story_id}:v1"


class DeterministicMockChapterProvider:
    """Exercise continuity and ordering without claiming creative quality."""

    def generate(self, blueprint: dict) -> dict:
        validate_mock_blueprint(blueprint)
        snapshot = StorySnapshot(
            id=UUID(int=0), source_type=SourceType.USER_IDEA,
            stage=StoryStage.CHAPTERS, planned_chapters=20,
            has_story_bible=True, has_hook_contract=True,
        )
        chapters: list[dict] = []
        prior_state = "hook_handoff"
        for objective in blueprint["chapter_plan"]:
            number = objective["number"]
            next_state = f"synthetic_state_{number:02d}"
            recap = None if number == 1 else f"Synthetic recap of {prior_state}."
            content = (
                f"Synthetic chapter {number:02d} follows {objective['objective']}. "
                f"It receives {prior_state} and establishes {next_state}. "
                "This text is a fixture for workflow testing, not reader-facing prose."
            )
            chapter = Chapter(number, f"Synthetic Chapter {number:02d}", content, recap)
            snapshot = accept_chapter(snapshot, chapter)
            chapters.append({
                "number": chapter.number,
                "title": chapter.title,
                "recap": chapter.recap,
                "content": chapter.content,
                "continuity_in": prior_state,
                "continuity_out": next_state,
            })
            prior_state = next_state
        return {
            "kind": "mock_chapters",
            "schema_version": 1,
            "is_mock": True,
            "chapter_count": len(snapshot.chapters),
            "chapters": chapters,
        }


class MockChaptersHandler:
    def __init__(self, tasks: TaskRepository):
        self.tasks = tasks
        self.provider = DeterministicMockChapterProvider()

    def __call__(self, task_id: UUID) -> dict:
        story_id = self.tasks.get_task_story_id(task_id)
        blueprint = self.tasks.get_task_result_by_key(
            story_id, mock_blueprint_key(story_id), expected_type="mock_blueprint",
        )
        if blueprint["status"] != "completed" or blueprint["checkpoint"] is None:
            raise ValueError("A completed mock blueprint is required before chapters.")
        return self.provider.generate(blueprint["checkpoint"])
