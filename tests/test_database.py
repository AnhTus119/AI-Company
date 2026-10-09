from datetime import datetime, timezone
from hashlib import sha256

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from ai_company.adapters.database import (
    ArtifactRow,
    AuditEventRow,
    Base,
    CampaignRow,
    ChapterRow,
    GateRow,
    StoryRepository,
    StoryRow,
)
from ai_company.domain.workflow import DomainError, GateName, GateOutcome, SourceType, StoryStage


@pytest.fixture
def repository(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    return StoryRepository(sessionmaker(engine, expire_on_commit=False))


def test_story_draft_survives_new_repository_instance(repository) -> None:
    campaign_id = repository.create_campaign("Trial", SourceType.USER_IDEA, 1)
    story_id = repository.create_story(campaign_id, SourceType.USER_IDEA, "A fictional premise")
    second_repository = StoryRepository(repository.sessions)
    assert second_repository.get_story(story_id).stage == StoryStage.DRAFT
    with repository.sessions() as session:
        events = session.scalars(select(AuditEventRow).order_by(AuditEventRow.created_at)).all()
    assert len(events) == 2


def test_ready_transition_is_transactionally_guarded(repository) -> None:
    campaign_id = repository.create_campaign("Trial", SourceType.USER_IDEA, 1)
    story_id = repository.create_story(campaign_id, SourceType.USER_IDEA, "A fictional premise")
    with pytest.raises(DomainError, match="automated gates"):
        repository.record_production_ready(story_id, datetime.now(timezone.utc))
    assert repository.get_story(story_id).production_ready_at is None


def test_review_rejects_draft(repository) -> None:
    campaign_id = repository.create_campaign("Trial", SourceType.USER_IDEA, 1)
    story_id = repository.create_story(campaign_id, SourceType.USER_IDEA, "A fictional premise")
    with pytest.raises(DomainError, match="production-ready"):
        repository.record_final_review(story_id, False, datetime.now(timezone.utc))


def test_ready_and_rejection_keep_original_kpi_timestamp(repository) -> None:
    campaign_id = repository.create_campaign("Trial", SourceType.USER_IDEA, 1)
    story_id = repository.create_story(campaign_id, SourceType.USER_IDEA, "A fictional premise")
    with repository.sessions.begin() as session:
        row = session.get(StoryRow, story_id)
        row.stage = StoryStage.AUTOMATED_GATES.value
        row.planned_chapters = 20
        row.has_story_bible = True
        row.has_hook_contract = True
        for number in range(1, 21):
            session.add(ChapterRow(
                story_id=story_id, number=number, title=f"Chapter {number}",
                recap=None if number == 1 else "Previously", content="Fictional story text.",
            ))
        for name in GateName:
            session.add(GateRow(story_id=story_id, gate_name=name.value, outcome=GateOutcome.PASS.value))
        for filename in ("hook.mp4", "hook.srt", "story.txt", "caption.txt", "comment.txt"):
            session.add(ArtifactRow(
                story_id=story_id, filename=filename, storage_uri=f"artifact://{filename}",
                sha256_hex=sha256(filename.encode()).hexdigest(), byte_size=len(filename),
                verified=True, is_mock=False,
            ))
    ready_at = datetime(2026, 10, 7, 1, tzinfo=timezone.utc)
    ready = repository.record_production_ready(story_id, ready_at)
    rejected = repository.record_final_review(story_id, False, ready_at)
    assert rejected.production_ready_at == ready.production_ready_at == ready_at
    assert rejected.stage == StoryStage.HUMAN_REJECTED
    assert repository.get_story(story_id).production_ready_at == ready_at
