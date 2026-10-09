"""Fail-closed environment configuration for the bounded Gemini prototype."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

from ai_company.domain.workflow import DomainError
from ai_company.providers.base import TokenRateCard


def _positive_int(values: Mapping[str, str], key: str, *, allow_zero: bool = False) -> int:
    try:
        value = int(values.get(key, ""))
    except ValueError as exc:
        raise DomainError(f"{key} must be an integer.") from exc
    if value < 0 or (value == 0 and not allow_zero):
        raise DomainError(f"{key} must be {'non-negative' if allow_zero else 'positive'}.")
    return value


@dataclass(frozen=True)
class GeminiPrototypeSettings:
    enabled: bool
    api_key: str
    model: str
    policy_version: str
    assignment_version: str
    budget_version: str
    daily_budget_minor: int
    rate_card: TokenRateCard
    max_output_tokens: int
    timeout_seconds: int


def load_gemini_prototype_settings(
    environment: Mapping[str, str] | None = None, *, require_secret: bool = True,
) -> GeminiPrototypeSettings:
    values = os.environ if environment is None else environment
    enabled_text = values.get("AI_COMPANY_REAL_AI_ENABLED", "false").lower()
    if enabled_text not in {"true", "false"}:
        raise DomainError("AI_COMPANY_REAL_AI_ENABLED must be true or false.")
    enabled = enabled_text == "true"
    required = {
        "GEMINI_MODEL": values.get("GEMINI_MODEL", ""),
        "AI_COMPANY_POLICY_VERSION": values.get("AI_COMPANY_POLICY_VERSION", ""),
        "AI_COMPANY_ASSIGNMENT_VERSION": values.get("AI_COMPANY_ASSIGNMENT_VERSION", ""),
        "AI_COMPANY_BUDGET_VERSION": values.get("AI_COMPANY_BUDGET_VERSION", ""),
        "AI_COMPANY_GEMINI_RATE_CARD_VERSION": values.get("AI_COMPANY_GEMINI_RATE_CARD_VERSION", ""),
    }
    if enabled and any(not value.strip() for value in required.values()):
        missing = ", ".join(key for key, value in required.items() if not value.strip())
        raise DomainError(f"Real AI is enabled but configuration is missing: {missing}.")
    api_key = values.get("GEMINI_API_KEY", "")
    if enabled and require_secret and not api_key.strip():
        raise DomainError("Real AI is enabled but GEMINI_API_KEY is missing.")
    currency = values.get("AI_COMPANY_BUDGET_CURRENCY", "USD")
    daily = _positive_int(values, "AI_COMPANY_DAILY_BUDGET_MINOR") if enabled else 1
    input_rate = _positive_int(
        values, "AI_COMPANY_GEMINI_INPUT_MINOR_PER_MILLION", allow_zero=True,
    ) if enabled else 0
    output_rate = _positive_int(
        values, "AI_COMPANY_GEMINI_OUTPUT_MINOR_PER_MILLION", allow_zero=True,
    ) if enabled else 0
    max_output = _positive_int(values, "AI_COMPANY_GEMINI_MAX_OUTPUT_TOKENS") if enabled else 1
    timeout = _positive_int(values, "AI_COMPANY_GEMINI_TIMEOUT_SECONDS") if enabled else 60
    return GeminiPrototypeSettings(
        enabled=enabled,
        api_key=api_key,
        model=required["GEMINI_MODEL"],
        policy_version=required["AI_COMPANY_POLICY_VERSION"],
        assignment_version=required["AI_COMPANY_ASSIGNMENT_VERSION"],
        budget_version=required["AI_COMPANY_BUDGET_VERSION"],
        daily_budget_minor=daily,
        rate_card=TokenRateCard(
            required["AI_COMPANY_GEMINI_RATE_CARD_VERSION"] or "disabled",
            currency, input_rate, output_rate,
        ),
        max_output_tokens=max_output,
        timeout_seconds=timeout,
    )
