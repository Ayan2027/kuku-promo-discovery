
import json
from pathlib import Path

from src.config import settings
from src.models import DatasetSummary
from src.ingestion.zip_handler import extract_txt_files
from src.ingestion.screenplay_parser import parse_screenplay_file


def save_json(data, path: Path):
    """
    Safely write JSON using a temporary file.
    """

    path.parent.mkdir(parents=True, exist_ok=True)

    temporary_path = path.with_suffix(
        path.suffix + ".tmp"
    )

    temporary_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    temporary_path.replace(path)


def process_zip(
    zip_path: str | Path,
    input_dir: str | Path | None = None,
    processed_dir: str | Path | None = None,
):
    """
    Process every TXT screenplay in a ZIP archive.

    Returns:
        episodes, summary, warnings
    """

    input_dir = Path(input_dir or settings.INPUT_DIR)
    processed_dir = Path(
        processed_dir or settings.PROCESSED_DIR
    )

    processed_dir.mkdir(parents=True, exist_ok=True)

    # 1. Extract screenplay files.
    files = extract_txt_files(
        zip_path=zip_path,
        output_dir=input_dir,
    )

    episodes = []
    warnings = []
    failed_episodes = []

    # 2. Process each episode independently.
    for file_path in files:

        try:
            episode, episode_warnings = (
                parse_screenplay_file(file_path)
            )

            episodes.append(episode)

            warnings.extend(episode_warnings)

        except Exception as exc:

            error = (
                f"{file_path.name}: "
                f"episode processing failed: {exc}"
            )

            failed_episodes.append(error)
            warnings.append(error)

    # 3. Prevent duplicate episode numbers.
    episode_numbers = [
        episode.episode_number for episode in episodes
    ]

    if len(episode_numbers) != len(set(episode_numbers)):
        raise ValueError(
            "Duplicate episode numbers detected. "
            "Resolve the source files before exporting."
        )

    episodes.sort(
        key=lambda episode: episode.episode_number
    )

    # 4. Calculate actual dataset statistics.
    summary = DatasetSummary(
        total_episodes=len(files),
        processed_episodes=len(episodes),
        failed_episodes=len(failed_episodes),

        total_scenes=sum(
            len(ep.scenes) for ep in episodes
        ),

        total_segments=sum(
            len(ep.segments) for ep in episodes
        ),

        dialogue_segments=sum(
            1
            for ep in episodes
            for seg in ep.segments
            if seg.segment_type == "DIALOGUE"
        ),

        camera_segments=sum(
            1
            for ep in episodes
            for seg in ep.segments
            if seg.segment_type == "CAMERA"
        ),

        action_segments=sum(
            1
            for ep in episodes
            for seg in ep.segments
            if seg.segment_type == "ACTION"
        ),

        sound_segments=sum(
            1
            for ep in episodes
            for seg in ep.segments
            if seg.segment_type == "SOUND FX"
        ),

        missing_timestamps=sum(
            1 for warning in warnings
            if "missing" in warning.lower()
            and "timestamp" in warning.lower()
        ),

        invalid_timestamps=sum(
            1 for warning in warnings
            if "invalid timestamp" in warning.lower()
        ),

        parsing_errors=failed_episodes,
    )

    # 5. Export complete parsed screenplay dataset.
    parsed_data = [
        episode.model_dump(mode="json")
        for episode in episodes
    ]

    save_json(
        parsed_data,
        processed_dir / "parsed_screenplays.json"
    )

    # 6. Export dataset summary.
    save_json(
        summary.model_dump(mode="json"),
        processed_dir / "dataset_summary.json"
    )

    # 7. Export detailed parsing warnings.
    save_json(
        {
            "total_warnings": len(warnings),
            "warnings": warnings,
            "failed_episodes": failed_episodes,
        },
        processed_dir / "parsing_warnings.json"
    )

    return episodes, summary, warnings
