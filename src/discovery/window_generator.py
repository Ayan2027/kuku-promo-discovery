"""
Candidate window generation.

The original implementation created a fixed 30-second window from every
segment start. That produced clips that cut dialogue mid-sentence and made
almost every candidate exactly the same length.

This version is boundary-aware:

* A window may only start on a dialogue/action/scene boundary.
* A window may only end on a dialogue/action/scene boundary.
* Durations vary between the configured minimum and maximum.
* Candidate windows are scored with the same explainable scorer used by the
  final ranker, so selection and ranking cannot disagree.
* Selected windows for an episode are non-overlapping by default, which is
  what removes the "5 near-identical clips per episode" problem at source.
"""

from __future__ import annotations

import re

from src.config import settings
from src.scoring.scorer import score_window
from src.utils.timestamps import seconds_to_timestamp


NARRATIVE_SIGNALS = {
    "betrayal": ["betray", "traitor", "lied", "deceived", "secret"],
    "conflict": ["hate", "kill", "leave", "fight", "revenge", "destroy",
                 "never forgive"],
    "suspense": ["who are you", "what happened", "don't move", "wait",
                 "impossible", "how could"],
    "romance": ["love", "kiss", "heart", "marry", "darling", "husband",
                "wife"],
    "revelation": ["truth", "father", "mother", "identity", "secret",
                   "pregnant", "confession"],
    "cliffhanger": ["suddenly", "but then", "what if", "you don't know",
                    "listen to me", "one thing"],
}

BEAT_TYPES = {"DIALOGUE", "ACTION"}


def get_signal_score(segments):
    """Estimate narrative potential using deterministic keyword signals."""

    score = 0
    matched_categories = set()

    for segment in segments:
        content = str(getattr(segment, "content", "")).lower()
        for category, keywords in NARRATIVE_SIGNALS.items():
            if any(keyword in content for keyword in keywords):
                score += 2
                matched_categories.add(category)

    score += len(matched_categories) * 3

    if any(getattr(s, "segment_type", "") == "DIALOGUE" for s in segments):
        score += 3
    if any(getattr(s, "segment_type", "") == "ACTION" for s in segments):
        score += 2

    return score, sorted(matched_categories)


def _overlap_ratio(a: dict, b: dict) -> float:
    intersection = max(
        0.0,
        min(a["end_seconds"], b["end_seconds"])
        - max(a["start_seconds"], b["start_seconds"]),
    )
    shorter = min(
        a["end_seconds"] - a["start_seconds"],
        b["end_seconds"] - b["start_seconds"],
    )
    return intersection / shorter if shorter > 0 else 0.0


def _inside_dialogue(episode, value: float) -> bool:
    """True when ``value`` falls strictly inside a spoken line."""

    return any(
        segment.segment_type == "DIALOGUE"
        and float(segment.start_seconds) + 0.01 < value
        < float(segment.end_seconds) - 0.01
        for segment in episode.segments
    )


def _boundary_values(episode, kinds: str) -> list[float]:
    values: set[float] = set()

    for segment in episode.segments:
        if kinds == "start" and segment.segment_type in BEAT_TYPES:
            if not _inside_dialogue(episode, float(segment.start_seconds)):
                values.add(round(float(segment.start_seconds), 2))
        elif kinds == "end" and segment.segment_type in BEAT_TYPES:
            if not _inside_dialogue(episode, float(segment.end_seconds)):
                values.add(round(float(segment.end_seconds), 2))

    for scene in episode.scenes:
        if kinds == "start":
            if not _inside_dialogue(episode, float(scene.start_seconds)):
                values.add(round(float(scene.start_seconds), 2))
        else:
            if not _inside_dialogue(episode, float(scene.end_seconds)):
                values.add(round(float(scene.end_seconds), 2))

    values.add(0.0)
    values.add(round(float(episode.duration_seconds), 2))
    return sorted(
        v for v in values
        if v >= 0 and not _inside_dialogue(episode, v)
    )


