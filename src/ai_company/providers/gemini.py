"""Minimal Gemini REST adapter with no SDK dependency and no secret persistence."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ai_company.providers.base import (
    ProviderFailure,
    ProviderUsage,
    StructuredRequest,
    StructuredResult,
)


HttpPost = Callable[[str, dict[str, str], bytes, float], tuple[int, dict]]


def _post_json(url: str, headers: dict[str, str], body: bytes, timeout: float) -> tuple[int, dict]:
    request = Request(url, data=body, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status, json.load(response)
    except HTTPError as exc:
        if exc.code == 429:
            raise ProviderFailure("quota_exhausted", retryable=True) from exc
        if exc.code in {401, 403}:
            raise ProviderFailure("authentication_failed", retryable=False) from exc
        if 500 <= exc.code <= 599:
            raise ProviderFailure("provider_unavailable", retryable=True) from exc
        raise ProviderFailure("provider_request_rejected", retryable=False) from exc
    except (URLError, TimeoutError) as exc:
        raise ProviderFailure("provider_unavailable", retryable=True) from exc
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ProviderFailure("invalid_provider_response", retryable=False) from exc


class GeminiStructuredProvider:
    provider_key = "gemini"

    def __init__(
        self, api_key: str, model_key: str, *, timeout_seconds: float = 60,
        http_post: HttpPost = _post_json,
    ) -> None:
        if not api_key.strip():
            raise ValueError("GEMINI_API_KEY is required.")
        if not re.fullmatch(r"[A-Za-z0-9._-]{3,100}", model_key):
            raise ValueError("Gemini model ID is invalid.")
        if not 1 <= timeout_seconds <= 300:
            raise ValueError("Gemini timeout must be between 1 and 300 seconds.")
        self._api_key = api_key
        self.model_key = model_key
        self.timeout_seconds = timeout_seconds
        self._http_post = http_post

    def generate_structured(self, request: StructuredRequest) -> StructuredResult:
        if not request.prompt.strip() or request.max_output_tokens <= 0:
            raise ValueError("Structured generation needs a prompt and positive output limit.")
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model_key}:generateContent"
        )
        payload = {
            "contents": [{"role": "user", "parts": [{"text": request.prompt}]}],
            "generationConfig": {
                "temperature": request.temperature,
                "maxOutputTokens": request.max_output_tokens,
                "responseFormat": {
                    "text": {
                        "mimeType": "application/json",
                        "schema": request.json_schema,
                    }
                },
            },
        }
        status, response = self._http_post(
            url,
            {"Content-Type": "application/json", "x-goog-api-key": self._api_key},
            json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            self.timeout_seconds,
        )
        if status != 200:
            raise ProviderFailure("provider_request_failed", retryable=status >= 500)
        try:
            text = response["candidates"][0]["content"]["parts"][0]["text"]
            value = json.loads(text)
            metadata = response.get("usageMetadata", {})
            candidate_tokens = int(metadata.get("candidatesTokenCount", 0))
            thinking_tokens = int(metadata.get("thoughtsTokenCount", 0))
            usage = ProviderUsage(
                input_tokens=int(metadata.get("promptTokenCount", 0)),
                output_tokens=candidate_tokens + thinking_tokens,
                total_tokens=int(metadata.get("totalTokenCount", 0)),
            )
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ProviderFailure("invalid_provider_response", retryable=False) from exc
        if not isinstance(value, dict):
            raise ProviderFailure("invalid_provider_response", retryable=False)
        return StructuredResult(value=value, usage=usage)
