"""Run at most one offline mock blueprint task from the Lite queue."""

from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Event

from ai_company.adapters.database import TaskRepository, initialize_lite_schema, make_session_factory
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
    worker = make_mock_lite_worker(sessions, "mock-cli", output_root=output_root)
    if args.loop:
        print("mock worker polling; press Ctrl+C to stop", flush=True)
        try:
            worker.run_forever(
                Event(), provider_slots=1, budget_slots=1,
                poll_seconds=args.poll_seconds,
            )
        except KeyboardInterrupt:
            print("mock worker stopped", flush=True)
    else:
        print(worker.run_once(provider_slots=1, budget_slots=1), flush=True)


if __name__ == "__main__":
    main()
