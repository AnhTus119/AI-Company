"""Run at most one offline mock blueprint task from the Lite queue."""

from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Event, Thread

from ai_company.adapters.database import (
    BudgetRepository, GovernanceRepository, NovelWorkspaceRepository, StoryRepository, TaskRepository,
    initialize_lite_schema, make_session_factory,
)
from ai_company.application.agent_runner import BudgetedStructuredAgentRunner
from ai_company.application.provider_config import load_story_agent_settings
from ai_company.application.provider_factory import build_provider_bindings
from ai_company.application.real_blueprint import RealBlueprintHandler
from ai_company.application.real_chapter import CHAPTER_TASK_TYPE, RealChapterPipelineHandler
from ai_company.application.runtime import RuntimeProfile, load_runtime_settings
from ai_company.worker.lite import make_mock_lite_worker


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline Lite mock worker")
    parser.add_argument("--loop", action="store_true", help="Keep polling until Ctrl+C")
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    args = parser.parse_args()
    if args.poll_seconds <= 0:
        parser.error("--poll-seconds must be positive")
    settings = load_runtime_settings()
    if settings.profile != RuntimeProfile.LITE or settings.data_dir is None:
        raise SystemExit("The offline mock runner supports the Lite profile only.")
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    sessions = make_session_factory(settings.database_url)
    initialize_lite_schema(sessions)
    tasks = TaskRepository(sessions)
    tasks.hold_interrupted_tasks(datetime.now(timezone.utc))
    output_root = Path(os.environ.get("ARTIFACT_ROOT") or settings.data_dir / "artifacts")
    provider_settings = load_story_agent_settings()
    concurrency = settings.max_local_workers or 1
    governance = GovernanceRepository(sessions) if provider_settings.enabled else None
    budgets = BudgetRepository(sessions) if provider_settings.enabled else None
    bindings = build_provider_bindings(provider_settings) if provider_settings.enabled else {}

    def build_worker(index: int):
        worker_id = f"lite-cli-{index}"
        worker = make_mock_lite_worker(
            sessions, worker_id, output_root=output_root, max_active_tasks=concurrency,
        )
        if provider_settings.enabled:
            assert governance is not None and budgets is not None
            worker.handlers["real_blueprint"] = RealBlueprintHandler(
                StoryRepository(sessions), tasks, governance,
                budgets, bindings,
                provider_settings, worker_id,
            )
            worker.handlers[CHAPTER_TASK_TYPE] = RealChapterPipelineHandler(
                tasks,
                NovelWorkspaceRepository(sessions),
                BudgetedStructuredAgentRunner(governance, budgets, bindings, provider_settings),
                worker_id,
            )
        return worker

    workers = [build_worker(index + 1) for index in range(concurrency)]
    if args.loop:
        route = " -> ".join(provider_settings.ordered_providers)
        mode = f"mock + approved agents ({route})" if provider_settings.enabled else "mock only"
        print(f"Lite workers={concurrency} polling ({mode}); press Ctrl+C to stop", flush=True)
        stop = Event()
        threads = [
            Thread(
                target=worker.run_forever,
                kwargs={
                    "stop": stop,
                    "provider_slots": concurrency,
                    "budget_slots": concurrency,
                    "poll_seconds": args.poll_seconds,
                },
                name=worker.worker_id,
            )
            for worker in workers
        ]
        try:
            for thread in threads:
                thread.start()
            while any(thread.is_alive() for thread in threads):
                for thread in threads:
                    thread.join(timeout=0.5)
        except KeyboardInterrupt:
            print("mock worker stopped", flush=True)
        finally:
            stop.set()
            for thread in threads:
                thread.join(timeout=max(2.0, args.poll_seconds + 1))
    else:
        print(workers[0].run_once(provider_slots=1, budget_slots=1), flush=True)


if __name__ == "__main__":
    main()
