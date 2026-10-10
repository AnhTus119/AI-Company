"""Construct configured providers without persisting their credentials."""

from __future__ import annotations

from dataclasses import dataclass

from ai_company.application.provider_config import StoryAgentSettings
from ai_company.providers.base import StructuredTextProvider, TokenRateCard
from ai_company.providers.openai import OpenAIResponsesStructuredProvider


@dataclass(frozen=True)
class ProviderBinding:
    provider: StructuredTextProvider
    rate_card: TokenRateCard
    max_output_tokens: int
    service_tier: str = "default"


def build_provider_bindings(settings: StoryAgentSettings) -> dict[str, ProviderBinding]:
    bindings: dict[str, ProviderBinding] = {}
    for provider_key, item in settings.providers.items():
        if provider_key == "openai":
            provider = OpenAIResponsesStructuredProvider(
                item.api_key, item.model,
                base_url=item.base_url or "https://api.openai.com/v1",
                timeout_seconds=item.timeout_seconds,
            )
        else:
            raise ValueError(f"Unsupported provider: {provider_key}")
        bindings[provider_key] = ProviderBinding(
            provider, item.rate_card, item.max_output_tokens, item.service_tier,
        )
    return bindings
