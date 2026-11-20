
import re
from pathlib import Path

from src.models import Episode, Scene, Segment
from src.utils.timestamps import parse_timestamp


# ============================================================
# 1. REGEX PATTERNS
# ============================================================

EPISODE_NUMBER_RE = re.compile(
    r"^[ \t]*EPISODE NUMBER:[ \t]*Episode[ \t]+(\d+)[ \t]*$",
    re.IGNORECASE | re.MULTILINE
)

LOGLINE_RE = re.compile(
    r"^[ \t]*EPISODE LOGLINE:[ \t]*(.*)$",
    re.IGNORECASE | re.MULTILINE
)

CONTINUITY_RE = re.compile(
    r"^[ \t]*CONTINUITY NOTES:[ \t]*(.*)$",
    re.IGNORECASE | re.MULTILINE
)

SCENE_MARKER_RE = re.compile(
    r"^[ \t]*SCENE[ \t]+(\d+)[ \t]*$",
    re.IGNORECASE | re.MULTILINE
)

# Supports both:
# Scene heading:
# SCENE HEADING:

SCENE_HEADING_RE = re.compile(
    r"^[ \t]*(?:SCENE[ \t]+)?HEADING[ \t]*:[ \t]*(.+?)[ \t]*$",
    re.IGNORECASE | re.MULTILINE
)

# Supports both:
# Scene start:
# SCENE START:

SCENE_START_RE = re.compile(
    r"^[ \t]*(?:SCENE[ \t]+)?START[ \t]*:[ \t]*([^\r\n]+)$",
    re.IGNORECASE | re.MULTILINE
)

SCENE_END_RE = re.compile(
    r"^[ \t]*(?:SCENE[ \t]+)?END[ \t]*:[ \t]*([^\r\n]+)$",
    re.IGNORECASE | re.MULTILINE
)

# Matches screenplay segment headings:
# **CAMERA:**
# **ACTION:**
# **LADY JULIANA (Desperate, Pleading):**

SEGMENT_HEADING_RE = re.compile(
    r"^[ \t]*\*\*(?P<label>[^*\r\n]+)\*\*[ \t]*$",
    re.MULTILINE
)

# Matches:
# Start: (00:00.00) | End: (00:04.80)

SEGMENT_TIMING_RE = re.compile(
    r"^[ \t]*Start[ \t]*:[ \t]*\((?P<start>[^)]*)\)"
    r"[ \t]*\|[ \t]*End[ \t]*:[ \t]*\((?P<end>[^)]*)\)"
    r"[ \t]*$",
    re.IGNORECASE | re.MULTILINE
)


# ============================================================
# 2. FILE DECODING
# ============================================================

def decode_screenplay(file_path: Path) -> str:
    """
    Decode screenplay text using common encodings.
    """

    raw = file_path.read_bytes()

    encodings = [
        "utf-8-sig",
        "utf-8",
        "cp1252",
    ]

    for encoding in encodings:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue

    raise ValueError(
        f"Unable to decode screenplay: {file_path.name}"
    )


# ============================================================
# 3. BASIC EXTRACTION HELPERS
# ============================================================

def extract_single(pattern, text, default=""):
    """
    Extract the first regex match.
    """

    match = pattern.search(text)

    if not match:
        return default

    return match.group(1).strip()


def clean_content(content: str) -> str:
    """
    Remove surrounding whitespace and script section markers while
    preserving the original internal screenplay content.
    """

    content = re.sub(
        r"-{2,}\s*SCRIPT\s+(?:START|END)\s*-{2,}",
        "",
        content,
        flags=re.IGNORECASE,
    )

    return content.strip()


def normalize_segment_label(label: str):
    """
    Identify segment type, speaker and emotional direction.

    Returns:
        segment_type, speaker, direction
    """

    label = label.strip().rstrip(":").strip()

    normalized = label.upper()

    if normalized == "CAMERA":
        return "CAMERA", None, None

    if normalized == "ACTION":
        return "ACTION", None, None

    if normalized in {
        "SOUND FX",
        "SOUND EFFECTS",
        "SFX",
    }:
        return "SOUND FX", None, None

    # Extract character directions.
    directions = re.findall(
        r"\((.*?)\)",
        label
    )

    # Speaker is the text before the first parenthesis.
    speaker = re.split(
        r"\s*\(",
        label,
        maxsplit=1
    )[0].strip()

    direction = "; ".join(
        item.strip()
        for item in directions
        if item.strip()
    ) or None

    if not speaker:
        return "OTHER", None, None

    return "DIALOGUE", speaker, direction


# ============================================================
# 4. SCENE METADATA EXTRACTION
# ============================================================

def extract_scene_metadata(scene_text: str):
    """
    Extract scene heading and timestamps.

    Handles uppercase and title-case metadata.
    """

    heading_match = SCENE_HEADING_RE.search(scene_text)

    start_match = SCENE_START_RE.search(scene_text)

    end_match = SCENE_END_RE.search(scene_text)

    heading = (
        heading_match.group(1).strip()
        if heading_match
        else "UNKNOWN SCENE"
    )

    start_raw = (
        start_match.group(1).strip()
        if start_match
        else ""
    )

    end_raw = (
        end_match.group(1).strip()
        if end_match
        else ""
    )

    return heading, start_raw, end_raw


