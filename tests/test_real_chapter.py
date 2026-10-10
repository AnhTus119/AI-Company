from datetime import datetime, timezone
from uuid import UUID

import pytest
from sqlalchemy import func, select

from ai_company.adapters.database import (
    BudgetRepository,
    GovernanceRepository,
    NovelWorkspaceRepository,
    ProviderCallRow,
    StoryRepository,
    TaskRepository,
    initialize_lite_schema,
    make_session_factory,
)
from ai_company.application.agent_runner import BudgetedStructuredAgentRunner
from ai_company.application.novel_workspace import NovelWorkspace, materialize_workspace
from ai_company.application.provider_config import (
    AgentRouteSettings,
    ProviderModelSettings,
    StoryAgentSettings,
)
from ai_company.application.provider_factory import ProviderBinding
from ai_company.application.real_chapter import (
    CHAPTER_TASK_TYPE,
    RealChapterPipelineHandler,
    real_chapter_key,
)
from ai_company.application.capacity import ResourceSnapshot
from ai_company.domain.workflow import SourceType
from ai_company.providers.base import ProviderUsage, StructuredResult, TokenRateCard
from ai_company.worker.lite import LiteWorker


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
            "chapter_one_handoff": "Begin before delivery.", "planned_payoff_chapter": 18,
        },
        "audit": {"provider": "gemini", "model": "gemini-test"},
    }


class SequentialProvider:
    provider_key = "gemini"
    model_key = "gemini-test"

    def __init__(self, qc_passed: bool) -> None:
        self.qc_passed = qc_passed
        self.calls = 0

    def generate_structured(self, request):
        self.calls += 1
        content = " ".join(["Mara read the letter and faced the truth with Eli."] * 60)
        if "passed" in request.json_schema.get("properties", {}):
            return StructuredResult({
                "title": "The Letter", "content": content,
                "summary": "Mara confronts Eli about the letter.",
                "editor_notes": ["Completed internal edit."],
                "passed": self.qc_passed,
                "continuity_issues": [] if self.qc_passed else ["The reveal occurs too early."],
                "unresolved_risks": [],
                "continuity_notes": ["Mara now distrusts Eli."],
                "new_open_loops": ["Why was the seal broken?"],
                "close_open_loops": [],
            }, ProviderUsage(100, 100, 200))
        if self.calls == 1:
            value = {
                "title": "The Letter", "content": content,
                "summary": "Mara confronts Eli about the letter.",
                "continuity_notes": ["Mara now distrusts Eli."],
                "new_open_loops": ["Why was the seal broken?"],
            }
        elif self.calls == 2:
            value = {
                "title": "The Letter", "content": content,
                "summary": "Mara confronts Eli about the letter.",
                "editor_notes": ["Tightened pacing."],
            }
        else:
            value = {
                "passed": self.qc_passed,
                "continuity_issues": [] if self.qc_passed else ["The reveal occurs too early."],
                "unresolved_risks": [],
                "continuity_notes": ["Mara now distrusts Eli."],
                "new_open_loops": ["Why was the seal broken?"],
                "close_open_loops": [],
            }
        return StructuredResult(value, ProviderUsage(100, 100, 200))


