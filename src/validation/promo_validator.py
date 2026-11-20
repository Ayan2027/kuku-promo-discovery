
from typing import Any


def validate_candidate(
    candidate: dict,
    episode: dict,
    min_duration: float = 20.0,
    max_duration: float = 60.0,
) -> tuple[str, list[str]]:
    issues = []

    try:
        start = float(candidate["start_seconds"])
        end = float(candidate["end_seconds"])
        duration = float(candidate["duration_seconds"])
    except (KeyError, TypeError, ValueError):
        return "INVALID", ["Missing or invalid numeric timestamps."]

    episode_number = candidate.get("episode_number")
    if episode_number != episode.get("episode_number"):
        issues.append("Candidate episode number does not match source episode.")

    if start < 0:
        issues.append("Clip starts before episode start.")
    if end <= start:
        issues.append("Clip end must be after clip start.")
    if not min_duration <= duration <= max_duration:
        issues.append(
            f"Clip duration {duration:.2f}s is outside "
            f"{min_duration:.0f}-{max_duration:.0f}s."
        )
    if abs((end - start) - duration) > 0.1:
        issues.append("Stored duration does not match start and end timestamps.")

    episode_duration = float(episode.get("duration_seconds", 0))
    if episode_duration and end > episode_duration + 0.01:
        issues.append("Clip ends after the episode duration.")

    segments = episode.get("segments", [])
    segment_map = {s.get("segment_id"): s for s in segments}
    source_ids = candidate.get("source_segment_ids") or []

    if not source_ids:
        issues.append("No source segment IDs attached to candidate.")
    else:
        missing = [sid for sid in source_ids if sid not in segment_map]
        if missing:
            issues.append(f"Source segment IDs not found: {missing[:5]}")

        wrong_episode = [
            sid for sid in source_ids
            if sid in segment_map
            and segment_map[sid].get("episode_number") != episode_number
        ]
        if wrong_episode:
            issues.append("Candidate references segments from another episode.")

        if not missing:
            non_overlapping = [
                sid for sid in source_ids
                if float(segment_map[sid].get("start_seconds", 0)) >= end
                or float(segment_map[sid].get("end_seconds", 0)) <= start
            ]
            if non_overlapping:
                issues.append("Some referenced segments do not overlap the clip.")

    # Compare display timestamps with seconds, without changing source data.
    from src.utils.timestamps import parse_timestamp

    for field, seconds_field in (
        ("start_timestamp", "start_seconds"),
        ("end_timestamp", "end_seconds"),
    ):
        try:
            parsed = parse_timestamp(str(candidate[field]))
            if abs(parsed - float(candidate[seconds_field])) > 0.1:
                issues.append(f"{field} does not match {seconds_field}.")
        except (KeyError, TypeError, ValueError):
            issues.append(f"Invalid or missing {field}.")

    # Warn if any selected source segment extends beyond its scene.
    scene_map = {s.get("scene_id"): s for s in episode.get("scenes", [])}
    for sid in source_ids:
        segment = segment_map.get(sid)
        if not segment:
            continue
        scene = scene_map.get(segment.get("scene_id"))
        if scene and float(segment.get("end_seconds", 0)) > (
            float(scene.get("end_seconds", 0)) + 0.01
        ):
            issues.append(
                f"Source segment {sid} extends beyond its scene boundary."
            )

    if any(
        "outside" in issue.lower()
        or "before episode" in issue.lower()
        or "must be after" in issue.lower()
        or "timestamp" in issue.lower()
        or "duration" in issue.lower()
        for issue in issues
    ):
        return "INVALID", issues

    if issues:
        return "NEEDS_REVIEW", issues

    return "VALID", []
