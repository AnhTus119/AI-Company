"""One-time explicit approval bootstrap for the bounded Gemini prototype."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from ai_company.adapters.database import (
    BudgetRepository,
    GovernanceRepository,
    initialize_lite_schema,
    make_session_factory,
)
from ai_company.application.local_env import load_local_env
from ai_company.application.provider_config import load_gemini_prototype_settings
from ai_company.application.runtime import RuntimeProfile, load_runtime_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Approve local Gemini prototype configuration")
    parser.add_argument("--approve", action="store_true", help="Create and activate immutable local snapshots")
    parser.add_argument("--approved-by", default="local-owner")
    args = parser.parse_args()
    if not args.approve:
        parser.error("Review .env, then rerun with --approve to record explicit approval.")
    root = Path(__file__).resolve().parents[3]
    load_local_env(root / ".env")
    settings = load_gemini_prototype_settings()
    if not settings.enabled:
        parser.error("Set AI_COMPANY_REAL_AI_ENABLED=true in .env first.")
    runtime = load_runtime_settings()
    if runtime.profile != RuntimeProfile.LITE or runtime.data_dir is None:
        parser.error("This bootstrap currently supports the Lite profile only.")
    runtime.data_dir.mkdir(parents=True, exist_ok=True)
    sessions = make_session_factory(runtime.database_url)
    initialize_lite_schema(sessions)
    governance = GovernanceRepository(sessions)
    budgets = BudgetRepository(sessions)
    now = datetime.now(timezone.utc)
    governance.create_policy_version(settings.policy_version, {
        "provider_permissions": {
            "gemini": {
                "approved": True,
                "prototype_only": True,
                "allowed_categories": ["synthetic_prompt", "story_text"],
            }
        }
    })
    governance.approve_policy_version(settings.policy_version, args.approved_by, now)
    governance.create_assignment_version(settings.assignment_version, {
        "story_bible": {
            "primary": {
                "provider": "gemini",
                "model": settings.model,
                "capabilities": ["text", "structured_output"],
                "approved": True,
            }
        }
    })
    governance.activate_assignment_version(settings.assignment_version, args.approved_by, now)
    budgets.create_policy(
        settings.budget_version, settings.rate_card.currency,
        settings.daily_budget_minor, "Asia/Ho_Chi_Minh",
    )
    budgets.activate_policy(settings.budget_version, args.approved_by, now)
    print("Approved local Gemini prototype snapshots and daily budget.")
    print(f"Model: {settings.model}")
    print(f"Daily cap: {settings.daily_budget_minor} {settings.rate_card.currency} minor units")
    print("The API key was read from .env and was not stored in the database.")


if __name__ == "__main__":
    main()
