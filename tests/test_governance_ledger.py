from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, text

from ai_company.adapters.database import (
    CostLedgerRow,
    GovernanceRepository,
    ModelAssignmentVersionRow,
    PolicyVersionRow,
    ProviderCallRow,
    StoryRepository,
    TaskAttemptRow,
    TaskRepository,
    initialize_lite_schema,
    make_session_factory,
)
from ai_company.application.runtime import load_runtime_settings
from ai_company.domain.workflow import DomainError, SourceType


def repositories(tmp_path):
    settings = load_runtime_settings({"AI_COMPANY_DATA_DIR": str(tmp_path)})
    sessions = make_session_factory(settings.database_url)
    initialize_lite_schema(sessions)
    stories = StoryRepository(sessions)
    campaign_id = stories.create_campaign("Ledger", SourceType.USER_IDEA, 1)
    story_id = stories.create_story(campaign_id, SourceType.USER_IDEA, "A fictional premise")
    tasks = TaskRepository(sessions)
    now = datetime.now(timezone.utc)
    task_id = tasks.create_task(story_id, "story_bible", "ledger-task", now, attempt_limit=1)
    assert tasks.claim_task(task_id, "ledger-worker", now, lease_seconds=60)
    with sessions() as session:
        attempt_id = session.scalar(select(TaskAttemptRow.id).where(TaskAttemptRow.task_id == task_id))
    assert attempt_id is not None
    return sessions, GovernanceRepository(sessions), attempt_id, now


def test_versions_must_be_explicitly_approved_before_provider_call(tmp_path) -> None:
    sessions, governance, attempt_id, now = repositories(tmp_path)
    governance.create_policy_version("policy-v1", {"cloud_categories": ["story_text"]})
    governance.create_assignment_version("models-v1", {"story_bible": {"provider": "prototype"}})
    arguments = dict(
        task_attempt_id=attempt_id,
        policy_version="policy-v1",
        assignment_version="models-v1",
        provider_key="prototype",
        model_key="test-model",
        workload="story_bible",
        requested_at=now,
        estimated_minor=12,
        currency="USD",
        rate_card_version="trial-2026-10",
    )
    with pytest.raises(DomainError, match="approved policy"):
        governance.start_provider_call(**arguments)
    governance.approve_policy_version("policy-v1", "owner", now)
    with pytest.raises(DomainError, match="active model-assignment"):
        governance.start_provider_call(**arguments)
    governance.activate_assignment_version("models-v1", "owner", now)
    call_id = governance.start_provider_call(**arguments)
    governance.finish_provider_call(
        call_id,
        completed_at=now + timedelta(milliseconds=1250),
        usage={"input_units": 100, "output_units": 50},
        actual_minor=10,
    )
    with sessions() as session:
        call = session.get(ProviderCallRow, call_id)
        cost = session.scalar(select(CostLedgerRow).where(CostLedgerRow.provider_call_id == call_id))
        assert call.status == "completed" and call.latency_ms == 1250
        assert call.usage == {"input_units": 100, "output_units": 50}
        assert cost.estimated_minor == 12 and cost.actual_minor == 10 and cost.currency == "USD"


def test_approved_versions_and_call_completion_are_one_way(tmp_path) -> None:
    _, governance, attempt_id, now = repositories(tmp_path)
    governance.create_policy_version("policy-v1", {"allowed": ["story_text"]})
    governance.create_assignment_version("models-v1", {"story_bible": {"provider": "prototype"}})
    governance.approve_policy_version("policy-v1", "owner", now)
    governance.activate_assignment_version("models-v1", "owner", now)
    with pytest.raises(DomainError, match="immutable"):
        governance.approve_policy_version("policy-v1", "owner", now)
    with pytest.raises(DomainError, match="immutable"):
        governance.activate_assignment_version("models-v1", "owner", now)
    call_id = governance.start_provider_call(
        task_attempt_id=attempt_id,
        policy_version="policy-v1",
        assignment_version="models-v1",
        provider_key="prototype",
        model_key="test-model",
        workload="story_bible",
        requested_at=now,
        estimated_minor=0,
        currency="USD",
        rate_card_version="free-trial",
    )
    governance.finish_provider_call(call_id, completed_at=now, usage={}, actual_minor=0)
    with pytest.raises(DomainError, match="only once"):
        governance.finish_provider_call(call_id, completed_at=now, usage={}, actual_minor=0)


def test_governance_documents_reject_secret_shaped_fields(tmp_path) -> None:
    _, governance, _, _ = repositories(tmp_path)
    with pytest.raises(DomainError, match="credentials"):
        governance.create_policy_version("unsafe", {"api_key": "must-not-be-stored"})


def test_existing_lite_schema_v1_upgrades_without_losing_data(tmp_path) -> None:
    database = tmp_path / "state.sqlite3"
    sessions = make_session_factory(f"sqlite:///{database}")
    engine = sessions.kw["bind"]
    from ai_company.adapters.database import Base, CampaignRow
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE cost_ledger")
        connection.exec_driver_sql("DROP TABLE provider_call_ledger")
        connection.exec_driver_sql("DROP TABLE model_assignment_versions")
        connection.exec_driver_sql("DROP TABLE policy_versions")
        connection.exec_driver_sql("PRAGMA user_version=1")
    campaign_id = StoryRepository(sessions).create_campaign("Preserved", SourceType.USER_IDEA, 1)
    initialize_lite_schema(sessions)
    with sessions() as session:
        assert session.execute(text("PRAGMA user_version")).scalar() == 6
        assert session.get(CampaignRow, campaign_id).name == "Preserved"
        assert session.scalar(select(PolicyVersionRow)) is None
        assert session.scalar(select(ModelAssignmentVersionRow)) is None
