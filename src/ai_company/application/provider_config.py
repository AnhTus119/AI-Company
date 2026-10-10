"""Fail-closed configuration for approved story agents and their providers."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Mapping

from ai_company.domain.workflow import DomainError
from ai_company.providers.base import TokenRateCard


SUPPORTED_PROVIDERS = ("openai", "gemini")
ROLE_WORKLOADS = {
    "story_architect": "story_bible",
    "chapter_writer": "chapter_writer",
    "editor": "chapter_editor",
    "continuity_qc": "continuity_qc",
}


def _positive_int(values: Mapping[str, str], key: str, *, allow_zero: bool = False) -> int:
    try:
        value = int(values.get(key, ""))
    except ValueError as exc:
        raise DomainError(f"{key} must be an integer.") from exc
    if value < 0 or (value == 0 and not allow_zero):
        raise DomainError(f"{key} must be {'non-negative' if allow_zero else 'positive'}.")
    return value


@dataclass(frozen=True)
class ProviderModelSettings:
    provider_key: str
    api_key: str
    model: str
    base_url: str | None
    rate_card: TokenRateCard
    max_output_tokens: int
    timeout_seconds: int


@dataclass(frozen=True)
class AgentRouteSettings:
    primary_provider: str
    fallback_providers: tuple[str, ...]

    @property
    def ordered_providers(self) -> tuple[str, ...]:
        return (self.primary_provider, *self.fallback_providers)


@dataclass(frozen=True)
class StoryAgentSettings:
    enabled: bool
    policy_version: str
    assignment_version: str
    budget_version: str
    daily_budget_minor: int
    primary_provider: str
    fallback_providers: tuple[str, ...]
    providers: dict[str, ProviderModelSettings]
    routes: dict[str, AgentRouteSettings] = field(default_factory=dict)

    @property
    def ordered_providers(self) -> tuple[str, ...]:
        return (self.primary_provider, *self.fallback_providers)

    @property
    def model(self) -> str:
        return self.providers[self.primary_provider].model

    @property
    def rate_card(self) -> TokenRateCard:
        return self.providers[self.primary_provider].rate_card

    def route_for(self, workload: str) -> AgentRouteSettings:
        return self.routes.get(
            workload, AgentRouteSettings(self.primary_provider, self.fallback_providers),
        )


# Backward-compatible import name. The object is now deliberately multi-provider.
GeminiPrototypeSettings = StoryAgentSettings


def _provider_settings(
    values: Mapping[str, str], provider: str, currency: str, *, require_secret: bool,
) -> ProviderModelSettings | None:
    prefix = provider.upper()
    api_key = values.get(f"{prefix}_API_KEY", "").strip()
    model = values.get(f"{prefix}_MODEL", "").strip()
    if not api_key and not model:
        return None
    if not model:
        raise DomainError(f"{prefix}_MODEL is required when {prefix}_API_KEY is configured.")
    if require_secret and not api_key:
        raise DomainError(f"{prefix}_API_KEY is required for provider {provider}.")
    rate_version = values.get(f"AI_COMPANY_{prefix}_RATE_CARD_VERSION", "").strip()
    if not rate_version:
        raise DomainError(f"AI_COMPANY_{prefix}_RATE_CARD_VERSION is required.")
    return ProviderModelSettings(
        provider_key=provider,
        api_key=api_key,
        model=model,
        base_url=(values.get("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()
                  if provider == "openai" else None),
        rate_card=TokenRateCard(
            rate_version,
            currency,
            _positive_int(values, f"AI_COMPANY_{prefix}_INPUT_MINOR_PER_MILLION", allow_zero=True),
            _positive_int(values, f"AI_COMPANY_{prefix}_OUTPUT_MINOR_PER_MILLION", allow_zero=True),
        ),
        max_output_tokens=_positive_int(values, f"AI_COMPANY_{prefix}_MAX_OUTPUT_TOKENS"),
        timeout_seconds=_positive_int(values, f"AI_COMPANY_{prefix}_TIMEOUT_SECONDS"),
    )


def load_story_agent_settings(
    environment: Mapping[str, str] | None = None, *, require_secret: bool = True,
) -> StoryAgentSettings:
    values = os.environ if environment is None else environment
    enabled_text = values.get("AI_COMPANY_REAL_AI_ENABLED", "false").lower()
    if enabled_text not in {"true", "false"}:
        raise DomainError("AI_COMPANY_REAL_AI_ENABLED must be true or false.")
    enabled = enabled_text == "true"
    architect_primary = values.get("AI_COMPANY_STORY_ARCHITECT_PROVIDER", "gemini").strip().lower()
    architect_fallbacks = tuple(
        item.strip().lower()
        for item in values.get("AI_COMPANY_STORY_ARCHITECT_FALLBACKS", "").split(",")
        if item.strip()
    )

    def role_route(role: str, workload: str) -> tuple[str, AgentRouteSettings]:
        prefix = f"AI_COMPANY_{role.upper()}"
        primary = values.get(f"{prefix}_PROVIDER", "").strip().lower() or architect_primary
        fallback_text = values.get(f"{prefix}_FALLBACKS")
        fallbacks = architect_fallbacks if fallback_text is None or not fallback_text.strip() else tuple(
            item.strip().lower() for item in fallback_text.split(",") if item.strip()
        )
        ordered = (primary, *fallbacks)
        if len(set(ordered)) != len(ordered) or any(item not in SUPPORTED_PROVIDERS for item in ordered):
            raise DomainError(
                f"{role.replace('_', ' ').title()} providers must be unique and supported: openai, gemini."
            )
        return workload, AgentRouteSettings(primary, fallbacks)

    routes = dict(role_route(role, workload) for role, workload in ROLE_WORKLOADS.items())
    architect = routes["story_bible"]
    ordered = tuple(dict.fromkeys(
        provider for route in routes.values() for provider in route.ordered_providers
    ))
    required = {
        "AI_COMPANY_POLICY_VERSION": values.get("AI_COMPANY_POLICY_VERSION", ""),
        "AI_COMPANY_ASSIGNMENT_VERSION": values.get("AI_COMPANY_ASSIGNMENT_VERSION", ""),
        "AI_COMPANY_BUDGET_VERSION": values.get("AI_COMPANY_BUDGET_VERSION", ""),
    }
    if enabled and any(not value.strip() for value in required.values()):
        missing = ", ".join(key for key, value in required.items() if not value.strip())
        raise DomainError(f"Real AI is enabled but configuration is missing: {missing}.")
    currency = values.get("AI_COMPANY_BUDGET_CURRENCY", "USD")
    daily = _positive_int(values, "AI_COMPANY_DAILY_BUDGET_MINOR") if enabled else 1
    providers: dict[str, ProviderModelSettings] = {}
    if enabled:
        for provider in ordered:
            configured = _provider_settings(values, provider, currency, require_secret=require_secret)
            if configured is None:
                raise DomainError(f"Provider {provider} is assigned but has no key/model configuration.")
            providers[provider] = configured
    return StoryAgentSettings(
        enabled=enabled,
        policy_version=required["AI_COMPANY_POLICY_VERSION"],
        assignment_version=required["AI_COMPANY_ASSIGNMENT_VERSION"],
        budget_version=required["AI_COMPANY_BUDGET_VERSION"],
        daily_budget_minor=daily,
        primary_provider=architect.primary_provider,
        fallback_providers=architect.fallback_providers,
        providers=providers,
        routes=routes,
    )


def load_gemini_prototype_settings(
    environment: Mapping[str, str] | None = None, *, require_secret: bool = True,
) -> StoryAgentSettings:
    """Backward-compatible loader name for the multi-provider story agent."""
    return load_story_agent_settings(environment, require_secret=require_secret)
