"""OpenAI Responses API adapter for strict structured output."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from ai_company.providers.base import ProviderFailure, ProviderUsage, StructuredRequest, StructuredResult

HttpPost = Callable[[str, dict[str, str], bytes, float], tuple[int, dict]]


def _post_json(url: str, headers: dict[str, str], body: bytes, timeout: float) -> tuple[int, dict]:
    request = Request(url, data=body, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status, json.load(response)
    except HTTPError as exc:
        if exc.code == 429:
            raise ProviderFailure("quota_or_rate_limit", retryable=True) from exc
        if exc.code in {401, 403}:
            raise ProviderFailure("authentication_failed", retryable=False) from exc
        if 500 <= exc.code <= 599:
            raise ProviderFailure("provider_unavailable", retryable=True) from exc
        raise ProviderFailure("provider_request_rejected", retryable=False) from exc
    except (URLError, TimeoutError) as exc:
        raise ProviderFailure("provider_unavailable", retryable=True) from exc
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ProviderFailure("invalid_provider_response", retryable=False) from exc


def _output_text(response: dict) -> str:
    direct = response.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct
    for item in response.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "refusal":
                raise ProviderFailure("model_refusal", retryable=False)
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                return content["text"]
    raise ProviderFailure("invalid_provider_response", retryable=False)


class OpenAIResponsesStructuredProvider:
    provider_key = "openai"

    def __init__(
        self, api_key: str, model_key: str, *,
        base_url: str = "https://api.openai.com/v1", timeout_seconds: float = 60,
        http_post: HttpPost = _post_json,
    ) -> None:
        if not api_key.strip():
            raise ValueError("OPENAI_API_KEY is required.")
        if not re.fullmatch(r"[A-Za-z0-9._:-]{2,160}", model_key):
            raise ValueError("OpenAI model ID is invalid.")
        parsed = urlparse(base_url)
        if parsed.scheme != "https" or not parsed.netloc or parsed.query or parsed.fragment:
            raise ValueError("OPENAI_BASE_URL must be HTTPS without query or fragment.")
        if not 1 <= timeout_seconds <= 300:
            raise ValueError("OpenAI timeout must be between 1 and 300 seconds.")
        self._api_key = api_key
        self.model_key = model_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._http_post = http_post

    def generate_structured(self, request: StructuredRequest) -> StructuredResult:
        if not request.prompt.strip() or request.max_output_tokens <= 0:
            raise ValueError("Structured generation needs a prompt and positive output limit.")
        payload = {
            "model": self.model_key,
            "input": [{"role": "user", "content": request.prompt}],
            "max_output_tokens": request.max_output_tokens,
            "text": {"format": {
                "type": "json_schema", "name": "story_blueprint", "strict": True,
                "schema": request.json_schema,
            }},
        }
        status, response = self._http_post(
            f"{self.base_url}/responses",
            {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
            json.dumps(payload, separators=(",", ":")).encode("utf-8"), self.timeout_seconds,
        )
        if status != 200:
            raise ProviderFailure("provider_request_failed", retryable=status >= 500)
        if response.get("status") in {"failed", "cancelled", "incomplete"}:
            raise ProviderFailure("incomplete_provider_response", retryable=False)
        try:
            value = json.loads(_output_text(response))
            metadata = response.get("usage") or {}
            usage = ProviderUsage(
                input_tokens=int(metadata.get("input_tokens", 0)),
                output_tokens=int(metadata.get("output_tokens", 0)),
                total_tokens=int(metadata.get("total_tokens", 0)),
            )
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ProviderFailure("invalid_provider_response", retryable=False) from exc
        if not isinstance(value, dict):
            raise ProviderFailure("invalid_provider_response", retryable=False)
        return StructuredResult(value=value, usage=usage)