# ============================================================
# 5. SEGMENT EXTRACTION
# ============================================================

def extract_segments(
    scene_text: str,
    episode_number: int,
    scene_id: str,
    source_file: str,
    line_offset: int,
    warnings: list[str],
):
    """
    Extract all timed segments from a scene.

    Overlapping segments are preserved independently.

    Each segment retains:
        - Episode number
        - Scene ID
        - Segment ID
        - Original timestamps
        - Converted timestamps
        - Original content
        - Source file
        - Source line
    """

    segments = []

    headings = list(
        SEGMENT_HEADING_RE.finditer(scene_text)
    )

    for index, heading_match in enumerate(headings):

        label = heading_match.group("label").strip()

        block_start = heading_match.end()

        if index + 1 < len(headings):
            block_end = headings[index + 1].start()
        else:
            block_end = len(scene_text)

        block_text = scene_text[
            block_start:block_end
        ]

        segment_id = (
            f"{scene_id}_SEG{index + 1:04d}"
        )

        # ----------------------------------------------------
        # Extract timing
        # ----------------------------------------------------

        timing_match = SEGMENT_TIMING_RE.search(
            block_text
        )

        if not timing_match:

            warnings.append(
                f"{source_file}: {segment_id}: "
                f"missing or malformed timing for '{label}'."
            )

            continue

        raw_start = timing_match.group("start").strip()

        raw_end = timing_match.group("end").strip()

        # ----------------------------------------------------
        # Convert timestamps
        # ----------------------------------------------------

        try:

            start_seconds = parse_timestamp(raw_start)

            end_seconds = parse_timestamp(raw_end)

            if end_seconds <= start_seconds:
                raise ValueError(
                    "Segment end must be greater than start."
                )

        except (ValueError, TypeError) as exc:

            warnings.append(
                f"{source_file}: {segment_id}: "
                f"invalid timestamp: {exc}"
            )

            continue

        # ----------------------------------------------------
        # Extract original content
        # ----------------------------------------------------

        content = block_text[
            timing_match.end():
        ]

        content = clean_content(content)

        if not content:

            warnings.append(
                f"{source_file}: {segment_id}: "
                "empty segment content."
            )

            continue

        # ----------------------------------------------------
        # Identify segment type
        # ----------------------------------------------------

        segment_type, speaker, direction = (
            normalize_segment_label(label)
        )

        # ----------------------------------------------------
        # Source line tracking
        # ----------------------------------------------------

        source_line = (
            line_offset
            + scene_text.count(
                "\n",
                0,
                heading_match.start()
            )
            + 1
        )

        # ----------------------------------------------------
        # Create structured segment
        # ----------------------------------------------------

        try:

            segment = Segment(
                segment_id=segment_id,

                episode_number=episode_number,

                scene_id=scene_id,

                segment_type=segment_type,

                speaker=speaker,

                emotion_or_direction=direction,

                start_timestamp=raw_start,

                end_timestamp=raw_end,

                start_seconds=start_seconds,

                end_seconds=end_seconds,

                content=content,

                source_file=source_file,

                source_line=source_line,
            )

            segments.append(segment)

        except Exception as exc:

            warnings.append(
                f"{source_file}: {segment_id}: "
                f"segment validation failed: {exc}"
            )

    return segments


# ============================================================
# 6. SCENE PARSER
# ============================================================

def parse_scene(
    scene_text: str,
    episode_number: int,
    scene_number: int,
    source_file: str,
    line_offset: int,
    warnings: list[str],
):
    """
    Parse one screenplay scene.

    Returns:
        Scene object, list of Segment objects

    Invalid scene boundaries are reported and skipped.
    """

    scene_id = (
        f"E{episode_number:03d}_S{scene_number:02d}"
    )

    # --------------------------------------------------------
    # Extract scene metadata
    # --------------------------------------------------------

    heading, start_raw, end_raw = (
        extract_scene_metadata(scene_text)
    )

    # --------------------------------------------------------
    # Check missing metadata
    # --------------------------------------------------------

    if not start_raw or not end_raw:

        warnings.append(
            f"{source_file}: {scene_id}: "
            "missing scene start/end timestamp."
        )

        return None, []

    # --------------------------------------------------------
    # Convert scene timestamps
    # --------------------------------------------------------

    try:

        scene_start = parse_timestamp(start_raw)

        scene_end = parse_timestamp(end_raw)

        if scene_end <= scene_start:
            raise ValueError(
                "Scene end must be greater than scene start."
            )

    except (ValueError, TypeError) as exc:

        warnings.append(
            f"{source_file}: {scene_id}: "
            f"invalid scene timestamp: {exc}"
        )

        return None, []

    # --------------------------------------------------------
    # Create scene
    # --------------------------------------------------------

    scene = Scene(
        scene_id=scene_id,

        episode_number=episode_number,

        scene_heading=heading,

        start_timestamp=start_raw,

        end_timestamp=end_raw,

        start_seconds=scene_start,

        end_seconds=scene_end,

    )

    # --------------------------------------------------------
    # Extract segments
    # --------------------------------------------------------

    segments = extract_segments(
        scene_text=scene_text,

        episode_number=episode_number,

        scene_id=scene_id,

        source_file=source_file,

        line_offset=line_offset,

        warnings=warnings,
    )

    scene.segment_ids = [
        segment.segment_id
        for segment in segments
    ]

    # --------------------------------------------------------
    # Check segment boundaries
    # --------------------------------------------------------

    for segment in segments:

        if (
            segment.start_seconds < scene_start
            or segment.end_seconds > scene_end
        ):

            warnings.append(
                f"{source_file}: {segment.segment_id}: "
                "segment extends outside scene boundaries."
            )

    return scene, segments


