
import re

from src.config import settings


NARRATIVE_SIGNALS = {
    "betrayal": [
        "betray", "traitor", "lied", "deceived", "secret"
    ],
    "conflict": [
        "hate", "kill", "leave", "fight", "revenge",
        "destroy", "never forgive"
    ],
    "suspense": [
        "who are you", "what happened", "don't move",
        "wait", "impossible", "how could"
    ],
    "romance": [
        "love", "kiss", "heart", "marry", "darling",
        "husband", "wife"
    ],
    "revelation": [
        "truth", "father", "mother", "identity",
        "secret", "pregnant", "confession"
    ],
    "cliffhanger": [
        "suddenly", "but then", "what if", "you don't know",
        "listen to me", "one thing"
    ],
}


def get_signal_score(segments):
    """
    Estimate narrative potential using configurable keywords.

    This is a heuristic, not an AI-generated score.
    """

    score = 0
    matched_categories = set()

    for segment in segments:

        content = segment.content.lower()

        for category, keywords in NARRATIVE_SIGNALS.items():

            if any(keyword in content for keyword in keywords):

                score += 2
                matched_categories.add(category)

    # Multiple different narrative signals are more useful
    # than repeated occurrences of the same signal.
    score += len(matched_categories) * 3

    # Give dialogue and action additional contextual value.
    if any(s.segment_type == "DIALOGUE" for s in segments):
        score += 3

    if any(s.segment_type == "ACTION" for s in segments):
        score += 2

    return score, sorted(matched_categories)


def generate_candidate_windows(episode, max_windows=5):
    """
    Generate ranked 20-60 second candidate windows.

    Uses actual segment boundaries and preserves
    all overlapping source segments.
    """

    min_duration = settings.PROMO_MIN_DURATION
    max_duration = settings.PROMO_MAX_DURATION

    episode_duration = episode.duration_seconds

    if episode_duration < min_duration:
        return []

    candidates = []
    seen_intervals = set()

    # Candidate starts come from original segment starts.
    starts = sorted({
        segment.start_seconds
        for segment in episode.segments
    })

    for start in starts:

        available_duration = episode_duration - start

        if available_duration < min_duration:
            continue

        # Prefer a 30-second clip.
        duration = min(30.0, max_duration, available_duration)

        if duration < min_duration:
            duration = min(max_duration, available_duration)

        end = start + duration

        interval_key = (
            round(start, 2),
            round(end, 2)
        )

        if interval_key in seen_intervals:
            continue

        seen_intervals.add(interval_key)

        overlapping_segments = [
            segment
            for segment in episode.segments
            if (
                segment.start_seconds < end
                and segment.end_seconds > start
            )
        ]

        if not overlapping_segments:
            continue

        signal_score, categories = get_signal_score(
            overlapping_segments
        )

        # Skip windows with no meaningful narrative evidence.
        if signal_score <= 0:
            continue

        candidates.append({
            "window_id": (
                f"E{episode.episode_number:03d}_"
                f"W{len(candidates) + 1:04d}"
            ),

            "episode_number": episode.episode_number,

            "start_seconds": round(start, 2),

            "end_seconds": round(end, 2),

            "start_timestamp": overlapping_segments[0].start_timestamp
            if overlapping_segments[0].start_seconds == start
            else None,

            "duration_seconds": round(end - start, 2),

            "segments": overlapping_segments,

            "signal_score": signal_score,

            "signal_categories": categories,
        })

    # Correct timestamp formatting from actual seconds.
    from src.utils.timestamps import seconds_to_timestamp

    for candidate in candidates:

        candidate["start_timestamp"] = seconds_to_timestamp(
            candidate["start_seconds"]
        )

        candidate["end_timestamp"] = seconds_to_timestamp(
            candidate["end_seconds"]
        )

    candidates.sort(
        key=lambda item: (
            -item["signal_score"],
            item["start_seconds"]
        )
    )

    # Keep only the most promising windows.
    selected = candidates[:max_windows]

    # Reassign IDs after ranking.
    for index, candidate in enumerate(selected, start=1):

        candidate["window_id"] = (
            f"E{episode.episode_number:03d}_W{index:04d}"
        )

    return selected
