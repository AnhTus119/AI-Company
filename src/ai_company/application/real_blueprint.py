"""Bounded real-AI Story Bible/20-chapter-plan slice for one user-idea story."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError, field_validator

from ai_company.adapters.database import (
    BudgetRepository,
    GovernanceRepository,
    StoryRepository,
    TaskRepository,
)
from ai_company.application.provider_config import StoryAgentSettings
from ai_company.application.provider_factory import ProviderBinding
from ai_company.domain.policy import (
    AssignmentSnapshot,
    DataCategory,
    ModelChoice,
    ProviderPermission,
    assert_cloud_boundary,
    route_model,
)
from ai_company.domain.workflow import DomainError
from ai_company.providers.base import ProviderFailure, StructuredRequest


WORKLOAD = "story_bible"


def real_blueprint_key(story_id: UUID) -> str:
    return f"real-blueprint:{story_id}:v1"


class CharacterPlan(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    role: str = Field(min_length=1, max_length=120)
    motivation: str = Field(min_length=1, max_length=500)
    secret: str = Field(min_length=1, max_length=500)


class StoryBiblePlan(BaseModel):
    setting: str = Field(min_length=1, max_length=500)
    timeline: str = Field(min_length=1, max_length=1000)
    core_conflict: str = Field(min_length=1, max_length=1000)
    emotional_arc: str = Field(min_length=1, max_length=1000)
    ending: str = Field(min_length=1, max_length=1000)
    characters: list[CharacterPlan] = Field(min_length=2, max_length=8)


class ChapterObjective(BaseModel):
    number: int = Field(ge=1, le=20)
    objective: str = Field(min_length=1, max_length=700)
    reveal_or_turn: str = Field(min_length=1, max_length=700)


class HookContractPlan(BaseModel):
    hook_event: str = Field(min_length=1, max_length=700)
    stakes: str = Field(min_length=1, max_length=700)
    open_loop: str = Field(min_length=1, max_length=700)
    chapter_one_handoff: str = Field(min_length=1, max_length=700)
    planned_payoff_chapter: int = Field(ge=1, le=20)


class RealBlueprint(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    story_bible: StoryBiblePlan
    chapter_plan: list[ChapterObjective] = Field(min_length=20, max_length=20)
    hook_contract: HookContractPlan

    @field_validator("chapter_plan")
    @classmethod
    def sequential_plan(cls, plan: list[ChapterObjective]) -> list[ChapterObjective]:
        if [item.number for item in plan] != list(range(1, 21)):
            raise ValueError("Chapter plan must contain sequential chapters 1 through 20.")
        return plan


REAL_BLUEPRINT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["title", "story_bible", "chapter_plan", "hook_contract"],
    "properties": {
        "title": {"type": "string", "description": "Original English drama story title."},
        "story_bible": {
            "type": "object",
            "additionalProperties": False,
            "required": ["setting", "timeline", "core_conflict", "emotional_arc", "ending", "characters"],
            "properties": {
                "setting": {"type": "string"},
                "timeline": {"type": "string"},
                "core_conflict": {"type": "string"},
                "emotional_arc": {"type": "string"},
                "ending": {"type": "string"},
                "characters": {
                    "type": "array", "minItems": 2, "maxItems": 8,
                    "items": {
                        "type": "object", "additionalProperties": False,
                        "required": ["name", "role", "motivation", "secret"],
                        "properties": {
                            "name": {"type": "string"}, "role": {"type": "string"},
                            "motivation": {"type": "string"}, "secret": {"type": "string"},
                        },
                    },
                },
            },
        },
        "chapter_plan": {
            "type": "array", "minItems": 20, "maxItems": 20,
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["number", "objective", "reveal_or_turn"],
                "properties": {
                    "number": {"type": "integer", "minimum": 1, "maximum": 20},
                    "objective": {"type": "string"},
                    "reveal_or_turn": {"type": "string"},
                },
            },
        },
        "hook_contract": {
            "type": "object", "additionalProperties": False,
            "required": ["hook_event", "stakes", "open_loop", "chapter_one_handoff", "planned_payoff_chapter"],
            "properties": {
                "hook_event": {"type": "string"}, "stakes": {"type": "string"},
                "open_loop": {"type": "string"}, "chapter_one_handoff": {"type": "string"},
                "planned_payoff_chapter": {"type": "integer", "minimum": 1, "maximum": 20},
            },
        },
    },
}


def _prompt(premise: str) -> str:
    if not premise.strip() or len(premise) > 4000:
        raise DomainError("A real Story Bible premise must contain 1–4000 characters.")
    return (
        "Create an original English-language drama blueprint for an adult Facebook reading audience. "
        "The story must be fictional, emotionally clear, mobile-readable, and designed for exactly 20 sequential "
        "chapters of 500–700 words later. Resolve the core conflict by chapter 20. Do not include sexual content "
        "involving minors, graphic violence, hate, political persuasion, or copied characters/dialogue. Keep the "
        "main cast compact. The hook is Chapter 0 and must hand off coherently to Chapter 1. Return only the JSON "
        "required by the supplied schema.\n\nUSER PREMISE:\n" + premise.strip()
    )


def _approved_route(
    governance: GovernanceRepository,
    settings: StoryAgentSettings,
    unavailable_providers: frozenset[str],
):
    policy, assignments = governance.approved_context(
        settings.policy_version, settings.assignment_version,
    )
    workload = assignments.get(WORKLOAD, {})

    def choice(document: dict) -> ModelChoice:
        return ModelChoice(
            str(document.get("provider", "")), str(document.get("model", "")),
            frozenset(document.get("capabilities", [])), bool(document.get("approved")),
        )

    routed = route_model(
        AssignmentSnapshot(
            settings.assignment_version,
            WORKLOAD,
            choice(workload.get("primary", {})),
            tuple(choice(item) for item in workload.get("fallbacks", [])),
            activated_by_user=True,
        ),
        frozenset({"text", "structured_output"}),
        unavailable_providers,
    )
    binding = settings.providers.get(routed.choice.provider)
    if binding is None or routed.choice.model != binding.model:
        raise DomainError("Configured provider/model does not match the active assignment snapshot.")
    provider_data = policy.get("provider_permissions", {}).get(routed.choice.provider, {})
    categories = frozenset(DataCategory(item) for item in provider_data.get("allowed_categories", []))
    assert_cloud_boundary(
        ProviderPermission(
            routed.choice.provider, bool(provider_data.get("approved")), categories,
            prototype_only=bool(provider_data.get("prototype_only", True)),
        ),
        frozenset({DataCategory.SYNTHETIC_PROMPT, DataCategory.STORY_TEXT}),
        prototype=True,
    )
    return routed


class RealBlueprintHandler:
    def __init__(
        self,
        stories: StoryRepository,
        tasks: TaskRepository,
        governance: GovernanceRepository,
        budgets: BudgetRepository,
        providers: dict[str, ProviderBinding],
        settings: StoryAgentSettings,
        worker_id: str,
    ) -> None:
        self.stories = stories
        self.tasks = tasks
        self.governance = governance
        self.budgets = budgets
        self.providers = providers
        self.settings = settings
        self.worker_id = worker_id

    def __call__(self, task_id: UUID) -> dict:
        story_id = self.tasks.get_task_story_id(task_id)
        attempt_id = self.tasks.get_active_attempt_id(task_id, self.worker_id)
        prompt = _prompt(self.stories.get_story_idea(story_id))
        schema_bytes = json.dumps(REAL_BLUEPRINT_SCHEMA, separators=(",", ":")).encode("utf-8")
        input_upper_bound = len(prompt.encode("utf-8")) + len(schema_bytes) + 2048
        unavailable: set[str] = set()
        last_failure: ProviderFailure | None = None
        while len(unavailable) < len(self.providers):
            routed = _approved_route(self.governance, self.settings, frozenset(unavailable))
            binding = self.providers.get(routed.choice.provider)
            if binding is None:
                raise DomainError("Approved provider is not loaded in this worker.")
            estimate = binding.rate_card.upper_bound(input_upper_bound, binding.max_output_tokens)
            now = datetime.now(timezone.utc)
            reservation_id = self.budgets.reserve(
                self.settings.budget_version, attempt_id, WORKLOAD, estimate, now,
            )
            try:
                call_id = self.governance.start_provider_call(
                    task_attempt_id=attempt_id,
                    policy_version=self.settings.policy_version,
                    assignment_version=self.settings.assignment_version,
                    provider_key=binding.provider.provider_key,
                    model_key=binding.provider.model_key,
                    workload=WORKLOAD,
                    requested_at=now,
                    estimated_minor=estimate,
                    currency=binding.rate_card.currency,
                    rate_card_version=binding.rate_card.version,
                    used_fallback=routed.used_fallback,
                    route_reason=routed.reason,
                    budget_decision_id=reservation_id,
                )
            except Exception:
                self.budgets.release(reservation_id, datetime.now(timezone.utc))
                raise
            try:
                result = binding.provider.generate_structured(StructuredRequest(
                    prompt=prompt, json_schema=REAL_BLUEPRINT_SCHEMA,
                    max_output_tokens=binding.max_output_tokens,
                ))
                blueprint = RealBlueprint.model_validate(result.value)
                actual = binding.rate_card.actual(result.usage)
                if actual > estimate:
                    raise ProviderFailure("cost_exceeded_reservation", retryable=False)
            except ValidationError as exc:
                failure = ProviderFailure("invalid_structured_output", retryable=False)
                failure.__cause__ = exc
            except ProviderFailure as exc:
                failure = exc
            except Exception as exc:
                failure = ProviderFailure("provider_handler_error", retryable=False)
                failure.__cause__ = exc
            else:
                finished = datetime.now(timezone.utc)
                self.governance.finish_provider_call(
                    call_id, completed_at=finished,
                    usage=result.usage.as_ledger_document(), actual_minor=actual,
                )
                self.budgets.settle(reservation_id, actual, finished)
                break
            finished = datetime.now(timezone.utc)
            self.governance.finish_provider_call(
                call_id, completed_at=finished, usage={}, actual_minor=None, error_code=failure.code,
            )
            self.budgets.settle(reservation_id, estimate, finished)
            last_failure = failure
            if not failure.retryable:
                raise failure
            unavailable.add(routed.choice.provider)
        else:
            raise last_failure or ProviderFailure("no_provider_available", retryable=True)
        return {
            "kind": "story_blueprint", "schema_version": 1, "is_mock": False,
            **blueprint.model_dump(),
            "audit": {
                "provider_call_id": str(call_id),
                "budget_reservation_id": str(reservation_id),
                "provider": binding.provider.provider_key,
                "model": binding.provider.model_key,
                "used_fallback": routed.used_fallback,
                "assignment_version": self.settings.assignment_version,
                "policy_version": self.settings.policy_version,
            },
        }