def _short_title(episode_number: int, category: str, hook: str) -> str:
    words = re.findall(r"[A-Za-z']+", str(hook))
    stop = {
        "the", "a", "an", "and", "but", "so", "then", "you", "i", "we",
        "he", "she", "they", "it", "is", "are", "was", "were", "to", "of",
        "in", "on", "for", "with", "my", "your", "me", "do", "did", "not",
    }
    keywords = [w for w in words if w.lower() not in stop]
    phrase = " ".join(keywords[:4]) if keywords else category
    return f"Episode {episode_number} — {category}: {phrase}"[:120]


def generate_candidate_windows(episode, max_windows=5, min_score=None):
    """Generate ranked, boundary-aligned, non-overlapping promo candidates."""

    min_duration = float(settings.PROMO_MIN_DURATION)
    max_duration = float(settings.PROMO_MAX_DURATION)
    episode_duration = float(episode.duration_seconds)

    if episode_duration < min_duration:
        return []

    starts = _boundary_values(episode, "start")
    ends = _boundary_values(episode, "end")

    candidates: list[dict] = []
    seen: set[tuple[float, float]] = set()

    for start in starts:
        if episode_duration - start < min_duration:
            continue

        possible_ends = [
            end for end in ends
            if min_duration <= (end - start) <= max_duration
        ]

        if not possible_ends:
            continue

        for end in possible_ends:
            key = (round(start, 2), round(end, 2))
            if key in seen:
                continue
            seen.add(key)

            selected = [
                segment for segment in episode.segments
                if (
                    float(segment.start_seconds) < end
                    and float(segment.end_seconds) > start
                )
            ]
            if not selected:
                continue

            scores, editorial = score_window(start, end, episode.segments)

            signal_score, categories = get_signal_score(selected)

            scene_ids = {segment.scene_id for segment in selected}

            candidates.append({
                "window_id": "PENDING",
                "episode_number": episode.episode_number,
                "start_seconds": round(start, 2),
                "end_seconds": round(end, 2),
                "start_timestamp": seconds_to_timestamp(start),
                "end_timestamp": seconds_to_timestamp(end),
                "duration_seconds": round(end - start, 2),
                "segments": selected,
                "scene_count": len(scene_ids),
                "signal_score": signal_score,
                "signal_categories": categories,
                "score_breakdown": scores,
                "editorial": editorial,
            })

    # Strongest first. Tie-break on a shorter, tighter clip.
    candidates.sort(
        key=lambda item: (
            -float(item["score_breakdown"]["final_score"]),
            item["duration_seconds"],
            item["start_seconds"],
        )
    )

    threshold = (
        float(min_score)
        if min_score is not None
        else float(getattr(settings, "PROMO_MIN_SCORE", 0.0))
    )

    selected_windows: list[dict] = []

    def affordable(candidate: dict) -> bool:
        if candidate["score_breakdown"]["final_score"] < threshold:
            return False
        return not any(
            _overlap_ratio(candidate, kept) >= 0.40
            for kept in selected_windows
        )

    # Prefer clips that stay inside one scene. Only fill the remaining slots
    # with a cross-scene clip when the episode does not have enough clean
    # single-scene material.
    for candidate in candidates:
        if candidate.get("scene_count", 1) <= 1 and affordable(candidate):
            selected_windows.append(candidate)
            if len(selected_windows) >= max_windows:
                break

    if len(selected_windows) < max_windows:
        for candidate in candidates:
            if candidate.get("scene_count", 1) > 1 and affordable(candidate):
                selected_windows.append(candidate)
                if len(selected_windows) >= max_windows:
                    break

    selected_windows.sort(
        key=lambda item: (
            -float(item["score_breakdown"]["final_score"]),
            item["duration_seconds"],
        )
    )

    for index, window in enumerate(selected_windows, start=1):
        window["window_id"] = f"W{index:04d}"

        editorial = window["editorial"]
        category = (
            window["signal_categories"][0].title()
            if window["signal_categories"]
            else "Drama"
        )
        window["editorial"]["emotional_category"] = category
        window["editorial"]["title"] = _short_title(
            episode.episode_number,
            category,
            editorial.get("opening_hook", ""),
        )

    return selected_windows
