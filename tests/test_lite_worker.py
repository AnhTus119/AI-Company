from datetime import datetime, timezone
from threading import Event

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from ai_company.adapters.database import Base, StoryRepository, TaskRepository, TaskRow
from ai_company.application.capacity import ResourceSnapshot
from ai_company.domain.workflow import SourceType
from ai_company.worker.lite import LiteWorker


def make_worker(tmp_path, handler, available_mb=900):
    engine = create_engine(f"sqlite:///{tmp_path / 'worker.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    stories = StoryRepository(sessions)
    campaign_id = stories.create_campaign("Worker", SourceType.USER_IDEA, 1)
    story_id = stories.create_story(campaign_id, SourceType.USER_IDEA, "A fictional premise")
    tasks = TaskRepository(sessions)
    task_id = tasks.create_task(story_id, "probe", "probe:1", datetime.now(timezone.utc))
    worker = LiteWorker(
        tasks, {"probe": handler}, "worker-one",
        lambda: ResourceSnapshot(4096, available_mb, 4),
    )
    return worker, sessions, task_id


def test_lite_worker_completes_supported_task(tmp_path) -> None:
    worker, sessions, task_id = make_worker(tmp_path, lambda _task_id: {"done": True})
    assert worker.run_once(provider_slots=1, budget_slots=1) == "completed"
    with sessions() as session:
        task = session.scalar(select(TaskRow).where(TaskRow.id == task_id))
        assert task.status == "completed" and task.checkpoint == {"done": True}


def test_lite_worker_waits_for_memory_and_budget(tmp_path) -> None:
    worker, sessions, task_id = make_worker(tmp_path, lambda _task_id: {}, available_mb=100)
    assert worker.run_once(provider_slots=1, budget_slots=1) == "deferred_capacity"
    with sessions() as session:
        assert session.get(TaskRow, task_id).status == "queued"


def test_lite_worker_records_redacted_failure(tmp_path) -> None:
    def broken(_task_id):
        raise RuntimeError("secret-like provider response")

    worker, sessions, task_id = make_worker(tmp_path, broken)
    assert worker.run_once(provider_slots=1, budget_slots=1) == "failed"
    with sessions() as session:
        assert session.get(TaskRow, task_id).status == "technical_failure"


def test_lite_worker_loop_stops_after_signal(tmp_path) -> None:
    stop = Event()
    worker, sessions, task_id = make_worker(tmp_path, lambda _task_id: {"done": True})

    def read_once() -> ResourceSnapshot:
        stop.set()
        return ResourceSnapshot(4096, 900, 4)

    worker.resource_reader = read_once
    worker.run_forever(stop, provider_slots=1, budget_slots=1, poll_seconds=0.01)
    with sessions() as session:
        assert session.get(TaskRow, task_id).status == "completed"
