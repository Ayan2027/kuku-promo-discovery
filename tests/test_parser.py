
import pytest

from src.ingestion.screenplay_parser import (
    parse_screenplay_text,
    normalize_segment_label,
)


def make_episode(scene_metadata: str) -> str:
    return f"""
EPISODE NUMBER: Episode 1
EPISODE LOGLINE: A test episode.
CONTINUITY NOTES: Test continuity.

--- SCRIPT START ---

SCENE 01
{scene_metadata}

**CAMERA:**
Start: (00:00.00) | End: (00:05.00)
A close-up of the main character.

**ACTION:**
Start: (00:01.00) | End: (00:05.00)
The character looks shocked.

**LADY JULIANA (Desperate, Pleading):**
Start: (00:02.00) | End: (00:04.00)
"Why did you betray me?"

**SOUND FX:**
Start: (00:03.00) | End: (00:05.00)
A dramatic musical sting.

--- SCRIPT END ---
"""


def test_standard_scene_format():
    text = make_episode(
        """
Scene heading: INT. CATHEDRAL – DAY
Scene start: 00:00.00
Scene end: 00:10.00
"""
    )

    episode, warnings = parse_screenplay_text(text)

    assert episode.episode_number == 1
    assert len(episode.scenes) == 1
    assert len(episode.segments) == 4
    assert not warnings


def test_uppercase_scene_format():
    text = make_episode(
        """
SCENE HEADING: EXT. WOODLAND PATH – NIGHT
SCENE START: 00:00.00
SCENE END: 00:10.00
"""
    )

    episode, warnings = parse_screenplay_text(text)

    assert len(episode.scenes) == 1
    assert episode.scenes[0].scene_heading == (
        "EXT. WOODLAND PATH – NIGHT"
    )


def test_segment_categories():
    text = make_episode(
        """
Scene heading: INT. ROOM – DAY
Scene start: 00:00.00
Scene end: 00:10.00
"""
    )

    episode, _ = parse_screenplay_text(text)

    categories = [
        segment.segment_type
        for segment in episode.segments
    ]

    assert categories == [
        "CAMERA",
        "ACTION",
        "DIALOGUE",
        "SOUND FX",
    ]


def test_dialogue_speaker_and_direction():
    segment_type, speaker, direction = (
        normalize_segment_label(
            "LADY JULIANA (Desperate, Pleading):"
        )
    )

    assert segment_type == "DIALOGUE"
    assert speaker == "LADY JULIANA"
    assert direction == "Desperate, Pleading"


def test_overlapping_intervals_are_preserved():
    text = make_episode(
        """
Scene heading: INT. ROOM – DAY
Scene start: 00:00.00
Scene end: 00:10.00
"""
    )

    episode, _ = parse_screenplay_text(text)

    camera = episode.segments[0]
    action = episode.segments[1]

    assert camera.start_seconds == 0
    assert action.start_seconds == 1

    assert camera.end_seconds == 5
    assert action.end_seconds == 5


def test_missing_scene_timestamp_is_reported():
    text = make_episode(
        """
Scene heading: INT. ROOM – DAY
Scene start: 00:00.00
"""
    )

    with pytest.raises(ValueError):
        parse_screenplay_text(text)


def test_invalid_segment_timestamp_is_reported():
    text = make_episode(
        """
Scene heading: INT. ROOM – DAY
Scene start: 00:00.00
Scene end: 00:10.00
"""
    )

    text = text.replace(
        "Start: (00:02.00) | End: (00:04.00)",
        "Start: (00:70.00) | End: (00:04.00)"
    )

    episode, warnings = parse_screenplay_text(text)

    assert any(
        "invalid timestamp" in warning.lower()
        for warning in warnings
    )


def test_missing_episode_number():
    text = """
EPISODE LOGLINE: Test
SCENE 01
"""

    with pytest.raises(ValueError):
        parse_screenplay_text(text)
