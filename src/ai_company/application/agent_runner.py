"""Budgeted, policy-approved structured agent execution shared by story roles."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TypeVar
from uuid import UUID

from pydantic import BaseModel, ValidationError

from ai_company.adapters.database import BudgetRepository, GovernanceRepository
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


OutputModel = TypeVar("OutputModel", bound=BaseModel)


def _choice(document: dict) -> ModelChoice:
    return ModelChoice(
        str(document.get("provider", "")),
        str(document.get("model", "")),
        frozenset(document.get("capabilities", [])),
        bool(document.get("approved")),
    )


class BudgetedStructuredAgentRunner:
    """Run one role through immutable routing, cloud-boundary, budget, and audit checks."""

    def __init__(
        self,
        governance: GovernanceRepository,
        budgets: BudgetRepository,
        providers: dict[str, ProviderBinding],
        settings: StoryAgentSettings,
    ) -> None:
        self.governance = governance
        self.budgets = budgets
        self.providers = providers
        self.settings = settings

    def _approved_route(self, workload: str, unavailable: frozenset[str]):
        policy, assignments = self.governance.approved_context(
            self.settings.policy_version, self.settings.assignment_version,
        )
        workload_assignment = assignments.get(workload, {})
        routed = route_model(
            AssignmentSnapshot(
                self.settings.assignment_version,
                workload,
                _choice(workload_assignment.get("primary", {})),
                tuple(_choice(item) for item in workload_assignment.get("fallbacks", [])),
                activated_by_user=True,
            ),
            frozenset({"text", "structured_output"}),
            unavailable,
        )
        binding = self.settings.providers.get(routed.choice.provider)
        if binding is None or routed.choice.model != binding.model:
            raise DomainError("Configured provider/model does not match the active assignment snapshot.")
        permission = policy.get("provider_permissions", {}).get(routed.choice.provider, {})
        assert_cloud_boundary(
            ProviderPermission(
                routed.choice.provider,
                bool(permission.get("approved")),
                frozenset(DataCategory(item) for item in permission.get("allowed_categories", [])),
                prototype_only=bool(permission.get("prototype_only", True)),
            ),
            frozenset({DataCategory.SYNTHETIC_PROMPT, DataCategory.STORY_TEXT}),
            prototype=True,
        )
        return routed

    def run(
        self,
        *,
        attempt_id: UUID,
        workload: str,
        prompt: str,
        json_schema: dict,
        output_model: type[OutputModel],
    ) -> tuple[OutputModel, dict]:
        route = self.settings.route_for(workload)
        schema_bytes = json.dumps(json_schema, separators=(",", ":")).encode("utf-8")
        input_upper_bound = len(prompt.encode("utf-8")) + len(schema_bytes) + 2048
        unavailable: set[str] = set()
        last_failure: ProviderFailure | None = None
        while len(unavailable) < len(route.ordered_providers):
            routed = self._approved_route(workload, frozenset(unavailable))
            binding = self.providers.get(routed.choice.provider)
            if binding is None:
                raise DomainError("Approved provider is not loaded in this worker.")
            estimate = binding.rate_card.upper_bound(input_upper_bound, binding.max_output_tokens)
            now = datetime.now(timezone.utc)
            reservation_id = self.budgets.reserve(
                self.settings.budget_version, attempt_id, workload, estimate, now,
            )
            try:
                call_id = self.governance.start_provider_call(
                    task_attempt_id=attempt_id,
                    policy_version=self.settings.policy_version,
                    assignment_version=self.settings.assignment_version,
                    provider_key=binding.provider.provider_key,
                    model_key=binding.provider.model_key,
                    workload=workload,
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
                    prompt=prompt,
                    json_schema=json_schema,
                    max_output_tokens=binding.max_output_tokens,
                    reasoning_effort=self.settings.reasoning_effort_for(workload),
                    service_tier=binding.service_tier,
                ))
                value = output_model.model_validate(result.value)
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
                    call_id,
                    completed_at=finished,
                    usage=result.usage.as_ledger_document(),
                    actual_minor=actual,
                )
                self.budgets.settle(reservation_id, actual, finished)
                return value, {
                    "provider_call_id": str(call_id),
                    "budget_reservation_id": str(reservation_id),
                    "provider": binding.provider.provider_key,
                    "model": binding.provider.model_key,
                    "used_fallback": routed.used_fallback,
                    "assignment_version": self.settings.assignment_version,
                    "policy_version": self.settings.policy_version,
                    "workload": workload,
                }
            finished = datetime.now(timezone.utc)
            self.governance.finish_provider_call(
                call_id,
                completed_at=finished,
                usage={},
                actual_minor=None,
                error_code=failure.code,
            )
            self.budgets.settle(reservation_id, estimate, finished)
            last_failure = failure
            if not failure.retryable:
                raise failure
            unavailable.add(routed.choice.provider)
        raise last_failure or ProviderFailure("no_provider_available", retryable=True)
