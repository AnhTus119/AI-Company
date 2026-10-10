"""Deterministic story lifecycle and production readiness gates."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime, timezone
from enum import StrEnum
from hashlib import sha256
from typing import Mapping
from uuid import UUID
from zoneinfo import ZoneInfo


class DomainError(ValueError):
    """A requested transition violates a production invariant."""


class SourceType(StrEnum):
    REFERENCE = "reference"
    USER_IDEA = "user_idea"
    REFERENCE_USER_IDEA = "reference_user_idea"
    AUTONOMOUS = "autonomous"


class ApprovalMode(StrEnum):
    MANUAL = "manual"
    AUTO = "auto"


class StoryStage(StrEnum):
    DRAFT = "draft"
    ADMITTED = "admitted"
    REFERENCE_ANALYSIS = "reference_analysis"
    CONCEPT = "concept"
    STORY_BIBLE = "story_bible"
    CHAPTER_PLAN = "chapter_plan"
    HOOK_CONTRACT = "hook_contract"
    CHAPTERS = "chapters_sequential"
    HOOK_MEDIA = "hook_media"
    METADATA = "metadata"
    AUTOMATED_GATES = "automated_gates"
    PRODUCTION_READY = "production_ready"
    APPROVED = "approved"
    HUMAN_REJECTED = "human_rejected"


class GateName(StrEnum):
    SAFETY = "safety"
    ORIGINALITY = "originality"
    STORY_BIBLE = "story_bible"
    CHAPTERS = "chapters"
    HOOK = "hook"
    HOOK_STORY_CONTINUITY = "hook_story_continuity"
    FINAL_STORY = "final_story"
    BUDGET_POLICY = "budget_policy"
    ARTIFACT_INTEGRITY = "artifact_integrity"


class GateOutcome(StrEnum):
    PASS = "pass"
    WARNING = "warning"
    CRITICAL_FAIL = "critical_fail"
    NEEDS_REVIEW = "needs_review"


REQUIRED_GATE_NAMES = frozenset(GateName)
REQUIRED_ARTIFACTS = frozenset(
    {"hook.mp4", "hook.srt", "story.txt", "caption.txt", "comment.txt"}
)
KPI_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")


@dataclass(frozen=True)
class Chapter:
    number: int
    title: str
    content: str
    recap: str | None = None

    def __post_init__(self) -> None:
        if not 1 <= self.number <= 20:
            raise DomainError("A chapter number must be between 1 and 20.")
        if not self.title.strip() or not self.content.strip():
            raise DomainError("A chapter needs a title and content.")
        if self.number == 1 and self.recap is not None:
            raise DomainError("Chapter 1 cannot have a recap.")
        if self.number > 1 and not (self.recap or "").strip():
            raise DomainError("Chapters 2–20 need a recap.")

    @property
    def word_count(self) -> int:
        return len(self.content.split())


@dataclass(frozen=True)
class ArtifactEvidence:
    filename: str
    sha256_hex: str
    byte_size: int
    verified: bool
    is_mock: bool = False

    def __post_init__(self) -> None:
        if len(self.sha256_hex) != 64 or any(c not in "0123456789abcdef" for c in self.sha256_hex):
            raise DomainError("Artifact evidence needs a lowercase SHA-256 digest.")
        if self.byte_size <= 0:
            raise DomainError("Artifact evidence needs a non-empty file.")

    @classmethod
    def from_bytes(cls, filename: str, data: bytes, *, is_mock: bool = False) -> ArtifactEvidence:
        return cls(filename, sha256(data).hexdigest(), len(data), True, is_mock)


@dataclass(frozen=True)
class StorySnapshot:
    id: UUID
    source_type: SourceType
    stage: StoryStage = StoryStage.DRAFT
    chapters: tuple[Chapter, ...] = ()
    gates: Mapping[GateName, GateOutcome] = field(default_factory=dict)
    artifacts: Mapping[str, ArtifactEvidence] = field(default_factory=dict)
    production_ready_at: datetime | None = None
    review_decision_at: datetime | None = None
    planned_chapters: int = 0
    has_story_bible: bool = False
    has_hook_contract: bool = False

    @property
    def has_mock_artifacts(self) -> bool:
        return any(evidence.is_mock for evidence in self.artifacts.values())


_NEXT_STAGE: dict[StoryStage, StoryStage] = {
    StoryStage.DRAFT: StoryStage.ADMITTED,
    StoryStage.REFERENCE_ANALYSIS: StoryStage.CONCEPT,
    StoryStage.CONCEPT: StoryStage.STORY_BIBLE,
    StoryStage.STORY_BIBLE: StoryStage.CHAPTER_PLAN,
    StoryStage.CHAPTER_PLAN: StoryStage.HOOK_CONTRACT,
    StoryStage.HOOK_CONTRACT: StoryStage.CHAPTERS,
    StoryStage.CHAPTERS: StoryStage.HOOK_MEDIA,
    StoryStage.HOOK_MEDIA: StoryStage.METADATA,
    StoryStage.METADATA: StoryStage.AUTOMATED_GATES,
}


def advance(snapshot: StorySnapshot, target: StoryStage) -> StorySnapshot:
    """Advance a story by one allowed stage, with source-specific intake."""
    if snapshot.stage == StoryStage.ADMITTED:
        expected = (
            StoryStage.REFERENCE_ANALYSIS
            if snapshot.source_type in {SourceType.REFERENCE, SourceType.REFERENCE_USER_IDEA}
            else StoryStage.CONCEPT
        )
    else:
        expected = _NEXT_STAGE.get(snapshot.stage)
    if expected != target:
        raise DomainError(f"Cannot advance {snapshot.stage} to {target}.")
    if target == StoryStage.CHAPTER_PLAN and not snapshot.has_story_bible:
        raise DomainError("A Story Bible is required before chapter planning.")
    if target == StoryStage.HOOK_CONTRACT and snapshot.planned_chapters != 20:
        raise DomainError("An exactly 20-chapter plan is required.")
    if target == StoryStage.CHAPTERS and not snapshot.has_hook_contract:
        raise DomainError("A Hook–Story Contract is required before chapters.")
    if target == StoryStage.HOOK_MEDIA and len(snapshot.chapters) != 20:
        raise DomainError("All 20 chapters must be accepted before hook media.")
    return replace(snapshot, stage=target)


def accept_chapter(snapshot: StorySnapshot, chapter: Chapter) -> StorySnapshot:
    if snapshot.stage != StoryStage.CHAPTERS:
        raise DomainError("Chapters can only be accepted during chapter generation.")
    expected_number = len(snapshot.chapters) + 1
    if chapter.number != expected_number:
        raise DomainError(f"Expected chapter {expected_number}; received {chapter.number}.")
    return replace(snapshot, chapters=(*snapshot.chapters, chapter))


def mark_production_ready(snapshot: StorySnapshot, at: datetime) -> StorySnapshot:
    if snapshot.stage != StoryStage.AUTOMATED_GATES:
        raise DomainError("The story has not reached automated gates.")
    if snapshot.production_ready_at is not None:
        raise DomainError("Production readiness is recorded only once.")
    if at.tzinfo is None:
        raise DomainError("A timezone-aware timestamp is required.")
    if len(snapshot.chapters) != 20 or snapshot.planned_chapters != 20:
        raise DomainError("Exactly 20 planned and accepted chapters are required.")
    if not snapshot.has_story_bible or not snapshot.has_hook_contract:
        raise DomainError("Story Bible and Hook–Story Contract are required.")
    failed = sorted(
        name.value for name in REQUIRED_GATE_NAMES
        if snapshot.gates.get(name) != GateOutcome.PASS
    )
    if failed:
        raise DomainError(f"Mandatory gates have not passed: {', '.join(failed)}.")
    missing = sorted(REQUIRED_ARTIFACTS - snapshot.artifacts.keys())
    if missing:
        raise DomainError(f"Required artifacts are missing: {', '.join(missing)}.")
    if any(not snapshot.artifacts[name].verified for name in REQUIRED_ARTIFACTS):
        raise DomainError("A required artifact has not passed checksum verification.")
    if snapshot.has_mock_artifacts:
        raise DomainError("Mock artifacts cannot be counted as production-ready.")
    return replace(snapshot, stage=StoryStage.PRODUCTION_READY, production_ready_at=at.astimezone(timezone.utc))


def decide_final_review(snapshot: StorySnapshot, *, approved: bool, at: datetime) -> StorySnapshot:
    if snapshot.stage != StoryStage.PRODUCTION_READY:
        raise DomainError("Only production-ready stories can receive final review.")
    if at.tzinfo is None:
        raise DomainError("A timezone-aware timestamp is required.")
    return replace(
        snapshot,
        stage=StoryStage.APPROVED if approved else StoryStage.HUMAN_REJECTED,
        review_decision_at=at.astimezone(timezone.utc),
    )


def production_kpi(stories: tuple[StorySnapshot, ...], local_day: date) -> int:
    return sum(
        story.production_ready_at is not None
        and story.production_ready_at.astimezone(KPI_TIMEZONE).date() == local_day
        for story in stories
    )
