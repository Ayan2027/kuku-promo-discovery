import copy
import json

from src.discovery.promo_discovery import (
    create_candidate,
    fallback_evaluation,
)
from src.discovery.ranker import rank_and_validate
from src.discovery.window_generator import generate_candidate_windows
from src.models import Episode, Scene, Segment
from src.quality.output_audit import build_output_audit, hook_offset


def make_episode():
    scene = Scene(
        scene_id="E001_S01",
        episode_number=1,
        scene_heading="INT. ROOM - NIGHT",
        start_timestamp="00:00.00",
        end_timestamp="01:00.00",
        start_seconds=0,
        end_seconds=60,
    )
    segments = [
        Segment(
            segment_id="SEG001",
            episode_number=1,
            scene_id="E001_S01",
            segment_type="DIALOGUE",
            speaker="JULIANA",
            start_timestamp="00:00.00",
            end_timestamp="00:08.00",
            start_seconds=0,
            end_seconds=8,
            content="Why did you betray me?",
            source_file="episode-001.txt",
        ),
        Segment(
            segment_id="SEG002",
            episode_number=1,
            scene_id="E001_S01",
            segment_type="ACTION",
            start_timestamp="00:08.00",
            end_timestamp="00:20.00",
            start_seconds=8,
            end_seconds=20,
            content="Juliana discovers the secret.",
            source_file="episode-001.txt",
        ),
        Segment(
            segment_id="SEG003",
            episode_number=1,
            scene_id="E001_S01",
            segment_type="DIALOGUE",
            speaker="DUKE",
            start_timestamp="00:20.00",
            end_timestamp="00:40.00",
            start_seconds=20,
            end_seconds=40,
            content="You don't know the truth, but you will.",
            source_file="episode-001.txt",
        ),
    ]
    return Episode(
        episode_number=1,
        source_file="episode-001.txt",
        logline="A secret changes everything.",
        continuity_notes="Test continuity.",
        scenes=[scene],
        segments=segments,
        duration_seconds=60,
        raw_text="Test screenplay",
    )


def make_run():
    episode = make_episode()
    windows = generate_candidate_windows(episode, max_windows=5)
    candidates = []
    for window in windows:
        candidate, _ = create_candidate(
            episode,
            window,
            fallback_evaluation(window),
            "DETERMINISTIC_FALLBACK",
        )
        candidates.append(candidate)

    ranked, _, _ = rank_and_validate(
        candidates,
        [episode.model_dump(mode="json")],
        return_dropped=True,
    )
    return ranked, [episode.model_dump(mode="json")]


def test_generated_run_passes_all_hard_requirements():
    ranked, episodes = make_run()

    audit = build_output_audit(ranked, episodes)

    assert audit["failed_checks"] == 0, json.dumps(
        [check for check in audit["checks"] if not check["passed"]],
        indent=2,
    )
    assert audit["status"] == "PASS"


def test_every_generated_hook_is_within_three_seconds():
    ranked, _ = make_run()

    offsets = [hook_offset(candidate) for candidate in ranked]

    assert offsets
    assert all(offset is not None and offset <= 3.0 for offset in offsets)


def test_audit_catches_a_bad_duration():
    ranked, episodes = make_run()
    tampered = copy.deepcopy(ranked)
    tampered[0]["duration_seconds"] = 90

    audit = build_output_audit(tampered, episodes)

    assert audit["status"] == "FAIL"
    assert any(
        check["id"] == "duration_20_60" and not check["passed"]
        for check in audit["checks"]
    )


def test_audit_catches_missing_source_segments():
    ranked, episodes = make_run()
    tampered = copy.deepcopy(ranked)
    tampered[0]["source_segments"] = []

    audit = build_output_audit(tampered, episodes)

    assert audit["status"] == "FAIL"
    failed_ids = {
        check["id"] for check in audit["checks"] if not check["passed"]
    }
    assert "source_segments_present" in failed_ids


def test_audit_catches_missing_hook_and_multiline_reason():
    ranked, episodes = make_run()
    tampered = copy.deepcopy(ranked)
    tampered[0]["opening_hook"] = ""
    tampered[0]["why_it_works"] = "Line one.\nLine two."

    audit = build_output_audit(tampered, episodes)

    failed_ids = {
        check["id"] for check in audit["checks"] if not check["passed"]
    }
    assert "hook_present" in failed_ids
    assert "why_it_works_one_line" in failed_ids


def test_audit_catches_a_missing_episode():
    ranked, episodes = make_run()
    extra = copy.deepcopy(episodes[0])
    extra["episode_number"] = 2

    audit = build_output_audit(ranked, episodes + [extra])

    assert audit["status"] == "FAIL"
    assert any(
        check["id"] == "all_episodes_covered" and not check["passed"]
        for check in audit["checks"]
    )
