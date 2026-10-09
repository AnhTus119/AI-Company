from dataclasses import replace

import pytest

from ai_company.domain.policy import (
    AdmissionContext,
    AssignmentSnapshot,
    CampaignStatus,
    DataCategory,
    ModelChoice,
    ProviderPermission,
    admission_decision,
    assert_cloud_boundary,
    route_model,
)
from ai_company.domain.workflow import DomainError


def test_admission_stops_at_review_limit_and_daily_target() -> None:
    base = AdmissionContext(CampaignStatus.RUNNING, 0, budget_available=True, requested_concurrency=8, safe_concurrency=2)
    assert admission_decision(base).effective_concurrency == 2
    assert admission_decision(replace(base, pending_final_review=10)).reason == "final_review_queue_full"
    assert admission_decision(replace(base, production_ready_today=60)).reason == "daily_target_reached"
    assert admission_decision(replace(base, status=CampaignStatus.AWAITING_RECOVERY)).allowed is False


def test_gemini_prototype_boundary_is_narrow() -> None:
    permission = ProviderPermission("gemini", True, frozenset({DataCategory.SYNTHETIC_PROMPT}), prototype_only=True)
    assert_cloud_boundary(permission, frozenset({DataCategory.SYNTHETIC_PROMPT}), prototype=True)
    with pytest.raises(DomainError):
        assert_cloud_boundary(permission, frozenset({DataCategory.REFERENCE_MEDIA}), prototype=True)
    with pytest.raises(DomainError):
        assert_cloud_boundary(permission, frozenset({DataCategory.SECRET}), prototype=True)
    with pytest.raises(DomainError):
        assert_cloud_boundary(permission, frozenset({DataCategory.SYNTHETIC_PROMPT}), prototype=False)


def test_fallback_must_be_approved_and_capable() -> None:
    primary = ModelChoice("a", "model-a", frozenset({"text"}), True)
    fallback = ModelChoice("b", "model-b", frozenset({"text", "json"}), True)
    assignment = AssignmentSnapshot("v1", "story_bible", primary, (fallback,), True)
    chosen = route_model(assignment, frozenset({"json"}))
    assert chosen.choice == fallback and chosen.used_fallback
    with pytest.raises(DomainError):
        route_model(replace(assignment, activated_by_user=False), frozenset({"text"}))
    with pytest.raises(DomainError):
        route_model(replace(assignment, fallbacks=(replace(fallback, approved=False),)), frozenset({"json"}))
