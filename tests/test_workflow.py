from dataclasses import replace
from datetime import date, datetime, timezone
from hashlib import sha256
from uuid import uuid4

import pytest

from ai_company.domain.workflow import (
    ArtifactEvidence,
    Chapter,
    DomainError,
    GateName,
    GateOutcome,
    SourceType,
    StorySnapshot,
    StoryStage,
    accept_chapter,
    advance,
    decide_final_review,
    mark_production_ready,
    production_kpi,
)


def complete_snapshot(*, mock_hook: bool = False) -> StorySnapshot:
    chapters = tuple(
        Chapter(n, f"Chapter {n}", "A story continues here.", None if n == 1 else "Earlier events.")
        for n in range(1, 21)
    )
    files = {name: ArtifactEvidence.from_bytes(name, name.encode(), is_mock=mock_hook and name == "hook.mp4")
             for name in ("hook.mp4", "hook.srt", "story.txt", "caption.txt", "comment.txt")}
    return StorySnapshot(
        id=uuid4(),
        source_type=SourceType.USER_IDEA,
        stage=StoryStage.AUTOMATED_GATES,
        chapters=chapters,
        planned_chapters=20,
        has_story_bible=True,
        has_hook_contract=True,
        gates={name: GateOutcome.PASS for name in GateName},
        artifacts=files,
    )


def test_sequential_chapters_and_recaps() -> None:
    snapshot = StorySnapshot(uuid4(), SourceType.USER_IDEA, stage=StoryStage.CHAPTERS)
    with pytest.raises(DomainError, match="recap"):
        Chapter(2, "Two", "Text", None)
    with pytest.raises(DomainError, match="Expected chapter 1"):
        accept_chapter(snapshot, Chapter(2, "Two", "Text", "Previously"))
    snapshot = accept_chapter(snapshot, Chapter(1, "One", "Text"))
    assert len(snapshot.chapters) == 1


def test_stage_requires_bible_plan_and_contract() -> None:
    snapshot = StorySnapshot(uuid4(), SourceType.USER_IDEA, stage=StoryStage.STORY_BIBLE)
    with pytest.raises(DomainError, match="Story Bible"):
        advance(snapshot, StoryStage.CHAPTER_PLAN)
    snapshot = replace(snapshot, has_story_bible=True)
    snapshot = advance(snapshot, StoryStage.CHAPTER_PLAN)
    with pytest.raises(DomainError, match="20-chapter"):
        advance(snapshot, StoryStage.HOOK_CONTRACT)


def test_production_ready_requires_all_gates_and_real_artifacts() -> None:
    snapshot = complete_snapshot()
    with pytest.raises(DomainError, match="Mandatory gates"):
        mark_production_ready(replace(snapshot, gates={}), datetime.now(timezone.utc))
    with pytest.raises(DomainError, match="Mock artifacts"):
        mark_production_ready(complete_snapshot(mock_hook=True), datetime.now(timezone.utc))
    with pytest.raises(DomainError, match="checksum"):
        broken = dict(snapshot.artifacts)
        broken["hook.mp4"] = replace(broken["hook.mp4"], verified=False)
        mark_production_ready(replace(snapshot, artifacts=broken), datetime.now(timezone.utc))


def test_human_rejection_does_not_erase_production_kpi() -> None:
    ready = mark_production_ready(complete_snapshot(), datetime(2026, 10, 6, 18, 30, tzinfo=timezone.utc))
    rejected = decide_final_review(ready, approved=False, at=datetime(2026, 10, 7, 3, tzinfo=timezone.utc))
    assert rejected.stage == StoryStage.HUMAN_REJECTED
    assert production_kpi((rejected,), date(2026, 10, 7)) == 1
    assert rejected.production_ready_at == ready.production_ready_at
