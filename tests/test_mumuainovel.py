import pytest

from ai_company.application.mumu_export import blueprint_to_mumu_project
from ai_company.domain.workflow import DomainError
from ai_company.integrations.mumuainovel import MuMuAINovelClient, MuMuSettings


def _blueprint():
    return {
        "kind": "story_blueprint", "is_mock": False, "title": "A Door Left Open",
        "story_bible": {
            "setting": "A coastal town", "timeline": "Three weeks",
            "core_conflict": "A family lie", "emotional_arc": "Distrust to truth",
            "ending": "The lie is exposed",
            "characters": [
                {"name": "Mara", "role": "lead", "motivation": "truth", "secret": "a letter"},
                {"name": "Eli", "role": "brother", "motivation": "repair", "secret": "the sender"},
            ],
        },
        "chapter_plan": [
            {"number": n, "objective": f"Objective {n}", "reveal_or_turn": f"Turn {n}"}
            for n in range(1, 21)
        ],
    }


def test_real_blueprint_converts_to_mumu_import_v1_1() -> None:
    document = blueprint_to_mumu_project(_blueprint())
    assert document["version"] == "1.1.0"
    assert document["project"]["chapter_count"] == 20
    assert len(document["outlines"]) == 20
    assert document["characters"][0]["name"] == "Mara"


def test_mumu_bridge_is_localhost_only() -> None:
    with pytest.raises(DomainError, match="local"):
        MuMuAINovelClient(MuMuSettings("https://remote.example", "user", "password"))
