"""Candidate de-duplication.

Windows that overlap heavily are not separate editorial ideas. The original
code only labelled them "Repetitive Promo" and still exported them in the
ranked list. This module removes them from the ranked list and returns them
as a separate rejection list, so the quality-check section can report them
honestly.
"""

from __future__ import annotations


def _overlap_ratio(a: dict, b: dict) -> float:
    intersection = max(
        0.0,
        min(float(a["end_seconds"]), float(b["end_seconds"]))
        - max(float(a["start_seconds"]), float(b["start_seconds"])),
    )
    shorter = min(
        float(a["end_seconds"]) - float(a["start_seconds"]),
        float(b["end_seconds"]) - float(b["start_seconds"]),
    )
    return intersection / shorter if shorter > 0 else 0.0


def _source_similarity(a: dict, b: dict) -> float:
    left = set(a.get("source_segment_ids") or [])
    right = set(b.get("source_segment_ids") or [])
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def _score(candidate: dict) -> float:
    return float(candidate.get("score_breakdown", {}).get("final_score", 0))


def deduplicate_candidates(
    candidates: list[dict],
    overlap_threshold: float = 0.50,
    source_threshold: float = 0.70,
) -> tuple[list[dict], list[dict]]:
    """Return ``(kept, dropped)`` ordered by descending score."""

    ordered = sorted(
        candidates,
        key=lambda c: (-_score(c), float(c.get("start_seconds", 0))),
    )
    kept: list[dict] = []
    dropped: list[dict] = []

    for candidate in ordered:
        duplicate_of = None
        for stronger in kept:
            if candidate.get("episode_number") != stronger.get("episode_number"):
                continue
            same_window = (
                _overlap_ratio(candidate, stronger) >= overlap_threshold
                or _source_similarity(candidate, stronger) >= source_threshold
            )
            if same_window:
                duplicate_of = stronger.get("promo_id")
                break

        if duplicate_of:
            candidate["human_review_label"] = "Repetitive Promo"
            candidate["duplicate_of"] = duplicate_of
            candidate["rejection_reason"] = (
                f"Overlaps a stronger candidate ({duplicate_of}) by more than "
                f"{overlap_threshold:.0%} of the shorter clip."
            )
            candidate.setdefault("validation_issues", []).append(
                candidate["rejection_reason"]
            )
            dropped.append(candidate)
        else:
            kept.append(candidate)

    return kept, dropped


def mark_repetitive_candidates(
    candidates: list[dict],
    overlap_threshold: float = 0.80,
    source_threshold: float = 0.85,
    drop: bool = False,
) -> list[dict]:
    """Backwards-compatible helper used by tests and older callers."""

    kept, dropped = deduplicate_candidates(
        candidates,
        overlap_threshold=overlap_threshold,
        source_threshold=source_threshold,
    )
    if drop:
        return kept
    return kept + dropped
