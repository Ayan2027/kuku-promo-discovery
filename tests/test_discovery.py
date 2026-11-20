
from src.models import Episode, Scene, Segment

from src.discovery.window_generator import (
    generate_candidate_windows,
    get_signal_score,
)

from src.discovery.promo_discovery import (
    _source_segments,
    fallback_evaluation,
    create_candidate,
)


def make_test_episode():

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
            end_timestamp="00:30.00",
            start_seconds=20,
            end_seconds=30,
            content="You don't know the truth.",
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


def test_signal_detection():

    episode = make_test_episode()

    score, categories = get_signal_score(
        episode.segments
    )

    assert score > 0
    assert len(categories) > 0


def test_window_duration():

    episode = make_test_episode()

    windows = generate_candidate_windows(
        episode,
        max_windows=5,
    )

    assert len(windows) > 0

    for window in windows:

        assert 20 <= window["duration_seconds"] <= 60

        assert window["end_seconds"] <= 60


def test_window_has_source_segments():

    episode = make_test_episode()

    windows = generate_candidate_windows(episode)

    for window in windows:

        assert len(window["segments"]) > 0

        assert all(
            segment.segment_id
            for segment in window["segments"]
        )


def test_fallback_evaluation():

    episode = make_test_episode()

    windows = generate_candidate_windows(episode)

    result = fallback_evaluation(windows[0])

    assert result["analysis_mode"] == (
        "DETERMINISTIC_FALLBACK"
    )

    assert result["dialogue"]


def test_windows_end_on_a_source_boundary():
    episode = make_test_episode()
    windows = generate_candidate_windows(episode)

    boundaries = {
        round(float(segment.end_seconds), 2)
        for segment in episode.segments
    }
    boundaries |= {
        round(float(scene.end_seconds), 2) for scene in episode.scenes
    }

    for window in windows:
        assert round(window["end_seconds"], 2) in boundaries


def make_camera_first_episode():

    scene = Scene(
        scene_id="E002_S01",
        episode_number=2,
        scene_heading="INT. HALL - DAY",
        start_timestamp="00:00.00",
        end_timestamp="00:55.00",
        start_seconds=0,
        end_seconds=55,
    )

    segments = [
        Segment(
            segment_id="C1",
            episode_number=2,
            scene_id="E002_S01",
            segment_type="CAMERA",
            start_timestamp="00:00.00",
            end_timestamp="00:06.00",
            start_seconds=0,
            end_seconds=6,
            content="The camera pans across the hall.",
            source_file="episode-002.txt",
        ),
        Segment(
            segment_id="D1",
            episode_number=2,
            scene_id="E002_S01",
            segment_type="DIALOGUE",
            speaker="HERO",
            start_timestamp="00:06.00",
            end_timestamp="00:20.00",
            start_seconds=6,
            end_seconds=20,
            content="You betrayed me!",
            source_file="episode-002.txt",
        ),
        Segment(
            segment_id="A1",
            episode_number=2,
            scene_id="E002_S01",
            segment_type="ACTION",
            start_timestamp="00:20.00",
            end_timestamp="00:40.00",
            start_seconds=20,
            end_seconds=40,
            content="He slaps her.",
            source_file="episode-002.txt",
        ),
        Segment(
            segment_id="D2",
            episode_number=2,
            scene_id="E002_S01",
            segment_type="DIALOGUE",
            speaker="HEROINE",
            start_timestamp="00:40.00",
            end_timestamp="00:55.00",
            start_seconds=40,
            end_seconds=55,
            content="I will never forgive you...",
            source_file="episode-002.txt",
        ),
    ]

    return Episode(
        episode_number=2,
        source_file="episode-002.txt",
        logline="A public slap.",
        continuity_notes="Test continuity.",
        scenes=[scene],
        segments=segments,
        duration_seconds=55,
        raw_text="Test screenplay two",
    )


def test_windows_open_on_a_beat_within_three_seconds():

    episode = make_camera_first_episode()

    windows = generate_candidate_windows(episode, max_windows=5)

    assert windows
    for window in windows:
        beats = [
            float(segment.start_seconds)
            for segment in window["segments"]
            if segment.segment_type in ("DIALOGUE", "ACTION")
        ]
        assert beats
        assert min(beats) <= window["start_seconds"] + 3.0
        # The scene opens with a six-second camera beat; no candidate may
        # start there and leave the viewer waiting for a hook.
        assert window["start_seconds"] > 0


def test_source_segments_are_clipped_to_the_window():

    episode = make_test_episode()
    segments = episode.segments

    clipped = _source_segments(segments, start=2.0, end=15.0)

    assert clipped
    assert clipped[0].start_seconds == 2.0
    assert clipped[-1].end_seconds == 15.0
    for segment in clipped:
        assert segment.start_seconds >= 2.0
        assert segment.end_seconds <= 15.0
        assert segment.end_seconds > segment.start_seconds


def test_windows_do_not_include_dead_air():
    episode = make_camera_first_episode()
    # Scene metadata says 55s, but the final beat ends at 55s in this test.
    # Shorten the last beat so the scene has a 10-second dead tail.
    episode.segments[-1].end_seconds = 45
    episode.segments[-1].end_timestamp = "00:45.00"

    windows = generate_candidate_windows(episode, max_windows=5)

    assert windows
    for window in windows:
        assert window["end_seconds"] <= 45.0


def test_candidate_segment_timeline_covers_clip_bounds():

    episode = make_test_episode()
    window = generate_candidate_windows(episode)[0]
    candidate, _ = create_candidate(
        episode,
        window,
        fallback_evaluation(window),
        "DETERMINISTIC_FALLBACK",
    )

    # Segments are ordered by start time; their union covers the clip. A
    # shorter overlapping segment can be listed after a longer one, so the
    # bounds are checked across the whole timeline rather than its last row.
    assert candidate.source_segments[0].start_seconds == (
        candidate.start_seconds
    )
    assert max(
        segment.end_seconds for segment in candidate.source_segments
    ) == candidate.end_seconds


def test_promo_id_has_a_single_episode_prefix():
    episode = make_test_episode()
    window = generate_candidate_windows(episode)[0]
    candidate, _ = create_candidate(
        episode,
        window,
        fallback_evaluation(window),
        "DETERMINISTIC_FALLBACK",
    )

    assert candidate.promo_id.startswith("E001_W")
    assert not candidate.promo_id.startswith("E001_E001")


def test_candidate_embeds_ordered_source_segments():
    episode = make_test_episode()
    window = generate_candidate_windows(episode)[0]
    candidate, _ = create_candidate(
        episode,
        window,
        fallback_evaluation(window),
        "DETERMINISTIC_FALLBACK",
    )

    starts = [segment.start_seconds for segment in candidate.source_segments]
    assert starts == sorted(starts)
    assert candidate.source_segments


def test_candidate_uses_python_timestamps():

    episode = make_test_episode()

    windows = generate_candidate_windows(episode)

    window = windows[0]

    evaluation = fallback_evaluation(window)

    candidate, metadata = create_candidate(
        episode,
        window,
        evaluation,
        "DETERMINISTIC_FALLBACK",
    )

    assert candidate.start_seconds == window["start_seconds"]

    assert candidate.end_seconds == window["end_seconds"]

    assert candidate.source_segment_ids

    assert metadata["analysis_mode"] == (
        "DETERMINISTIC_FALLBACK"
    )
