"""Translate an AI Company real blueprint into MuMuAINovel import schema 1.1.0."""

from __future__ import annotations

from datetime import datetime, timezone

from ai_company.domain.workflow import DomainError


def blueprint_to_mumu_project(blueprint: dict) -> dict:
    if blueprint.get("kind") != "story_blueprint" or blueprint.get("is_mock") is not False:
        raise DomainError("Only a completed real story blueprint can be exported to MuMuAINovel.")
    bible = blueprint.get("story_bible") or {}
    plan = blueprint.get("chapter_plan") or []
    if len(plan) != 20:
        raise DomainError("MuMuAINovel export requires the validated 20-chapter plan.")
    characters = [
        {
            "name": item["name"],
            "role_type": item.get("role"),
            "personality": item.get("motivation"),
            "background": item.get("secret"),
            "is_organization": False,
        }
        for item in bible.get("characters", [])
    ]
    outlines = [
        {
            "title": f"Chapter {item['number']}",
            "content": item["objective"],
            "structure": item["reveal_or_turn"],
            "order_index": item["number"],
        }
        for item in plan
    ]
    return {
        "version": "1.1.0",
        "export_time": datetime.now(timezone.utc).isoformat(),
        "project": {
            "title": blueprint["title"],
            "description": bible.get("core_conflict"),
            "theme": bible.get("emotional_arc"),
            "genre": "English drama",
            "target_words": 12000,
            "current_words": 0,
            "status": "planning",
            "world_time_period": bible.get("timeline"),
            "world_location": bible.get("setting"),
            "world_atmosphere": bible.get("emotional_arc"),
            "world_rules": "Ending contract: " + str(bible.get("ending", "")),
            "chapter_count": 20,
            "narrative_perspective": "third-person limited",
            "character_count": len(characters),
            "outline_mode": "one-to-one",
        },
        "chapters": [],
        "characters": characters,
        "outlines": outlines,
        "relationships": [],
        "organizations": [],
        "organization_members": [],
        "writing_styles": [],
        "generation_history": [],
        "careers": [],
        "character_careers": [],
        "story_memories": [],
        "plot_analysis": [],
        "project_default_style": None,
    }
