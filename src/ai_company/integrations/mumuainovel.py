"""Authenticated localhost bridge to MuMuAINovel's documented import API."""

from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from http.cookiejar import CookieJar
from typing import Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPCookieProcessor, Request, build_opener

from ai_company.domain.workflow import DomainError


@dataclass(frozen=True)
class MuMuSettings:
    base_url: str
    username: str
    password: str
    timeout_seconds: int = 30


def load_mumu_settings(values: Mapping[str, str]) -> MuMuSettings:
    return MuMuSettings(
        values.get("MUMUAINOVEL_BASE_URL", "http://127.0.0.1:8800").strip(),
        values.get("MUMUAINOVEL_USERNAME", "").strip(),
        values.get("MUMUAINOVEL_PASSWORD", ""),
    )


class MuMuAINovelClient:
    def __init__(self, settings: MuMuSettings) -> None:
        parsed = urlparse(settings.base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
            raise DomainError("MuMuAINovel integration is restricted to a local HTTP instance.")
        if parsed.query or parsed.fragment or not 1 <= settings.timeout_seconds <= 120:
            raise DomainError("MuMuAINovel URL or timeout is invalid.")
        self.settings = settings
        self.base_url = settings.base_url.rstrip("/")
        self._opener = build_opener(HTTPCookieProcessor(CookieJar()))

    def _request(self, path: str, *, body: bytes | None = None, content_type: str | None = None) -> dict:
        headers = {"Accept": "application/json"}
        if content_type:
            headers["Content-Type"] = content_type
        request = Request(
            self.base_url + path, data=body, headers=headers,
            method="POST" if body is not None else "GET",
        )
        try:
            with self._opener.open(request, timeout=self.settings.timeout_seconds) as response:
                return json.load(response)
        except HTTPError as exc:
            code = "authentication_failed" if exc.code in {401, 403} else "mumu_request_failed"
            raise DomainError(code) from exc
        except (URLError, TimeoutError) as exc:
            raise DomainError("mumu_unavailable") from exc
        except (json.JSONDecodeError, UnicodeError) as exc:
            raise DomainError("mumu_invalid_response") from exc

    def health(self) -> bool:
        try:
            response = self._request("/health")
        except DomainError:
            return False
        return response.get("status") in {"healthy", "ok"}

    def login(self) -> None:
        if not self.settings.username or not self.settings.password:
            raise DomainError("MuMuAINovel local username/password are required for import.")
        response = self._request(
            "/api/auth/local/login",
            body=json.dumps({
                "username": self.settings.username, "password": self.settings.password,
            }).encode("utf-8"),
            content_type="application/json",
        )
        if response.get("success") is not True:
            raise DomainError("authentication_failed")

    @staticmethod
    def _multipart(document: dict, filename: str) -> tuple[bytes, str]:
        boundary = "----AICompany" + secrets.token_hex(12)
        payload = json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            "Content-Type: application/json\r\n\r\n"
        ).encode("ascii") + payload + f"\r\n--{boundary}--\r\n".encode("ascii")
        return body, f"multipart/form-data; boundary={boundary}"

    def push_project(self, document: dict) -> dict:
        self.login()
        body, content_type = self._multipart(document, "ai-company-project.json")
        validation = self._request(
            "/api/projects/validate-import", body=body, content_type=content_type,
        )
        if validation.get("valid") is not True:
            raise DomainError("MuMuAINovel rejected the project import document.")
        body, content_type = self._multipart(document, "ai-company-project.json")
        result = self._request("/api/projects/import", body=body, content_type=content_type)
        if result.get("success") is not True:
            raise DomainError("MuMuAINovel project import failed.")
        return result
