
import json
import re
import hashlib
from pathlib import Path

from src.config import settings
from src.models import PromoCandidate

from src.ai.gemini_provider import GeminiProvider
from src.ai.prompts import build_episode_prompt

from src.discovery.window_generator import (
    generate_candidate_windows,
)


def save_json(data, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    temp = path.with_suffix(path.suffix + ".tmp")

    temp.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    temp.replace(path)


def safe_dialogue(segments):
    """
    Return exact dialogue content from source segments.
    """

    return [
        segment.content
        for segment in segments
        if segment.segment_type == "DIALOGUE"
    ]


def extract_characters(segments):
    """
    Extract speaker names from dialogue segments.
    """

    return sorted({
        segment.speaker
        for segment in segments
        if segment.speaker
        and segment.segment_type == "DIALOGUE"
    })


def fallback_evaluation(window):
    """
    Deterministic evaluation without external APIs.

    These are heuristic results, not LLM judgments.
    """

    segments = window["segments"]

    dialogue = safe_dialogue(segments)

    characters = extract_characters(segments)

    content = " ".join(
        segment.content for segment in segments
    )

    categories = window["signal_categories"]

    category = (
        categories[0].title()
        if categories
        else "Drama"
    )

    first_dialogue = (
        dialogue[0]
        if dialogue
        else content[:180]
    )

    last_dialogue = (
        dialogue[-1]
        if dialogue
        else content[-180:]
    )

    title = (
        f"Episode {window['episode_number']} - {category}"
    )

    return {
        "window_id": window["window_id"],
        "is_good_promo": True,
        "title": title,
        "opening_hook": first_dialogue,
        "main_dramatic_moment": (
            "Narrative signals detected: "
            + ", ".join(categories)
        ),
        "ending_cliffhanger_or_payoff": last_dialogue,
        "emotional_category": category,
        "promotional_justification": (
            "Heuristic candidate selected because the "
            "screenplay window contains narrative signals. "
            "Human review is required."
        ),
        "dialogue": dialogue,
        "characters": characters,
        "hook_strength": 0,
        "emotional_impact": 0,
        "suspense_curiosity": 0,
        "cliffhanger_payoff": 0,
        "standalone_clarity": 0,
        "promotional_relevance": 0,
        "analysis_mode": "DETERMINISTIC_FALLBACK",
    }


def create_candidate(
    episode,
    window,
    evaluation,
    analysis_mode,
):
    """
    Construct a PromoCandidate using Python-owned timestamps.

    AI-supplied timestamps are never accepted.
    """

    segments = window["segments"]

    source_ids = [
        segment.segment_id
        for segment in segments
    ]

    dialogue = safe_dialogue(segments)

    characters = extract_characters(segments)

    # Use source evidence instead of trusting generated dialogue.
    # AI can explain, but cannot introduce unsupported dialogue.
    title = str(
        evaluation.get("title", "Untitled Promo")
    )[:150]

    candidate = PromoCandidate(
        promo_id=(
            f"E{episode.episode_number:03d}_"
            f"{window['window_id']}"
        ),

        title=title,

        episode_number=episode.episode_number,

        start_timestamp=window["start_timestamp"],

        end_timestamp=window["end_timestamp"],

        start_seconds=window["start_seconds"],

        end_seconds=window["end_seconds"],

        duration_seconds=window["duration_seconds"],

        opening_hook=str(
            evaluation.get("opening_hook", "")
        ),

        main_dramatic_moment=str(
            evaluation.get("main_dramatic_moment", "")
        ),

        ending_cliffhanger_or_payoff=str(
            evaluation.get(
                "ending_cliffhanger_or_payoff", ""
            )
        ),

        dialogue=dialogue,

        characters=characters,

        emotional_category=str(
            evaluation.get("emotional_category", "Drama")
        ),

        promotional_justification=str(
            evaluation.get(
                "promotional_justification", ""
            )
        ),

        source_segment_ids=source_ids,

        validation_status="PENDING",

        human_review_label=(
            "NEEDS_HUMAN_REVIEW"
            if analysis_mode == "DETERMINISTIC_FALLBACK"
            else None
        ),
    )

    # Store analysis provenance separately.
    return candidate, {
        "analysis_mode": analysis_mode,
        "ai_window_id": window["window_id"],
        "heuristic_signal_score": window["signal_score"],
        "heuristic_categories": window["signal_categories"],
        "ai_evaluation": evaluation,
    }


def discover_episode_promos(
    episode,
    provider,
    cache_dir=None,
    force=False,
):
    """
    Discover promotional candidates for one episode.

    Existing episode results are reused unless force=True.
    """

    cache_dir = Path(
        cache_dir or settings.CACHE_DIR / "promo_discovery"
    )

    cache_dir.mkdir(parents=True, exist_ok=True)

    cache_file = cache_dir / (
        f"episode_{episode.episode_number:03d}.json"
    )

    # --------------------------------------------------------
    # Check cache
    # --------------------------------------------------------

    source_hash = hashlib.sha256(
        episode.raw_text.encode("utf-8")
    ).hexdigest()

    if cache_file.exists() and not force:

        try:

            cached = json.loads(
                cache_file.read_text(encoding="utf-8")
            )

            if cached.get("source_hash") == source_hash:

                candidates = [
                    PromoCandidate.model_validate(item)
                    for item in cached["candidates"]
                ]

                return candidates, cached.get("metadata", [])

        except Exception:
            # Invalid cache: rebuild this episode.
            pass

    # --------------------------------------------------------
    # Generate candidate windows
    # --------------------------------------------------------

    max_windows = int(
        __import__("os").getenv(
            "GEMINI_MAX_WINDOWS_PER_EPISODE", "5"
        )
    )

    windows = generate_candidate_windows(
        episode,
        max_windows=max_windows,
    )

    if not windows:
        return [], []

    # --------------------------------------------------------
    # Attempt Gemini analysis
    # --------------------------------------------------------

    prompt = build_episode_prompt(
        episode,
        windows,
    )

    ai_result = provider.analyze(prompt)

    evaluations = {}

    if ai_result:

        raw_evaluations = ai_result.get(
            "evaluations", []
        )

        for evaluation in raw_evaluations:

            if not isinstance(evaluation, dict):
                continue

            window_id = evaluation.get("window_id")

            if window_id:
                evaluations[window_id] = evaluation

    # --------------------------------------------------------
    # Build candidates
    # --------------------------------------------------------

    candidates = []

    metadata = []

    for window in windows:

        evaluation = evaluations.get(
            window["window_id"]
        )

        if evaluation and evaluation.get("is_good_promo") is True:

            mode = "GEMINI"

        else:

            evaluation = fallback_evaluation(window)

            mode = "DETERMINISTIC_FALLBACK"

        candidate, provenance = create_candidate(
            episode=episode,
            window=window,
            evaluation=evaluation,
            analysis_mode=mode,
        )

        candidates.append(candidate)

        metadata.append({
            "promo_id": candidate.promo_id,
            **provenance,
        })

    # --------------------------------------------------------
    # Save episode cache
    # --------------------------------------------------------

    save_json(
        {
            "episode_number": episode.episode_number,
            "source_hash": source_hash,
            "candidate_count": len(candidates),
            "candidates": [
                candidate.model_dump(mode="json")
                for candidate in candidates
            ],
            "metadata": metadata,
        },
        cache_file,
    )

    return candidates, metadata


def discover_all_promos(
    episodes,
    force=False,
):
    """
    Run discovery across all episodes.

    Gemini request budget is shared across this run.
    """

    provider = GeminiProvider()

    all_candidates = []

    all_metadata = []

    episode_results = []

    for episode in episodes:

        try:

            candidates, metadata = discover_episode_promos(
                episode=episode,
                provider=provider,
                force=force,
            )

            all_candidates.extend(candidates)

            all_metadata.extend(metadata)

            episode_results.append({
                "episode_number": episode.episode_number,
                "candidate_count": len(candidates),
                "status": "SUCCESS",
            })

        except Exception as exc:

            episode_results.append({
                "episode_number": episode.episode_number,
                "candidate_count": 0,
                "status": "FAILED",
                "error": str(exc),
            })

    output_dir = settings.PROCESSED_DIR

    save_json(
        [
            candidate.model_dump(mode="json")
            for candidate in all_candidates
        ],
        output_dir / "promo_candidates.json",
    )

    save_json(
        all_metadata,
        output_dir / "promo_analysis_metadata.json",
    )

    save_json(
        {
            "total_episodes": len(episodes),
            "successful_episodes": sum(
                1 for item in episode_results
                if item["status"] == "SUCCESS"
            ),
            "failed_episodes": sum(
                1 for item in episode_results
                if item["status"] == "FAILED"
            ),
            "total_candidates": len(all_candidates),
            "episode_results": episode_results,
            "provider_status": provider.status(),
        },
        output_dir / "discovery_summary.json",
    )

    return all_candidates, all_metadata, provider.status()
