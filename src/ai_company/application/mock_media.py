"""Low-memory, offline MP4 hook fixture with burned captions and mock audio."""

from __future__ import annotations

import math
import shutil
import tempfile
import wave
from array import array
from dataclasses import dataclass
from pathlib import Path

from ai_company.application.mock_text_assets import HOOK_LINES


WIDTH = 720
HEIGHT = 1280
SECONDS = 15
FPS = 1


@dataclass(frozen=True)
class MockHookVideo:
    path: Path
    duration_seconds: float
    width: int
    height: int
    is_mock: bool = True


def _mock_audio(path: Path) -> None:
    sample_rate = 16000
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        for second in range(SECONDS):
            samples = array("h")
            for index in range(sample_rate):
                # Short tones stand in for two voice turns; never sound like speech.
                active = (second in {0, 7}) and index < sample_rate // 4
                frequency = 440 if second == 0 else 660
                value = int(3500 * math.sin(2 * math.pi * frequency * index / sample_rate)) if active else 0
                samples.append(value)
            output.writeframes(samples.tobytes())


def _frame(second: int) -> bytes:
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (WIDTH, HEIGHT), (18, 26, 46))
    draw = ImageDraw.Draw(image)
    title_font = ImageFont.load_default(size=38)
    caption_font = ImageFont.load_default(size=48)
    draw.text((60, 130), "MOCK HOOK PREVIEW", fill=(190, 208, 236), font=title_font)
    caption = HOOK_LINES[0] if second < 7 else HOOK_LINES[1]
    # Keep text inside the 720 px frame and away from platform UI overlays.
    words = caption.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and draw.textbbox((0, 0), candidate, font=caption_font)[2] > WIDTH - 120:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    if len(lines) > 2:
        raise ValueError("Mock caption exceeds two lines.")
    draw.rounded_rectangle((35, 850, WIDTH - 35, 1050), radius=22, fill=(4, 10, 22))
    for index, line in enumerate(lines):
        width = draw.textbbox((0, 0), line, font=caption_font)[2]
        draw.text(((WIDTH - width) // 2, 895 + index * 70), line, fill="white", font=caption_font)
    return image.tobytes()


def render_mock_hook(destination: Path) -> MockHookVideo:
    """Render a real 15-second 720×1280 MP4; never replace an existing file."""
    try:
        import imageio_ffmpeg
        from PIL import Image  # noqa: F401 -- validates the optional media extra
    except ImportError as exc:
        raise RuntimeError("Install the optional media dependencies before rendering mock video.") from exc

    destination = destination.absolute()
    if destination.exists():
        raise FileExistsError(f"Mock video already exists: {destination}")
    if not destination.parent.is_dir():
        raise ValueError("Mock video destination directory must already exist.")
    staging = Path(tempfile.mkdtemp(prefix=".mock-video-", dir=destination.parent))
    video = staging / "hook.mp4"
    audio = staging / "mock-voice.wav"
    try:
        _mock_audio(audio)
        writer = imageio_ffmpeg.write_frames(
            str(video), (WIDTH, HEIGHT), fps=FPS, codec="libx264",
            quality=4, ffmpeg_log_level="error", ffmpeg_timeout=30,
            audio_path=str(audio), audio_codec="aac",
            output_params=["-preset", "ultrafast", "-movflags", "+faststart"],
        )
        writer.send(None)
        try:
            for second in range(SECONDS):
                writer.send(_frame(second))
        finally:
            writer.close()

        inspected = inspect_mock_hook(video)
        if destination.exists():
            raise FileExistsError(f"Mock video already exists: {destination}")
        video.rename(destination)
        return MockHookVideo(destination, inspected.duration_seconds, WIDTH, HEIGHT)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def inspect_mock_hook(path: Path) -> MockHookVideo:
    try:
        import imageio_ffmpeg
    except ImportError as exc:
        raise RuntimeError("Install the optional media dependencies before checking mock video.") from exc
    frames, duration = imageio_ffmpeg.count_frames_and_secs(str(path))
    if frames != SECONDS * FPS or not 13 <= duration <= 17:
        raise ValueError("Mock video frame count or duration is invalid.")
    reader = imageio_ffmpeg.read_frames(str(path))
    try:
        metadata = next(reader)
    finally:
        reader.close()
    if tuple(metadata["size"]) != (WIDTH, HEIGHT):
        raise ValueError("Mock video dimensions are invalid.")
    return MockHookVideo(path, duration, WIDTH, HEIGHT)
