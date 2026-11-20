"""Validation, quality labelling, de-duplication and global ranking."""

from __future__ import annotations

from src.config import settings
from src.discovery.deduplicator import deduplicate_candidates
from src.scoring.scorer import score_candidate
from src.validation.promo_validator import validate_candidate


def _to_dict(item):
    if hasattr(item, "model_dump"):
        return item.model_dump()
    return dict(item)


def _score(candidate):
    return float(
        (candidate.get("score_breakdown") or {}).get("final_score", 0)
    )


def _scores_valid(scores) -> bool:
    if not isinstance(scores, dict):
        return False

    required = (
        "hook_strength",
        "emotional_impact",
        "suspense_curiosity",
        "cliffhanger_payoff",
        "standalone_clarity",
        "promotional_relevance",
        "final_score",
    )
    try:
        return all(0 <= float(scores[key]) <= 10 for key in required)
    except (KeyError, TypeError, ValueError):
        return False


def _quality_label(score: float) -> str:
    good = float(getattr(settings, "PROMO_GOOD_SCORE", 6.5))
    weak = float(getattr(settings, "PROMO_WEAK_SCORE", 4.5))
    if score >= good:
        return "Good Promo"
    if score >= weak:
        return "Weak Promo"
    return "Bad Promo"


def _rank_reason(candidate: dict, rank: int) -> str:
    score = _score(candidate)
    label = candidate.get("human_review_label", "Unlabelled")
    hook = candidate.get("hook_type", "unknown")
    cliff = candidate.get("cliffhanger_type", "unknown")
    source = candidate.get("score_source", "heuristic")
    return (
        f"Rank {rank}: {score:.2f}/10 ({label}), scored by {source}. "
        f"Opens with a {hook} hook and ends on {cliff} tension."
    )


def _global_order(candidates):
    """Global quality order, not per-episode round-robin.

    The brief asks for ranked promos and a clear "post these first" answer.
    A reviewer should be able to trust that rank 10 scores at least as well
    as rank 11, so validity group then score are the primary keys.
    """

    def rank_penalty(candidate):
        # Missing/invalid context must never outrank a valid clip, but a
        # "needs review" candidate still competes on quality and keeps its
        # score-ordered position.
        return 100 if candidate.get("validation_status") == "INVALID" else 0

    return sorted(
        candidates,
        key=lambda c: (
            rank_penalty(c),
            -_score(c),
            int(c.get("episode_number", 0)),
            float(c.get("start_seconds", 0)),
        ),
    )


def rank_and_validate(
    candidates,
    episodes,
    min_duration=20.0,
    max_duration=60.0,
    drop_repetitive=True,
    return_dropped=False,
):
    episode_map = {
        int(ep["episode_number"]): ep
        for ep in (_to_dict(e) for e in episodes)
    }

    results = []
    scoring_counts = {"GEMINI": 0, "HEURISTIC": 0}

    for item in candidates:
        candidate = _to_dict(item)
        number = int(candidate["episode_number"])
        episode = episode_map.get(number)

        if episode is None:
            candidate["validation_status"] = "INVALID"
            candidate["validation_issues"] = [
                "Source episode was not found."
            ]
            candidate["score_breakdown"] = {
                "hook_strength": 0,
                "emotional_impact": 0,
                "suspense_curiosity": 0,
                "cliffhanger_payoff": 0,
                "standalone_clarity": 0,
                "promotional_relevance": 0,
                "final_score": 0,
            }
            candidate["human_review_label"] = "Invalid"
            candidate["score_source"] = "none"
            results.append(candidate)
            continue

        existing_scores = candidate.get("score_breakdown")
        use_ai_scores = (
            candidate.get("analysis_mode") == "GEMINI"
            and _scores_valid(existing_scores)
        )

        if use_ai_scores:
            candidate["score_breakdown"] = {
                key: float(existing_scores[key])
                for key in (
                    "hook_strength",
                    "emotional_impact",
                    "suspense_curiosity",
                    "cliffhanger_payoff",
                    "standalone_clarity",
                    "promotional_relevance",
                    "final_score",
                )
            }
            candidate["score_source"] = "GEMINI"
            scoring_counts["GEMINI"] += 1
        else:
            candidate["score_breakdown"] = score_candidate(
                candidate,
                episode.get("segments", []),
            )
            candidate["score_source"] = "heuristic"
            scoring_counts["HEURISTIC"] += 1

        status, issues = validate_candidate(
            candidate,
            episode,
            min_duration=min_duration,
            max_duration=max_duration,
        )

        candidate["validation_status"] = status
        candidate["validation_issues"] = issues

        if status == "INVALID":
            candidate["human_review_label"] = "Invalid"
        elif status == "NEEDS_REVIEW":
            candidate["human_review_label"] = "Needs Review"
        else:
            candidate["human_review_label"] = _quality_label(
                _score(candidate)
            )

        results.append(candidate)

    dropped = []
    if drop_repetitive:
        results, dropped = deduplicate_candidates(results)

    results = _global_order(results)

    for index, candidate in enumerate(results, start=1):
        candidate["rank"] = index
        candidate["rank_reason"] = _rank_reason(candidate, index)

    for candidate in dropped:
        candidate["rank"] = None
        candidate["rank_reason"] = "Not ranked: duplicate of a stronger clip."

    if return_dropped:
        return results, dropped, scoring_counts

    return results
