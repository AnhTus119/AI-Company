"""Fail-closed admission, provider routing, and cloud data rules."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import FrozenSet

from ai_company.domain.workflow import DomainError


class CampaignStatus(StrEnum):
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    AWAITING_RECOVERY = "awaiting_recovery_confirmation"


@dataclass(frozen=True)
class AdmissionContext:
    status: CampaignStatus
    production_ready_today: int
    daily_target: int = 60
    continue_authorized: bool = False
    pending_final_review: int = 0
    max_pending_approval: int = 10
    requested_concurrency: int = 1
    safe_concurrency: int = 1
    active_jobs: int = 0
    budget_available: bool = False


@dataclass(frozen=True)
class AdmissionDecision:
    allowed: bool
    reason: str
    effective_concurrency: int


def admission_decision(context: AdmissionContext) -> AdmissionDecision:
    if context.daily_target <= 0 or context.max_pending_approval <= 0:
        raise DomainError("Campaign limits must be positive.")
    effective = min(context.requested_concurrency, context.safe_concurrency)
    if effective <= 0:
        return AdmissionDecision(False, "no_safe_capacity", 0)
    if context.status != CampaignStatus.RUNNING:
        return AdmissionDecision(False, f"campaign_{context.status.value}", effective)
    if context.production_ready_today >= context.daily_target and not context.continue_authorized:
        return AdmissionDecision(False, "daily_target_reached", effective)
    if context.pending_final_review >= context.max_pending_approval:
        return AdmissionDecision(False, "final_review_queue_full", effective)
    if not context.budget_available:
        return AdmissionDecision(False, "budget_not_authorized", effective)
    if context.active_jobs >= effective:
        return AdmissionDecision(False, "concurrency_full", effective)
    return AdmissionDecision(True, "admitted", effective)


class DataCategory(StrEnum):
    SYNTHETIC_PROMPT = "synthetic_prompt"
    STORY_TEXT = "story_text"
    REFERENCE_MEDIA = "reference_media"
    MEDIA_ASSET = "media_asset"
    SECRET = "secret"
    INTERNAL_STATE = "internal_state"
    COST_ACCOUNT = "cost_account"
    PERSONAL_DATA = "personal_data"


ALWAYS_LOCAL = frozenset(
    {DataCategory.SECRET, DataCategory.INTERNAL_STATE, DataCategory.COST_ACCOUNT}
)


@dataclass(frozen=True)
class ProviderPermission:
    provider: str
    approved: bool
    allowed_categories: FrozenSet[DataCategory]
    prototype_only: bool = False


def assert_cloud_boundary(
    permission: ProviderPermission,
    categories: FrozenSet[DataCategory],
    *, prototype: bool,
) -> None:
    if not permission.approved:
        raise DomainError(f"Provider {permission.provider} is not approved.")
    if permission.prototype_only and not prototype:
        raise DomainError(f"Provider {permission.provider} is approved only for prototypes.")
    if categories & ALWAYS_LOCAL:
        raise DomainError("Local-only data cannot be sent to a cloud provider.")
    if not categories <= permission.allowed_categories:
        raise DomainError("The provider is not approved for every requested data category.")


@dataclass(frozen=True)
class ModelChoice:
    provider: str
    model: str
    capabilities: FrozenSet[str]
    approved: bool


@dataclass(frozen=True)
class AssignmentSnapshot:
    version: str
    workload: str
    primary: ModelChoice
    fallbacks: tuple[ModelChoice, ...] = ()
    activated_by_user: bool = False


@dataclass(frozen=True)
class RouteDecision:
    choice: ModelChoice
    assignment_version: str
    used_fallback: bool
    reason: str


def route_model(
    assignment: AssignmentSnapshot,
    required_capabilities: FrozenSet[str],
    unavailable_providers: FrozenSet[str] = frozenset(),
) -> RouteDecision:
    if not assignment.activated_by_user:
        raise DomainError("The assignment version has not been approved by the user.")
    for index, candidate in enumerate((assignment.primary, *assignment.fallbacks)):
        if (
            candidate.approved
            and candidate.provider not in unavailable_providers
            and required_capabilities <= candidate.capabilities
        ):
            return RouteDecision(
                candidate,
                assignment.version,
                index > 0,
                "primary" if index == 0 else "approved_fallback",
            )
    raise DomainError("No approved and capable model is available for this workload.")
