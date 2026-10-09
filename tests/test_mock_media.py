import importlib.util

import pytest

from ai_company.application.mock_media import HEIGHT, SECONDS, WIDTH, render_mock_hook


@pytest.mark.skipif(importlib.util.find_spec("imageio_ffmpeg") is None, reason="media extra not installed")
def test_mock_hook_is_playable_fifteen_second_vertical_mp4(tmp_path) -> None:
    import imageio_ffmpeg

    destination = tmp_path / "hook.mp4"
    result = render_mock_hook(destination)
    assert result.is_mock is True
    assert result.path == destination
    assert (result.width, result.height) == (WIDTH, HEIGHT)
    assert 13 <= result.duration_seconds <= 17
    assert destination.stat().st_size > 1000
    count, duration = imageio_ffmpeg.count_frames_and_secs(str(destination))
    assert count == SECONDS and 13 <= duration <= 17
    with pytest.raises(FileExistsError):
        render_mock_hook(destination)
