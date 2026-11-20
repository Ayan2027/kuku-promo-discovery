
def _overlap_ratio(a: dict, b: dict) -> float:
    intersection = max(
        0.0,
        min(float(a["end_seconds"]), float(b["end_seconds"]))
        - max(float(a["start_seconds"]), float(b["start_seconds"]))
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


def mark_repetitive_candidates(
    candidates: list[dict],
    overlap_threshold: float = 0.80,
    source_threshold: float = 0.85,
) -> list[dict]:
    ordered = sorted(
        candidates,
        key=lambda c: float(c.get("score_breakdown", {}).get("final_score", 0)),
        reverse=True,
    )
    kept = []

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
            candidate.setdefault("validation_issues", []).append(
                f"Highly overlaps with higher-ranked candidate {duplicate_of}."
            )
        else:
            kept.append(candidate)

    return candidates
