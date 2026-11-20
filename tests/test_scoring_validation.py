
from src.scoring.scorer import score_candidate
from src.validation.promo_validator import validate_candidate
from src.discovery.deduplicator import mark_repetitive_candidates


def make_episode():
    return {
        "episode_number": 1,
        "duration_seconds": 120,
        "scenes": [
            {"scene_id": "S1", "start_seconds": 0, "end_seconds": 120}
        ],
        "segments": [
            {
                "segment_id": "SEG1",
                "episode_number": 1,
                "scene_id": "S1",
                "segment_type": "DIALOGUE",
                "speaker": "HERO",
                "emotion_or_direction": "angry",
                "start_timestamp": "00:05.00",
                "end_timestamp": "00:15.00",
                "start_seconds": 5,
                "end_seconds": 15,
                "content": "You betrayed me! Tell me the truth?",
            },
            {
                "segment_id": "SEG2",
                "episode_number": 1,
                "scene_id": "S1",
                "segment_type": "DIALOGUE",
                "speaker": "HEROINE",
                "emotion_or_direction": "crying",
                "start_timestamp": "00:16.00",
                "end_timestamp": "00:35.00",
                "start_seconds": 16,
                "end_seconds": 35,
                "content": "I know your secret, but you will never understand!",
            },
        ],
    }


def make_candidate():
    return {
        "promo_id": "P1",
        "title": "Test promo",
        "episode_number": 1,
        "start_timestamp": "00:05.00",
        "end_timestamp": "00:35.00",
        "start_seconds": 5,
        "end_seconds": 35,
        "duration_seconds": 30,
        "opening_hook": "You betrayed me!",
        "main_dramatic_moment": "The truth is revealed.",
        "ending_cliffhanger_or_payoff": "You will never understand!",
        "dialogue": [],
        "characters": [],
        "emotional_category": "Conflict",
        "promotional_justification": "A dramatic confrontation.",
        "source_segment_ids": ["SEG1", "SEG2"],
        "score_breakdown": {},
        "validation_status": "",
        "validation_issues": [],
        "human_review_label": "",
    }


def test_scores_are_between_zero_and_ten():
    episode = make_episode()
    scores = score_candidate(make_candidate(), episode["segments"])

    for key in (
        "hook_strength",
        "emotional_impact",
        "suspense_curiosity",
        "cliffhanger_payoff",
        "standalone_clarity",
        "promotional_relevance",
    ):
        assert 0 <= scores[key] <= 10

    assert 0 <= scores["final_score"] <= 10


def test_valid_candidate_passes_validation():
    status, issues = validate_candidate(make_candidate(), make_episode())
    assert status == "VALID"
    assert issues == []


def test_too_short_candidate_fails_validation():
    candidate = make_candidate()
    candidate["end_seconds"] = 20
    candidate["end_timestamp"] = "00:20.00"
    candidate["duration_seconds"] = 15

    status, issues = validate_candidate(candidate, make_episode())
    assert status == "INVALID"
    assert any("duration" in issue.lower() for issue in issues)


def test_missing_source_segment_requires_review():
    candidate = make_candidate()
    candidate["source_segment_ids"] = ["UNKNOWN"]

    status, issues = validate_candidate(candidate, make_episode())
    assert status == "NEEDS_REVIEW"
    assert issues


def test_duplicate_candidates_are_flagged_not_deleted():
    first = make_candidate()
    second = make_candidate()
    second["promo_id"] = "P2"
    first["score_breakdown"] = {"final_score": 8}
    second["score_breakdown"] = {"final_score": 6}

    result = mark_repetitive_candidates([first, second])

    assert len(result) == 2
    assert second["human_review_label"] == "Repetitive Promo"


def test_ranking_is_global_score_order():
    from src.discovery.ranker import _global_order

    candidates = [
        {
            "promo_id": "E1_HIGH",
            "episode_number": 1,
            "validation_status": "VALID",
            "human_review_label": "Good Promo",
            "score_breakdown": {"final_score": 9},
            "start_seconds": 10,
        },
        {
            "promo_id": "E1_LOW",
            "episode_number": 1,
            "validation_status": "VALID",
            "human_review_label": "Weak Promo",
            "score_breakdown": {"final_score": 8},
            "start_seconds": 12,
        },
        {
            "promo_id": "E2_HIGH",
            "episode_number": 2,
            "validation_status": "VALID",
            "human_review_label": "Good Promo",
            "score_breakdown": {"final_score": 7},
            "start_seconds": 20,
        },
    ]

    ranked = _global_order(candidates)

    assert [c["promo_id"] for c in ranked] == [
        "E1_HIGH", "E1_LOW", "E2_HIGH"
    ]


def test_duplicate_candidates_are_removed_from_ranked_list():
    from src.discovery.deduplicator import deduplicate_candidates

    first = make_candidate()
    second = make_candidate()
    second["promo_id"] = "P2"
    first["score_breakdown"] = {"final_score": 8}
    second["score_breakdown"] = {"final_score": 6}

    kept, dropped = deduplicate_candidates([first, second])

    assert len(kept) == 1
    assert len(dropped) == 1
    assert dropped[0]["promo_id"] == "P2"
    assert dropped[0]["duplicate_of"] == "P1"

