import json

import pytest

from ai_company.providers.base import ProviderFailure, StructuredRequest, TokenRateCard
from ai_company.providers.gemini import GeminiStructuredProvider


def test_gemini_adapter_uses_header_and_current_structured_output_contract() -> None:
    captured = {}

    def post(url, headers, body, timeout):
        captured.update(url=url, headers=headers, body=json.loads(body), timeout=timeout)
        return 200, {
            "candidates": [{"content": {"parts": [{"text": '{"answer":"ok"}'}]}}],
            "usageMetadata": {
                "promptTokenCount": 10, "candidatesTokenCount": 4,
                "thoughtsTokenCount": 2, "totalTokenCount": 16,
            },
        }

    provider = GeminiStructuredProvider("private-test-key", "gemini-test-model", http_post=post)
    result = provider.generate_structured(StructuredRequest(
        "Return JSON", {"type": "object", "properties": {"answer": {"type": "string"}}}, 100,
    ))
    assert result.value == {"answer": "ok"}
    assert result.usage.total_tokens == 16 and result.usage.output_tokens == 6
    assert captured["headers"]["x-goog-api-key"] == "private-test-key"
    assert "private-test-key" not in captured["url"]
    assert "private-test-key" not in json.dumps(captured["body"])
    assert captured["body"]["generationConfig"]["responseFormat"]["text"]["mimeType"] == "application/json"


def test_gemini_adapter_rejects_malformed_response_without_exposing_body() -> None:
    provider = GeminiStructuredProvider(
        "private-test-key", "gemini-test-model",
        http_post=lambda *_: (200, {"unexpected": "private provider body"}),
    )
    with pytest.raises(ProviderFailure) as failure:
        provider.generate_structured(StructuredRequest("Return JSON", {"type": "object"}, 100))
    assert failure.value.code == "invalid_provider_response"
    assert "private provider body" not in str(failure.value)


def test_gemini_access_check_uses_model_endpoint_without_story_payload() -> None:
    captured = {}

    def get(url, headers, timeout):
        captured.update(url=url, headers=headers, timeout=timeout)
        return 200, {"name": "models/gemini-3.8-flash"}

    provider = GeminiStructuredProvider(
        "private-test-key", "gemini-3.8-flash", http_get=get,
    )
    provider.check_access()
    assert captured["url"].endswith("/models/gemini-3.8-flash")
    assert set(captured) == {"url", "headers", "timeout"}


def test_explicit_rate_card_rounds_up_and_supports_free_tier() -> None:
    paid = TokenRateCard("rate-v1", "USD", 75, 375)
    assert paid.upper_bound(10_000, 2_000) == 2
    free = TokenRateCard("free-v1", "USD", 0, 0)
    assert free.upper_bound(100_000, 100_000) == 0
