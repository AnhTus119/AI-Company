import json

import pytest

from ai_company.providers.base import ProviderFailure, StructuredRequest
from ai_company.providers.openai import OpenAIResponsesStructuredProvider


def test_openai_responses_adapter_uses_strict_schema_and_bearer_header() -> None:
    captured = {}

    def post(url, headers, body, timeout):
        captured.update(url=url, headers=headers, body=json.loads(body), timeout=timeout)
        return 200, {
            "status": "completed",
            "output_text": '{"answer":"ok"}',
            "usage": {"input_tokens": 11, "output_tokens": 5, "total_tokens": 16},
        }

    provider = OpenAIResponsesStructuredProvider(
        "private-openai-key", "gpt-test", http_post=post,
    )
    result = provider.generate_structured(StructuredRequest(
        "Return JSON", {"type": "object", "properties": {"answer": {"type": "string"}}}, 100,
    ))
    assert result.value == {"answer": "ok"}
    assert result.usage.total_tokens == 16
    assert captured["url"] == "https://api.openai.com/v1/responses"
    assert captured["headers"]["Authorization"] == "Bearer private-openai-key"
    assert captured["body"]["text"]["format"]["strict"] is True
    assert captured["body"]["reasoning"] == {"effort": "low"}
    assert captured["body"]["service_tier"] == "default"
    assert "private-openai-key" not in json.dumps(captured["body"])


def test_openai_adapter_rejects_refusal_without_exposing_response() -> None:
    provider = OpenAIResponsesStructuredProvider(
        "private-openai-key", "gpt-test",
        http_post=lambda *_: (200, {
            "status": "completed",
            "output": [{"type": "message", "content": [{"type": "refusal", "refusal": "private"}]}],
        }),
    )
    with pytest.raises(ProviderFailure) as failure:
        provider.generate_structured(StructuredRequest("Return JSON", {"type": "object"}, 100))
    assert failure.value.code == "model_refusal"
    assert "private" not in str(failure.value)


def test_openai_access_check_uses_model_endpoint_without_story_payload() -> None:
    captured = {}

    def get(url, headers, timeout):
        captured.update(url=url, headers=headers, timeout=timeout)
        return 200, {"id": "gpt-5.6-terra"}

    provider = OpenAIResponsesStructuredProvider(
        "private-openai-key", "gpt-5.6-terra", http_get=get,
    )
    provider.check_access()
    assert captured["url"].endswith("/models/gpt-5.6-terra")
    assert set(captured) == {"url", "headers", "timeout"}
