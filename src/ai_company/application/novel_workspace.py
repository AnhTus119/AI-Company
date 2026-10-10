"""Native local novel workspace, independently implemented for AI Company."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator

from ai_company.domain.workflow import DomainError


class WorkspaceCharacter(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    role: str = Field(min_length=1, max_length=120)
    motivation: str = Field(min_length=1, max_length=500)
    secret: str = Field(min_length=1, max_length=500)
    current_state: str = Field(default="planned", min_length=1, max_length=1000)


class WorkspaceOutline(BaseModel):
    chapter_number: int = Field(ge=1, le=20)
    title: str = Field(min_length=1, max_length=300)
    objective: str = Field(min_length=1, max_length=1000)
    reveal_or_turn: str = Field(min_length=1, max_length=1000)
    status: Literal["planned", "drafted", "reviewed", "approved"] = "planned"


class WorkspaceChapter(BaseModel):
    chapter_number: int = Field(ge=1, le=20)
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1, max_length=100_000)
    summary: str = Field(default="", max_length=3000)
    status: Literal["draft", "reviewed", "approved"] = "draft"
    word_count: int = Field(ge=1)
    continuity_notes: list[str] = Field(default_factory=list, max_length=20)
    updated_at: datetime

    @field_validator("continuity_notes")
    @classmethod
    def bounded_notes(cls, notes: list[str]) -> list[str]:
        if any(not item.strip() or len(item) > 500 for item in notes):
            raise ValueError("Continuity notes must contain 1–500 characters.")
        return [item.strip() for item in notes]


class WorkspaceForeshadow(BaseModel):
    id: UUID
    setup: str = Field(min_length=1, max_length=1000)
    planted_chapter: int = Field(ge=0, le=20)
    planned_payoff_chapter: int = Field(ge=1, le=20)
    status: Literal["planned", "planted", "resolved", "abandoned"] = "planned"
    resolution: str | None = Field(default=None, max_length=2000)
    resolved_chapter: int | None = Field(default=None, ge=1, le=20)


class WorkspaceContinuity(BaseModel):
    last_completed_chapter: int = Field(default=0, ge=0, le=20)
    open_loops: list[str] = Field(default_factory=list, max_length=100)
    timeline_notes: list[str] = Field(default_factory=list, max_length=200)

    @field_validator("open_loops", "timeline_notes")
    @classmethod
    def bounded_entries(cls, entries: list[str]) -> list[str]:
        if any(not item.strip() or len(item) > 1000 for item in entries):
            raise ValueError("Continuity entries must contain 1–1000 characters.")
        return [item.strip() for item in entries]


class NovelWorkspace(BaseModel):
    schema_version: int = Field(default=1, ge=1, le=1)
    story_id: UUID
    title: str = Field(min_length=1, max_length=200)
    status: Literal["planning", "drafting", "review", "complete"] = "planning"
    story_bible: dict
    hook_contract: dict
    characters: list[WorkspaceCharacter] = Field(min_length=2, max_length=20)
    outlines: list[WorkspaceOutline] = Field(min_length=20, max_length=20)
    chapters: list[WorkspaceChapter] = Field(default_factory=list, max_length=20)
    continuity: WorkspaceContinuity
    foreshadows: list[WorkspaceForeshadow] = Field(default_factory=list, max_length=200)
    provenance: dict

    @field_validator("outlines")
    @classmethod
    def sequential_outlines(cls, outlines: list[WorkspaceOutline]) -> list[WorkspaceOutline]:
        if [item.chapter_number for item in outlines] != list(range(1, 21)):
            raise ValueError("Workspace outlines must be sequential chapters 1 through 20.")
        return outlines

    @field_validator("chapters")
    @classmethod
    def unique_chapters(cls, chapters: list[WorkspaceChapter]) -> list[WorkspaceChapter]:
        numbers = [item.chapter_number for item in chapters]
        if len(numbers) != len(set(numbers)):
            raise ValueError("Workspace chapter numbers must be unique.")
        return sorted(chapters, key=lambda item: item.chapter_number)


class ChapterDraftInput(BaseModel):
    expected_version: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1, max_length=100_000)
    summary: str = Field(default="", max_length=3000)
    status: Literal["draft", "reviewed", "approved"] = "draft"
    continuity_notes: list[str] = Field(default_factory=list, max_length=20)
    new_open_loops: list[str] = Field(default_factory=list, max_length=20)
    close_open_loops: list[str] = Field(default_factory=list, max_length=20)


class ForeshadowInput(BaseModel):
    expected_version: int = Field(ge=1)
    setup: str = Field(min_length=1, max_length=1000)
    planted_chapter: int = Field(default=0, ge=0, le=20)
    planned_payoff_chapter: int = Field(ge=1, le=20)


def materialize_workspace(story_id: UUID, blueprint: dict) -> NovelWorkspace:
    if blueprint.get("kind") != "story_blueprint" or blueprint.get("is_mock") is not False:
        raise DomainError("A native workspace requires a completed real blueprint.")
    bible = blueprint.get("story_bible") or {}
    hook = blueprint.get("hook_contract") or {}
    plan = blueprint.get("chapter_plan") or []
    try:
        return NovelWorkspace(
            story_id=story_id,
            title=blueprint["title"],
            story_bible=bible,
            hook_contract=hook,
            characters=[WorkspaceCharacter(**item) for item in bible.get("characters", [])],
            outlines=[WorkspaceOutline(
                chapter_number=item["number"],
                title=f"Chapter {item['number']}",
                objective=item["objective"],
                reveal_or_turn=item["reveal_or_turn"],
            ) for item in plan],
            continuity=WorkspaceContinuity(open_loops=[hook["open_loop"]]),
            foreshadows=[WorkspaceForeshadow(
                id=uuid4(), setup=hook["hook_event"], planted_chapter=0,
                planned_payoff_chapter=hook["planned_payoff_chapter"], status="planted",
            )],
            provenance={
                "source": "ai_company_real_blueprint",
                "provider": (blueprint.get("audit") or {}).get("provider"),
                "model": (blueprint.get("audit") or {}).get("model"),
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise DomainError("The real blueprint cannot be materialized as a novel workspace.") from exc


def apply_chapter_draft(
    workspace: NovelWorkspace, chapter_number: int, body: ChapterDraftInput,
) -> NovelWorkspace:
    if not 1 <= chapter_number <= 20:
        raise DomainError("Chapter number must be between 1 and 20.")
    now = datetime.now(timezone.utc)
    words = re.findall(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*", body.content)
    chapter = WorkspaceChapter(
        chapter_number=chapter_number, title=body.title.strip(), content=body.content,
        summary=body.summary, status=body.status, word_count=len(words),
        continuity_notes=body.continuity_notes, updated_at=now,
    )
    chapters = {item.chapter_number: item for item in workspace.chapters}
    chapters[chapter_number] = chapter
    outlines = [
        item.model_copy(update={"status": "drafted" if body.status == "draft" else body.status})
        if item.chapter_number == chapter_number else item
        for item in workspace.outlines
    ]
    loops = [item for item in workspace.continuity.open_loops if item not in set(body.close_open_loops)]
    for item in body.new_open_loops:
        clean = item.strip()
        if clean and clean not in loops:
            loops.append(clean)
    completed = max(
        (item.chapter_number for item in chapters.values() if item.status in {"reviewed", "approved"}),
        default=workspace.continuity.last_completed_chapter,
    )
    continuity = WorkspaceContinuity(
        last_completed_chapter=completed,
        open_loops=loops,
        timeline_notes=[*workspace.continuity.timeline_notes, *body.continuity_notes],
    )
    return NovelWorkspace.model_validate({
        **workspace.model_dump(),
        "status": "review" if any(item.status == "reviewed" for item in chapters.values()) else "drafting",
        "chapters": sorted(chapters.values(), key=lambda item: item.chapter_number),
        "outlines": outlines,
        "continuity": continuity,
    })


def add_foreshadow(workspace: NovelWorkspace, body: ForeshadowInput) -> NovelWorkspace:
    if body.planted_chapter and body.planned_payoff_chapter < body.planted_chapter:
        raise DomainError("Foreshadow payoff cannot precede the planted chapter.")
    item = WorkspaceForeshadow(
        id=uuid4(), setup=body.setup.strip(), planted_chapter=body.planted_chapter,
        planned_payoff_chapter=body.planned_payoff_chapter,
        status="planted" if body.planted_chapter else "planned",
    )
    return NovelWorkspace.model_validate({
        **workspace.model_dump(), "foreshadows": [*workspace.foreshadows, item],
    })
