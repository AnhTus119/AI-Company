"""Opt-in local process test; requires memory headroom for API and worker."""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import URLError
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen

import pytest

from ai_company.application.capacity import read_resources
from ai_company.application.mock_media import inspect_mock_hook
from ai_company.application.owner_auth import create_owner_auth
from ai_company.domain.workflow import REQUIRED_ARTIFACTS


ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def _temporary_test_dir():
    directory = Path(tempfile.mkdtemp(prefix="ai-company-http-"))
    try:
        yield directory
    finally:
        # Windows can retain SQLite/WAL handles briefly after the API process exits.
        for attempt in range(20):
            try:
                shutil.rmtree(directory)
                break
            except PermissionError:
                if attempt == 19:
                    raise
                time.sleep(0.25)


def _request(base: str, path: str, payload: dict | None = None, opener=None) -> dict:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        base + path,
        data=body,
        headers={"Content-Type": "application/json"} if body is not None else {},
        method="POST" if body is not None else "GET",
    )
    with (opener.open(request, timeout=3) if opener is not None else urlopen(request, timeout=3)) as response:
        return json.load(response)


@pytest.mark.skipif(
    os.environ.get("AI_COMPANY_RUN_HTTP_INTEGRATION") != "1",
    reason="Set AI_COMPANY_RUN_HTTP_INTEGRATION=1 for the separate-process test.",
)
def test_http_api_and_worker_in_separate_processes() -> None:
    if read_resources().available_ram_mb < 768:
        pytest.skip("At least 768 MB of available RAM is required inside the test process.")

    with _temporary_test_dir() as temporary:
        create_owner_auth(temporary, {"Tou": "a-strong-test-password", "Chibun": "another-strong-test-password"})
        environment = os.environ.copy()
        environment["AI_COMPANY_PROFILE"] = "lite"
        environment["AI_COMPANY_DATA_DIR"] = str(temporary)
        environment["PYTHONPATH"] = str(ROOT / "src")
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        base = f"http://127.0.0.1:{port}"
        client = build_opener(HTTPCookieProcessor(CookieJar()))

        def request(path: str, payload: dict | None = None) -> dict:
            return _request(base, path, payload, opener=client)

        server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "ai_company.api.main:create_app",
             "--factory", "--host", "127.0.0.1", "--port", str(port), "--no-access-log"],
            cwd=ROOT,
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            deadline = time.monotonic() + 20
            while True:
                if server.poll() is not None:
                    pytest.fail(f"Local API exited during startup with code {server.returncode}.")
                try:
                    assert request("/health") == {"status": "ok"}
                    break
                except (URLError, TimeoutError):
                    if time.monotonic() >= deadline:
                        pytest.fail("Local API did not become ready within 20 seconds.")
                    time.sleep(0.2)

            assert request("/auth/login", {
                "username": "Tou", "password": "a-strong-test-password",
            })["username"] == "Tou"
            campaign = request("/campaigns", {
                "name": "HTTP process trial", "source_type": "user_idea", "target_count": 1,
            })
            story = request(f"/campaigns/{campaign['id']}/stories", {
                "source_type": "user_idea", "idea": "A fictional family secret",
            })
            story_id = story["id"]
            blueprint = request(f"/stories/{story_id}/mock-blueprint", {})
            first = subprocess.run(
                [sys.executable, "-m", "ai_company.worker.mock_cli"],
                cwd=ROOT, env=environment, capture_output=True, text=True, timeout=20,
                check=True,
            )
            assert "completed" in first.stdout
            result = request(f"/stories/{story_id}/mock-blueprint/{blueprint['task_id']}")
            assert result["status"] == "completed"

            chapters = request(f"/stories/{story_id}/mock-chapters", {})
            second = subprocess.run(
                [sys.executable, "-m", "ai_company.worker.mock_cli"],
                cwd=ROOT, env=environment, capture_output=True, text=True, timeout=20,
                check=True,
            )
            assert "completed" in second.stdout
            result = request(f"/stories/{story_id}/mock-chapters/{chapters['task_id']}")
            assert result["checkpoint"]["chapter_count"] == 20
            package = request(f"/stories/{story_id}/mock-package", {})
            third = subprocess.run(
                [sys.executable, "-m", "ai_company.worker.mock_cli"],
                cwd=ROOT, env=environment, capture_output=True, text=True, timeout=30,
                check=True,
            )
            assert "completed" in third.stdout
            packaged = request(f"/stories/{story_id}/mock-package/{package['task_id']}")
            assert packaged["status"] == "completed"
            directory = Path(packaged["checkpoint"]["directory"])
            assert {item.name for item in directory.iterdir()} == REQUIRED_ARTIFACTS
            assert 13 <= inspect_mock_hook(directory / "hook.mp4").duration_seconds <= 17
            assert request(f"/stories/{story_id}")["stage"] == "draft"
        finally:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)