# ============================================================
# 7. COMPLETE EPISODE PARSER
# ============================================================

def parse_screenplay_text(
    text: str,
    source_file: str = "unknown.txt",
):
    """
    Parse complete screenplay text.

    Returns:
        Episode object
        List of parsing warnings
    """

    warnings = []

    # --------------------------------------------------------
    # Episode number
    # --------------------------------------------------------

    episode_number_raw = extract_single(
        EPISODE_NUMBER_RE,
        text,
    )

    if not episode_number_raw:

        raise ValueError(
            f"Episode number missing in {source_file}"
        )

    episode_number = int(episode_number_raw)

    # --------------------------------------------------------
    # Episode metadata
    # --------------------------------------------------------

    logline = extract_single(
        LOGLINE_RE,
        text,
    )

    continuity_notes = extract_single(
        CONTINUITY_RE,
        text,
    )

    if not logline:

        warnings.append(
            f"{source_file}: missing episode logline."
        )

    if not continuity_notes:

        warnings.append(
            f"{source_file}: missing continuity notes."
        )

    # --------------------------------------------------------
    # Script markers
    # --------------------------------------------------------

    if "--- SCRIPT START ---" not in text:

        warnings.append(
            f"{source_file}: SCRIPT START marker missing."
        )

    if "--- SCRIPT END ---" not in text:

        warnings.append(
            f"{source_file}: SCRIPT END marker missing."
        )

    # --------------------------------------------------------
    # Identify scene boundaries
    # --------------------------------------------------------

    markers = list(
        SCENE_MARKER_RE.finditer(text)
    )

    if not markers:

        raise ValueError(
            f"No scenes found in {source_file}"
        )

    scenes = []

    all_segments = []

    # --------------------------------------------------------
    # Parse each scene
    # --------------------------------------------------------

    for position, marker in enumerate(markers):

        scene_number = int(marker.group(1))

        chunk_start = marker.start()

        if position + 1 < len(markers):

            chunk_end = markers[position + 1].start()

        else:

            chunk_end = len(text)

        scene_text = text[
            chunk_start:chunk_end
        ]

        line_offset = text.count(
            "\n",
            0,
            chunk_start
        )

        scene, segments = parse_scene(
            scene_text=scene_text,

            episode_number=episode_number,

            scene_number=scene_number,

            source_file=source_file,

            line_offset=line_offset,

            warnings=warnings,
        )

        if scene is None:
            continue

        scenes.append(scene)

        all_segments.extend(segments)

    # --------------------------------------------------------
    # Validate scene availability
    # --------------------------------------------------------

    if not scenes:

        raise ValueError(
            f"No valid scenes could be parsed in {source_file}"
        )

    # --------------------------------------------------------
    # Calculate episode duration
    # --------------------------------------------------------

    known_endpoints = [
        scene.end_seconds
        for scene in scenes
    ]

    known_endpoints.extend(
        segment.end_seconds
        for segment in all_segments
    )

    duration_seconds = max(
        known_endpoints,
        default=0,
    )

    # --------------------------------------------------------
    # Create episode model
    # --------------------------------------------------------

    episode = Episode(
        episode_number=episode_number,

        source_file=source_file,

        logline=logline,

        continuity_notes=continuity_notes,

        scenes=scenes,

        segments=all_segments,

        duration_seconds=duration_seconds,

        raw_text=text,
    )

    return episode, warnings


# ============================================================
# 8. SCREENPLAY FILE PARSER
# ============================================================

def parse_screenplay_file(
    file_path: str | Path,
):
    """
    Read and parse a screenplay TXT file.
    """

    file_path = Path(file_path)

    if not file_path.exists():

        raise FileNotFoundError(
            f"Screenplay file not found: {file_path}"
        )

    if file_path.suffix.lower() != ".txt":

        raise ValueError(
            f"Expected TXT file: {file_path.name}"
        )

    text = decode_screenplay(file_path)

    return parse_screenplay_text(
        text=text,
        source_file=file_path.name,
    )