def pipeline(tmp_path, qc_passed: bool, *, auto_continue: bool = False, fast: bool = False):
    sessions = make_session_factory(f"sqlite:///{tmp_path / 'chapter.sqlite3'}")
    initialize_lite_schema(sessions)
    stories = StoryRepository(sessions)
    campaign_id = stories.create_campaign("Real chapter", SourceType.USER_IDEA, 1)
    story_id = stories.create_story(campaign_id, SourceType.USER_IDEA, "A family receives a letter.")
    workspaces = NovelWorkspaceRepository(sessions)
    workspaces.create_or_get(story_id, materialize_workspace(story_id, blueprint()).model_dump(mode="json"))
    tasks = TaskRepository(sessions)
    now = datetime.now(timezone.utc)
    task_id = tasks.create_task(
        story_id, CHAPTER_TASK_TYPE, real_chapter_key(story_id, 1, 1), now,
        request_payload={
            "chapter_number": 1, "workspace_version": 1,
            "auto_continue": auto_continue,
        },
    )
    governance = GovernanceRepository(sessions)
    governance.create_policy_version("policy-v1", {"provider_permissions": {"gemini": {
        "approved": True, "prototype_only": True,
        "allowed_categories": ["synthetic_prompt", "story_text"],
    }}})
    governance.approve_policy_version("policy-v1", "owner", now)
    assignment = {"primary": {
        "provider": "gemini", "model": "gemini-test",
        "capabilities": ["text", "structured_output"], "approved": True,
    }}
    governance.create_assignment_version("models-v1", {
        role: assignment for role in ("chapter_writer", "chapter_editor", "continuity_qc")
    })
    governance.activate_assignment_version("models-v1", "owner", now)
    budgets = BudgetRepository(sessions)
    budgets.create_policy("budget-v1", "USD", 100, "Asia/Ho_Chi_Minh")
    budgets.activate_policy("budget-v1", "owner", now)
    rate = TokenRateCard("rate-v1", "USD", 100, 500)
    route = AgentRouteSettings("gemini", ())
    settings = StoryAgentSettings(
        True, "policy-v1", "models-v1", "budget-v1", 100,
        "gemini", (),
        {"gemini": ProviderModelSettings("gemini", "unused", "gemini-test", None, rate, 6000, 60)},
        {role: route for role in ("chapter_writer", "chapter_editor", "continuity_qc")},
        chapter_pipeline_mode="fast" if fast else "quality",
    )
    provider = SequentialProvider(qc_passed)
    runner = BudgetedStructuredAgentRunner(
        governance, budgets, {"gemini": ProviderBinding(provider, rate, 6000)}, settings,
    )
    worker_id = "chapter-worker"
    handler = RealChapterPipelineHandler(tasks, workspaces, runner, worker_id)
    worker = LiteWorker(
        tasks, {CHAPTER_TASK_TYPE: handler}, worker_id,
        lambda: ResourceSnapshot(4096, 1024, 4),
    )
    return sessions, story_id, task_id, tasks, workspaces, provider, worker


@pytest.mark.parametrize("qc_passed, expected_state, chapter_count", [
    (True, "saved", 1),
    (False, "needs_revision", 0),
])
def test_real_chapter_pipeline_saves_only_after_qc(
    tmp_path, qc_passed: bool, expected_state: str, chapter_count: int,
) -> None:
    sessions, story_id, task_id, tasks, workspaces, provider, worker = pipeline(tmp_path, qc_passed)
    assert worker.run_once(provider_slots=1, budget_slots=1) == "completed"
    result = tasks.get_task_result(task_id, story_id, expected_type=CHAPTER_TASK_TYPE)
    assert result["checkpoint"]["state"] == expected_state
    workspace = NovelWorkspace.model_validate(workspaces.get(story_id)["workspace"])
    assert len(workspace.chapters) == chapter_count
    assert provider.calls == 3
    with sessions() as session:
        assert session.scalar(select(func.count(ProviderCallRow.id))) == 3


def test_successful_auto_pipeline_queues_next_chapter_with_new_workspace_version(tmp_path) -> None:
    _, story_id, _, tasks, _, _, worker = pipeline(tmp_path, True, auto_continue=True)
    assert worker.run_once(provider_slots=1, budget_slots=1) == "completed"
    next_result = tasks.get_task_result_by_key(
        story_id, real_chapter_key(story_id, 2, 2), expected_type=CHAPTER_TASK_TYPE,
    )
    assert next_result["status"] == "queued"
    assert tasks.get_task_request(UUID(next_result["task_id"])) == {
        "chapter_number": 2, "workspace_version": 2, "auto_continue": True,
    }


def test_fast_pipeline_uses_one_provider_call_and_still_requires_qc_pass(tmp_path) -> None:
    sessions, story_id, task_id, tasks, workspaces, provider, worker = pipeline(
        tmp_path, True, fast=True,
    )
    assert worker.run_once(provider_slots=1, budget_slots=1) == "completed"
    result = tasks.get_task_result(task_id, story_id, expected_type=CHAPTER_TASK_TYPE)
    assert result["checkpoint"]["state"] == "saved"
    assert result["checkpoint"]["pipeline_mode"] == "fast"
    assert len(NovelWorkspace.model_validate(workspaces.get(story_id)["workspace"]).chapters) == 1
    assert provider.calls == 1
    with sessions() as session:
        assert session.scalar(select(func.count(ProviderCallRow.id))) == 1
