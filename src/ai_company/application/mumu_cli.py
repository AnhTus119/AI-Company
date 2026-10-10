"""Export or push a completed real blueprint to a local MuMuAINovel instance."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from uuid import UUID

from ai_company.adapters.database import TaskRepository, make_session_factory
from ai_company.application.local_env import load_local_env
from ai_company.application.mumu_export import blueprint_to_mumu_project
from ai_company.application.real_blueprint import real_blueprint_key
from ai_company.application.runtime import load_runtime_settings
from ai_company.integrations.mumuainovel import MuMuAINovelClient, load_mumu_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="MuMuAINovel bridge for a completed real blueprint")
    parser.add_argument("command", choices=("export", "push", "status"))
    parser.add_argument("--story-id")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    load_local_env(root / ".env")
    client = MuMuAINovelClient(load_mumu_settings(os.environ))
    if args.command == "status":
        print("available" if client.health() else "unavailable")
        return
    if not args.story_id:
        parser.error("--story-id is required for export and push")
    story_id = UUID(args.story_id)
    runtime = load_runtime_settings()
    tasks = TaskRepository(make_session_factory(runtime.database_url))
    result = tasks.get_task_result_by_key(
        story_id, real_blueprint_key(story_id), expected_type="real_blueprint",
    )
    if result["status"] != "completed" or not result.get("checkpoint"):
        parser.error("The real blueprint is not completed.")
    document = blueprint_to_mumu_project(result["checkpoint"])
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Exported: {args.output.resolve()}")
    if args.command == "push":
        pushed = client.push_project(document)
        print(f"Imported MuMuAINovel project: {pushed.get('project_id')}")


if __name__ == "__main__":
    main()
