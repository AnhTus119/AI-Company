from datetime import datetime, timezone
from uuid import uuid4

import pytest

from ai_company.application.mock_export import export_mock_package
from ai_company.application.mock_blueprint import DeterministicMockBlueprintProvider
from ai_company.application.mock_chapters import DeterministicMockChapterProvider
from ai_company.application.mock_text_assets import render_mock_text_assets
from ai_company.domain.workflow import REQUIRED_ARTIFACTS


def test_mock_export_is_versioned_and_cannot_overwrite(tmp_path) -> None:
    sources = tmp_path / "sources"
    sources.mkdir()
    files = {}
    for name in REQUIRED_ARTIFACTS:
        path = sources / name
        path.write_bytes(f"synthetic fixture for {name}".encode("utf-8"))
        files[name] = path
    output = tmp_path / "delivery"
    story_id = uuid4()
    at = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)

    result = export_mock_package(output, story_id, "A Synthetic Story", files, at=at)
    assert result.directory.parent.name == "MOCK_OUTPUT"
    assert set(path.name for path in result.directory.iterdir()) == REQUIRED_ARTIFACTS
    assert all(item.is_mock and item.verified for item in result.evidence.values())
    with pytest.raises(FileExistsError):
        export_mock_package(output, story_id, "A Synthetic Story", files, at=at)


def test_mock_text_assets_contain_twenty_sequential_chapters() -> None:
    blueprint = DeterministicMockBlueprintProvider().generate("An invented premise")
    checkpoint = DeterministicMockChapterProvider().generate(blueprint)
    assets = render_mock_text_assets(blueprint, checkpoint)
    assert set(assets) == {"story.txt", "hook.srt", "caption.txt", "comment.txt"}
    story = assets["story.txt"].decode("utf-8")
    assert story.count("Synthetic Chapter ") == 20
    assert "Synthetic Chapter 01" in story and "Synthetic Chapter 20" in story
    assert b"00:00:15,000" in assets["hook.srt"]
