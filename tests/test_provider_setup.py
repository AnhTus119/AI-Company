from pathlib import Path
from uuid import UUID

import pytest
from fastapi import HTTPException

from ai_company.adapters.database import StoryRepository, initialize_lite_schema, make_session_factory
from ai_company.api.main import CampaignCreate, StoryCreate, create_app
from ai_company.application.local_env import load_local_env
from ai_company.application.provider_config import load_story_agent_settings
from ai_company.domain.workflow import DomainError, SourceType


def configured_environment(tmp_path: Path) -> dict[str, str]:
    return {
        "AI_COMPANY_DATA_DIR": str(tmp_path),
        "AI_COMPANY_REAL_AI_ENABLED": "true",
        "OPENAI_API_KEY": "local-test-key",
        "OPENAI_MODEL": "gpt-5.6-terra",
        "AI_COMPANY_POLICY_VERSION": "policy-v1",
        "AI_COMPANY_ASSIGNMENT_VERSION": "models-v1",
        "AI_COMPANY_BUDGET_VERSION": "budget-v1",
        "AI_COMPANY_DAILY_BUDGET_MINOR": "100",
        "AI_COMPANY_BUDGET_CURRENCY": "USD",
        "AI_COMPANY_OPENAI_RATE_CARD_VERSION": "gpt-5.6-terra-standard-test",
        "AI_COMPANY_OPENAI_INPUT_MINOR_PER_MILLION": "200",
        "AI_COMPANY_OPENAI_OUTPUT_MINOR_PER_MILLION": "1200",
        "AI_COMPANY_OPENAI_MAX_OUTPUT_TOKENS": "6000",
        "AI_COMPANY_OPENAI_TIMEOUT_SECONDS": "60",
    }


def test_real_provider_configuration_is_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(DomainError, match="configuration is missing"):
        load_story_agent_settings({"AI_COMPANY_REAL_AI_ENABLED": "true"})
    settings = load_story_agent_settings(configured_environment(tmp_path))
    assert settings.enabled and settings.model == "gpt-5.6-terra"
    assert settings.rate_card.upper_bound(10_000, 2_000) == 5
    assert settings.chapter_pipeline_mode == "fast"


def test_story_agent_rejects_fallback_and_non_terra_model(tmp_path: Path) -> None:
    environment = configured_environment(tmp_path) | {
        "AI_COMPANY_STORY_ARCHITECT_PROVIDER": "openai",
        "AI_COMPANY_STORY_ARCHITECT_FALLBACKS": "gemini",
        "OPENAI_API_KEY": "local-openai-test-key",
        "OPENAI_MODEL": "gpt-5.6-terra",
        "OPENAI_BASE_URL": "https://api.openai.com/v1",
        "AI_COMPANY_OPENAI_RATE_CARD_VERSION": "openai-rate-v1",
        "AI_COMPANY_OPENAI_INPUT_MINOR_PER_MILLION": "100",
        "AI_COMPANY_OPENAI_OUTPUT_MINOR_PER_MILLION": "500",
        "AI_COMPANY_OPENAI_MAX_OUTPUT_TOKENS": "6000",
        "AI_COMPANY_OPENAI_TIMEOUT_SECONDS": "60",
    }
    with pytest.raises(DomainError, match="must use openai"):
        load_story_agent_settings(environment)
    environment["AI_COMPANY_STORY_ARCHITECT_FALLBACKS"] = ""
    environment["OPENAI_MODEL"] = "gpt-other"
    with pytest.raises(DomainError, match="gpt-5.6-terra"):
        load_story_agent_settings(environment)


def test_story_roles_all_inherit_openai_terra(tmp_path: Path) -> None:
    environment = configured_environment(tmp_path) | {
        "AI_COMPANY_EDITOR_PROVIDER": "openai",
        "AI_COMPANY_CONTINUITY_QC_PROVIDER": "openai",
        "OPENAI_API_KEY": "local-openai-test-key",
        "OPENAI_MODEL": "gpt-5.6-terra",
        "AI_COMPANY_OPENAI_RATE_CARD_VERSION": "openai-rate-v1",
        "AI_COMPANY_OPENAI_INPUT_MINOR_PER_MILLION": "100",
        "AI_COMPANY_OPENAI_OUTPUT_MINOR_PER_MILLION": "500",
        "AI_COMPANY_OPENAI_MAX_OUTPUT_TOKENS": "6000",
        "AI_COMPANY_OPENAI_TIMEOUT_SECONDS": "60",
    }
    settings = load_story_agent_settings(environment)
    assert settings.route_for("chapter_writer").ordered_providers == ("openai",)
    assert settings.route_for("chapter_editor").ordered_providers == ("openai",)
    assert settings.route_for("continuity_qc").ordered_providers == ("openai",)
    assert set(settings.providers) == {"openai"}


def test_local_env_loads_only_allowlisted_settings_without_overrides(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / ".env"
    path.write_text("GEMINI_MODEL=from-file\nAI_COMPANY_REAL_AI_ENABLED=true\n", encoding="utf-8")
    monkeypatch.setenv("GEMINI_MODEL", "from-process")
    monkeypatch.delenv("AI_COMPANY_REAL_AI_ENABLED", raising=False)
    load_local_env(path)
    assert __import__("os").environ["GEMINI_MODEL"] == "from-process"
    assert __import__("os").environ["AI_COMPANY_REAL_AI_ENABLED"] == "true"
    path.write_text("UNAPPROVED_SETTING=value\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported"):
        load_local_env(path)


def test_real_blueprint_api_is_disabled_until_operator_enables_configuration(tmp_path: Path, monkeypatch) -> None:
    sessions = make_session_factory(f"sqlite:///{tmp_path / 'state.sqlite3'}")
    initialize_lite_schema(sessions)
    app = create_app(StoryRepository(sessions))
    endpoint = lambda path, method: next(
        route.endpoint for route in app.routes if route.path == path and method in route.methods
    )
    campaign = endpoint("/campaigns", "POST")(
        CampaignCreate(name="Real provider", source_type=SourceType.USER_IDEA, target_count=1)
    )
    story = endpoint("/campaigns/{campaign_id}/stories", "POST")(
        UUID(campaign["id"]), StoryCreate(source_type=SourceType.USER_IDEA, idea="A fictional premise"),
    )
    with pytest.raises(HTTPException) as disabled:
        endpoint("/stories/{story_id}/real-blueprint", "POST")(UUID(story["id"]))
    assert disabled.value.status_code == 409
    for key, value in configured_environment(tmp_path).items():
        monkeypatch.setenv(key, value)
    queued = endpoint("/stories/{story_id}/real-blueprint", "POST")(UUID(story["id"]))
    assert queued["status"] == "queued" and queued["is_mock"] is False
