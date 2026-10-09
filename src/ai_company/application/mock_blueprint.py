"""Deterministic, offline blueprint fixture for orchestration smoke tests.

This is deliberately not creative output and must never pass production gates.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Protocol
from uuid import UUID

from ai_company.adapters.database import StoryRepository, TaskRepository


class BlueprintProvider(Protocol):
    def generate(self, premise: str) -> dict: ...


class DeterministicMockBlueprintProvider:
    """Return stable, clearly synthetic data without a network call."""

    def generate(self, premise: str) -> dict:
        seed = sha256(premise.strip().encode("utf-8")).hexdigest()[:12]
        return {
            "kind": "mock_story_blueprint",
            "schema_version": 1,
            "is_mock": True,
            "title": f"Synthetic Story {seed}",
            "story_bible": {
                "is_mock": True,
                "characters": ["Synthetic protagonist", "Synthetic counterpart"],
                "core_conflict": "Synthetic conflict for workflow validation",
                "timeline": "A synthetic sequence of twenty chapters",
                "ending": "Synthetic resolution in chapter twenty",
            },
            "chapter_plan": [
                {"number": number, "objective": f"Synthetic objective {number:02d}"}
                for number in range(1, 21)
            ],
            "hook_contract": {
                "hook_event": "Synthetic event for pipeline validation",
                "chapter_one_handoff": "Synthetic handoff for pipeline validation",
                "planned_payoff_chapter": 20,
            },
        }


def validate_mock_blueprint(payload: dict) -> None:
    """Reject malformed fixtures before a task is checkpointed."""
    if payload.get("kind") != "mock_story_blueprint" or payload.get("is_mock") is not True:
        raise ValueError("A blueprint smoke test must remain explicitly mock.")
    bible = payload.get("story_bible")
    if not isinstance(bible, dict) or bible.get("is_mock") is not True:
        raise ValueError("A mock Story Bible is required.")
    if not isinstance(bible.get("characters"), list) or not bible["characters"]:
        raise ValueError("A mock Story Bible needs characters.")
    if not all(isinstance(value, str) and value.strip() for value in bible["characters"]):
        raise ValueError("Mock characters must be non-empty.")
    if not all(isinstance(bible.get(key), str) and bible[key].strip()
               for key in ("core_conflict", "timeline", "ending")):
        raise ValueError("A mock Story Bible needs conflict, timeline, and ending.")
    plan = payload.get("chapter_plan")
    if not isinstance(plan, list) or len(plan) != 20:
        raise ValueError("A mock blueprint needs 20 chapter objectives.")
    if [item.get("number") for item in plan if isinstance(item, dict)] != list(range(1, 21)):
        raise ValueError("Mock chapter objectives must be sequential.")
    if not all(isinstance(item.get("objective"), str) and item["objective"].strip()
               for item in plan if isinstance(item, dict)):
        raise ValueError("Mock chapter objectives must be non-empty.")
    hook = payload.get("hook_contract")
    if not isinstance(hook, dict) or not all(
        isinstance(hook.get(key), str) and hook[key].strip()
        for key in ("hook_event", "chapter_one_handoff")
    ) or hook.get("planned_payoff_chapter") not in range(1, 21):
        raise ValueError("A mock blueprint needs a valid hook contract.")


class MockBlueprintHandler:
    def __init__(self, stories: StoryRepository, tasks: TaskRepository, provider: BlueprintProvider):
        self.stories = stories
        self.tasks = tasks
        self.provider = provider

    def __call__(self, task_id: UUID) -> dict:
        story_id = self.tasks.get_task_story_id(task_id)
        premise = self.stories.get_story_idea(story_id)
        payload = self.provider.generate(premise)
        validate_mock_blueprint(payload)
        return payload
