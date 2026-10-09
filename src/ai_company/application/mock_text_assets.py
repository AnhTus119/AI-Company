"""Text-side fixtures for the v1 output profile."""

from __future__ import annotations

from ai_company.application.mock_blueprint import validate_mock_blueprint


HOOK_LINES = (
    "A: What happened at the door?",
    "B: The answer is in the story.",
)


def render_mock_text_assets(blueprint: dict, chapter_checkpoint: dict) -> dict[str, bytes]:
    validate_mock_blueprint(blueprint)
    chapters = chapter_checkpoint.get("chapters")
    if chapter_checkpoint.get("kind") != "mock_chapters" or chapter_checkpoint.get("is_mock") is not True:
        raise ValueError("Only a mock chapter checkpoint can be rendered here.")
    if not isinstance(chapters, list) or len(chapters) != 20:
        raise ValueError("Twenty mock chapters are required for text export.")
    if [chapter.get("number") for chapter in chapters if isinstance(chapter, dict)] != list(range(1, 21)):
        raise ValueError("Mock chapters must be sequential before text export.")

    sections = [blueprint["title"]]
    for chapter in chapters:
        if not all(isinstance(chapter.get(key), str) and chapter[key].strip()
                   for key in ("title", "content")):
            raise ValueError("Every mock chapter needs a title and content.")
        if chapter["number"] > 1 and not (chapter.get("recap") or "").strip():
            raise ValueError("Mock chapters after the first need a recap.")
        sections.append(chapter["title"])
        if chapter["number"] > 1:
            sections.append(chapter["recap"])
        sections.append(chapter["content"])
    story = "\n\n".join(sections) + "\n"
    subtitle = (
        "1\n00:00:00,000 --> 00:00:07,000\n"
        f"{HOOK_LINES[0]}\n\n"
        "2\n00:00:07,000 --> 00:00:15,000\n"
        f"{HOOK_LINES[1]}\n"
    )
    return {
        "story.txt": story.encode("utf-8"),
        "hook.srt": subtitle.encode("utf-8"),
        "caption.txt": b"A secret changes everything. Read the story.\n",
        "comment.txt": b"What would you do next? Share your take below.\n",
    }
