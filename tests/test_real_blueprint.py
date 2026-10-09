from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select

from ai_company.adapters.database import (
    BudgetRepository, CostLedgerRow, GovernanceRepository, ProviderCallRow,
    StoryRepository, TaskRepository, initialize_lite_schema, make_session_factory,
)
from ai_company.application.capacity import ResourceSnapshot
from ai_company.application.provider_config import GeminiPrototypeSettings
from ai_company.application.real_blueprint import RealBlueprintHandler, real_blueprint_key
from ai_company.application.runtime import load_runtime_settings
from ai_company.domain.workflow import SourceType
from ai_company.providers.base import ProviderUsage, StructuredResult, TokenRateCard
from ai_company.worker.lite import LiteWorker


class FakeStructuredProvider:
    provider_key = "gemini"
    model_key = "gemini-test-model"

    def generate_structured(self, request):
        assert request.max_output_tokens == 6000
        return StructuredResult({
            "title": "The Door She Never Opened",
            "story_bible": {
                "setting": "A fictional coastal town.",
                "timeline": "Events unfold over three weeks.",
                "core_conflict": "A mother must confront a family deception.",
                "emotional_arc": "Distrust develops into painful clarity and measured forgiveness.",
                "ending": "The deception is exposed and the family chooses an honest future.",
                "characters": [
                    {"name": "Mara", "role": "protagonist", "motivation": "protect her family", "secret": "she hid an old letter"},
                    {"name": "Eli", "role": "brother", "motivation": "repair the past", "secret": "he knows who sent it"},
                ],
            },
            "chapter_plan": [
                {"number": number, "objective": f"Advance conflict {number}", "reveal_or_turn": f"Turn {number}"}
                for number in range(1, 21)
            ],
            "hook_contract": {
                "hook_event": "Mara finds a letter beneath the door.",
                "stakes": "Opening it may fracture her family.",
                "open_loop": "Who delivered the letter?",
                "chapter_one_handoff": "Chapter 1 begins moments before the delivery.",
                "planned_payoff_chapter": 18,
            },
        }, ProviderUsage(900, 1100, 2000))


def test_real_blueprint_requires_approved_route_and_budget_then_audits_call(tmp_path) -> None:
    runtime = load_runtime_settings({"AI_COMPANY_DATA_DIR": str(tmp_path)})
    sessions = make_session_factory(runtime.database_url)
    initialize_lite_schema(sessions)
    stories = StoryRepository(sessions)
    campaign_id = stories.create_campaign("Real trial", SourceType.USER_IDEA, 1)
    story_id = stories.create_story(campaign_id, SourceType.USER_IDEA, "A family receives an impossible letter.")
    tasks = TaskRepository(sessions)
    now = datetime.now(timezone.utc)
    task_id = tasks.create_task(story_id, "real_blueprint", real_blueprint_key(story_id), now)
    governance = GovernanceRepository(sessions)
    governance.create_policy_version("policy-real-v1", {
        "provider_permissions": {"gemini": {
            "approved": True, "prototype_only": True,
            "allowed_categories": ["synthetic_prompt", "story_text"],
        }}
    })
    governance.approve_policy_version("policy-real-v1", "owner", now)
    governance.create_assignment_version("models-real-v1", {
        "story_bible": {"primary": {
            "provider": "gemini", "model": "gemini-test-model",
            "capabilities": ["text", "structured_output"], "approved": True,
        }}
    })
    governance.activate_assignment_version("models-real-v1", "owner", now)
    budgets = BudgetRepository(sessions)
    budgets.create_policy("budget-real-v1", "USD", 100, "Asia/Ho_Chi_Minh")
    budgets.activate_policy("budget-real-v1", "owner", now)
    settings = GeminiPrototypeSettings(
        enabled=True, api_key="unused", model="gemini-test-model",
        policy_version="policy-real-v1", assignment_version="models-real-v1",
        budget_version="budget-real-v1", daily_budget_minor=100,
        rate_card=TokenRateCard("test-rate", "USD", 75, 375),
        max_output_tokens=6000, timeout_seconds=60,
    )
    worker_id = "real-test-worker"
    handler = RealBlueprintHandler(
        stories, tasks, governance, budgets, FakeStructuredProvider(), settings, worker_id,
    )
    worker = LiteWorker(
        tasks, {"real_blueprint": handler}, worker_id,
        lambda: ResourceSnapshot(4096, 1024, 4),
    )
    assert worker.run_once(provider_slots=1, budget_slots=1) == "completed"
    result = tasks.get_task_result(task_id, story_id, expected_type="real_blueprint")
    assert result["checkpoint"]["is_mock"] is False
    assert len(result["checkpoint"]["chapter_plan"]) == 20
    with sessions() as session:
        call = session.scalar(select(ProviderCallRow))
        cost = session.scalar(select(CostLedgerRow))
        assert call.status == "completed" and call.model_key == "gemini-test-model"
        assert cost.actual_minor is not None and cost.actual_minor <= cost.estimated_minor
