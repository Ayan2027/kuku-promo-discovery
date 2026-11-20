
from collections import defaultdict

from src.scoring.scorer import score_candidate
from src.validation.promo_validator import validate_candidate
from src.discovery.deduplicator import mark_repetitive_candidates


def _to_dict(item):
    if hasattr(item, "model_dump"):
        return item.model_dump()
    return dict(item)


def _score(candidate):
    return float(
        candidate.get("score_breakdown", {}).get("final_score", 0)
    )


def _diversified_order(candidates):
    """
    Round-robin ranking:
    1. Best distinct candidate from each episode.
    2. Further distinct candidates from each episode.
    3. Repetitive candidates.
    4. Technically invalid candidates.
    """
    valid = [
        c for c in candidates
        if c.get("validation_status") == "VALID"
    ]
    needs_review = [
        c for c in candidates
        if c.get("validation_status") == "NEEDS_REVIEW"
    ]
    invalid = [
        c for c in candidates
        if c.get("validation_status") == "INVALID"
    ]

    def order_group(group):
        by_episode = defaultdict(list)

        for candidate in group:
            by_episode[candidate.get("episode_number")].append(candidate)

        for episode_candidates in by_episode.values():
            episode_candidates.sort(
                key=lambda c: (
                    c.get("human_review_label") == "Repetitive Promo",
                    -_score(c),
                    c.get("start_seconds", 0),
                )
            )

        ordered = []
        max_items = max(
            (len(items) for items in by_episode.values()),
            default=0,
        )

        # Take one candidate per episode in each round.
        for round_index in range(max_items):
            round_candidates = [
                items[round_index]
                for items in by_episode.values()
                if round_index < len(items)
            ]
            round_candidates.sort(
                key=lambda c: (
                    c.get("human_review_label") == "Repetitive Promo",
                    -_score(c),
                )
            )
            ordered.extend(round_candidates)

        return ordered

    return (
        order_group(valid)
        + order_group(needs_review)
        + order_group(invalid)
    )


def rank_and_validate(
    candidates,
    episodes,
    min_duration=20.0,
    max_duration=60.0,
):
    episode_map = {
        int(ep["episode_number"]): ep
        for ep in (_to_dict(e) for e in episodes)
    }

    results = []

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
            candidate["human_review_label"] = "Missing Context"
            results.append(candidate)
            continue

        candidate["score_breakdown"] = score_candidate(
            candidate,
            episode.get("segments", []),
        )

        status, issues = validate_candidate(
            candidate,
            episode,
            min_duration=min_duration,
            max_duration=max_duration,
        )

        candidate["validation_status"] = status
        candidate["validation_issues"] = issues

        if status == "INVALID":
            candidate["human_review_label"] = "Incorrect Timestamp"
        elif status == "NEEDS_REVIEW":
            candidate["human_review_label"] = "Missing Context"
        elif candidate["score_breakdown"]["final_score"] >= 7:
            candidate["human_review_label"] = "Good Promo"
        else:
            candidate["human_review_label"] = "Weak Promo"

        results.append(candidate)

    # Flag similar windows without deleting them.
    mark_repetitive_candidates(results)

    # Rank distinct candidates across episodes before repeated ones.
    results = _diversified_order(results)

    for index, candidate in enumerate(results, start=1):
        candidate["rank"] = index

    return results
