"""One-time explicit approval bootstrap for configured story agents."""

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
from ai_company.application.provider_config import load_story_agent_settings
from ai_company.application.runtime import RuntimeProfile, load_runtime_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Approve local story-agent provider configuration")
    parser.add_argument("--approve", action="store_true", help="Create and activate immutable local snapshots")
    parser.add_argument("--approved-by", default="local-owner")
    args = parser.parse_args()
    if not args.approve:
        parser.error("Review .env, then rerun with --approve to record explicit approval.")
    root = Path(__file__).resolve().parents[3]
    load_local_env(root / ".env")
    settings = load_story_agent_settings()
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
            provider: {
                "approved": True,
                "prototype_only": True,
                "allowed_categories": ["synthetic_prompt", "story_text"],
            }
            for provider in settings.providers
        }
    })
    governance.approve_policy_version(settings.policy_version, args.approved_by, now)
    def assignment(provider: str) -> dict:
        return {
                "provider": provider,
                "model": settings.providers[provider].model,
                "capabilities": ["text", "structured_output"],
                "approved": True,
        }

    governance.create_assignment_version(settings.assignment_version, {
        workload: {
            "primary": assignment(route.primary_provider),
            "fallbacks": [assignment(provider) for provider in route.fallback_providers],
        }
        for workload, route in settings.routes.items()
    })
    governance.activate_assignment_version(settings.assignment_version, args.approved_by, now)
    budgets.create_policy(
        settings.budget_version, next(iter(settings.providers.values())).rate_card.currency,
        settings.daily_budget_minor, "Asia/Ho_Chi_Minh",
    )
    budgets.activate_policy(settings.budget_version, args.approved_by, now)
    print("Approved local story-agent snapshots and daily budget.")
    for workload, route in settings.routes.items():
        print(f"Route {workload}: " + " -> ".join(
            f"{provider}/{settings.providers[provider].model}" for provider in route.ordered_providers
        ))
    currency = next(iter(settings.providers.values())).rate_card.currency
    print(f"Daily cap: {settings.daily_budget_minor} {currency} minor units")
    print("API keys were read from .env and were not stored in the database.")


if __name__ == "__main__":
    main()
