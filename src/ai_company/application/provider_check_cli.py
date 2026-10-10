"""Verify configured provider credentials and model visibility without sending story data."""

from __future__ import annotations

from pathlib import Path

from ai_company.application.local_env import load_local_env
from ai_company.application.provider_config import load_story_agent_settings
from ai_company.application.provider_factory import build_provider_bindings
from ai_company.domain.workflow import DomainError
from ai_company.providers.base import ProviderFailure


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    load_local_env(root / ".env")
    try:
        settings = load_story_agent_settings()
        if not settings.enabled:
            raise DomainError("Set AI_COMPANY_REAL_AI_ENABLED=true before checking providers.")
        bindings = build_provider_bindings(settings)
        for provider_key, binding in bindings.items():
            checker = getattr(binding.provider, "check_access", None)
            if checker is None:
                raise DomainError(f"Provider {provider_key} does not support an access check.")
            checker()
            print(f"OK {provider_key}/{binding.provider.model_key}: key accepted and model visible.")
    except (DomainError, ProviderFailure, ValueError) as exc:
        code = exc.code if isinstance(exc, ProviderFailure) else str(exc)
        raise SystemExit(f"Provider check failed safely: {code}") from None
    print("No story prompt was sent and no API key was stored.")


if __name__ == "__main__":
    main()
