"""Single-worker database poller for low-memory local operation."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from threading import Event
from typing import Callable, Mapping
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from ai_company.adapters.database import StoryRepository, TaskRepository
from ai_company.application.capacity import ResourceSnapshot, read_resources, safe_worker_count
from ai_company.application.mock_blueprint import DeterministicMockBlueprintProvider, MockBlueprintHandler
from ai_company.application.mock_chapters import MockChaptersHandler
from ai_company.application.mock_package import MockPackageHandler
from ai_company.application.runtime import RuntimeProfile


TaskHandler = Callable[[UUID], dict | None]


class LiteWorker:
    def __init__(
        self,
        tasks: TaskRepository,
        handlers: Mapping[str, TaskHandler],
        worker_id: str,
        resource_reader: Callable[[], ResourceSnapshot],
        minimum_available_mb_by_type: Mapping[str, int] | None = None,
        max_active_tasks: int = 1,
        lease_seconds: int = 900,
    ) -> None:
        self.tasks = tasks
        self.handlers = handlers
        self.worker_id = worker_id
        self.resource_reader = resource_reader
        self.minimum_available_mb_by_type = minimum_available_mb_by_type or {}
        if max_active_tasks <= 0 or lease_seconds <= 0:
            raise ValueError("Worker capacity and lease must be positive.")
        self.max_active_tasks = max_active_tasks
        self.lease_seconds = lease_seconds

    def run_once(self, *, provider_slots: int, budget_slots: int) -> str:
        now = datetime.now(timezone.utc)
        task_id = self.tasks.next_eligible_task_id(now, tuple(self.handlers))
        if task_id is None:
            return "idle"
        task_type = self._task_type(task_id)
        resources = self.resource_reader()
        capacity = safe_worker_count(
            RuntimeProfile.LITE, resources, requested=1,
            provider_slots=provider_slots, budget_slots=budget_slots,
            minimum_available_mb=self.minimum_available_mb_by_type.get(task_type, 512),
        )
        if capacity == 0:
            return "deferred_capacity"
        if not self.tasks.claim_task(
            task_id, self.worker_id, now,
            lease_seconds=self.lease_seconds,
            max_active_tasks=self.max_active_tasks,
        ):
            return "not_claimed"
        try:
            checkpoint = self.handlers[task_type](task_id)
        except Exception:
            # Handler exception text may contain provider data; persist a fixed reason code only.
            self.tasks.fail_task(task_id, self.worker_id, datetime.now(timezone.utc), "handler_error")
            return "failed"
        self.tasks.complete_task(task_id, self.worker_id, datetime.now(timezone.utc), checkpoint=checkpoint)
        return "completed"

    def _task_type(self, task_id: UUID) -> str:
        return self.tasks.get_task_type(task_id)

    def run_forever(
        self,
        stop: Event,
        *,
        provider_slots: int,
        budget_slots: int,
        poll_seconds: float = 2.0,
    ) -> None:
        if poll_seconds <= 0:
            raise ValueError("poll_seconds must be positive")
        while not stop.is_set():
            self.tasks.hold_interrupted_tasks(datetime.now(timezone.utc))
            self.run_once(provider_slots=provider_slots, budget_slots=budget_slots)
            stop.wait(poll_seconds)


def make_mock_lite_worker(
    sessions: sessionmaker[Session],
    worker_id: str,
    resource_reader: Callable[[], ResourceSnapshot] = read_resources,
    output_root: Path | None = None,
    *,
    max_active_tasks: int = 1,
) -> LiteWorker:
    """Wire the offline smoke-test handler; no real provider is loaded."""
    stories = StoryRepository(sessions)
    tasks = TaskRepository(sessions)
    handler = MockBlueprintHandler(stories, tasks, DeterministicMockBlueprintProvider())
    handlers: dict[str, TaskHandler] = {
        "mock_blueprint": handler,
        "mock_chapters": MockChaptersHandler(tasks),
    }
    if output_root is not None:
        handlers["mock_package"] = MockPackageHandler(tasks, output_root)
    return LiteWorker(
        tasks,
        handlers,
        worker_id,
        resource_reader,
        {"mock_package": 768},
        max_active_tasks,
    )
