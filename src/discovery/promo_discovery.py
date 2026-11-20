"""
Promo discovery orchestration.

This module owns candidate construction. Python owns every timestamp; the AI
(or local fallback) may only supply text and scores. A candidate is only
created when the evaluator considers the window usable. If the evaluator says
``is_good_promo: false`` the window is skipped and recorded as a rejection
instead of being silently promoted to a candidate.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from src.ai.provider_factory import create_provider
from src.ai.prompts import build_episode_prompt
from src.config import settings
from src.discovery.window_generator import generate_candidate_windows
from src.models import PromoCandidate, SourceSegment
from src.scoring.scorer import (
    build_promotional_justification,
    build_why_it_works,
)
from src.utils.timestamps import seconds_to_timestamp


def save_json(data, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    temp.replace(path)


def safe_dialogue(segments):
    return [
        segment.content
        for segment in segments
        if segment.segment_type == "DIALOGUE"
    ]


def extract_characters(segments):
    return sorted({
        segment.speaker
        for segment in segments
        if segment.speaker and segment.segment_type == "DIALOGUE"
    })


def _clip(value: float, lower: float, upper: float) -> float:
    return round(max(lower, min(upper, value)), 2)


def _source_segments(
    segments,
    start: float | None = None,
    end: float | None = None,
) -> list[SourceSegment]:
    """Ordered source segments clipped to the promo window.

    Screenplay segments overlap each other and can extend past a clip's cut
    points. The exported spans are clipped to ``[start, end]`` so the ordered
    segment timeline exactly covers the stated clip, while ``segment_id``
    still identifies the original screenplay segment.
    """

    ordered = sorted(segments, key=lambda s: s.start_seconds)
    if start is None:
        start = min(float(s.start_seconds) for s in ordered)
    if end is None:
        end = max(float(s.end_seconds) for s in ordered)

    clipped: list[SourceSegment] = []
    for segment in ordered:
        seg_start = _clip(float(segment.start_seconds), start, end)
        seg_end = _clip(float(segment.end_seconds), start, end)
        if seg_end <= seg_start:
            continue
        clipped.append(SourceSegment(
            segment_id=segment.segment_id,
            scene_id=segment.scene_id,
            segment_type=segment.segment_type,
            speaker=segment.speaker,
            start_timestamp=seconds_to_timestamp(seg_start),
            end_timestamp=seconds_to_timestamp(seg_end),
            start_seconds=seg_start,
            end_seconds=seg_end,
            content=segment.content,
        ))
    return clipped


def _valid_scores(scores: dict | None) -> bool:
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


def fallback_evaluation(window):
    """Deterministic evaluation without external APIs.

    These are heuristic results, not LLM judgments.
    """

    segments = window["segments"]
    editorial = window.get("editorial", {})
    scores = window.get("score_breakdown", {})

    dialogue = safe_dialogue(segments)
    characters = extract_characters(segments)

    categories = window.get("signal_categories", [])
    category = (
        categories[0].title() if categories else
        editorial.get("emotional_category", "Drama")
    )

    opening_hook = editorial.get("opening_hook") or (
        dialogue[0] if dialogue else ""
    )
    ending = editorial.get("ending_cliffhanger") or (
        dialogue[-1] if dialogue else ""
    )
    main_moment = editorial.get("main_dramatic_moment") or opening_hook

    duration = float(window["duration_seconds"])
    why = build_why_it_works(
        opening_hook=opening_hook,
        ending_cliffhanger=ending,
        hook_type=editorial.get("hook_type", "unknown"),
        cliffhanger_type=editorial.get("cliffhanger_type", "unknown"),
        duration=duration,
        categories=categories,
    )
    justification = build_promotional_justification(
        opening_hook=opening_hook,
        ending_cliffhanger=ending,
        hook_type=editorial.get("hook_type", "unknown"),
        cliffhanger_type=editorial.get("cliffhanger_type", "unknown"),
        duration=duration,
        categories=categories,
    )

    return {
        "window_id": window["window_id"],
        "is_good_promo": float(scores.get("final_score", 0)) >= float(
            getattr(settings, "PROMO_GOOD_SCORE", 6.0)
        ),
        "title": editorial.get(
            "title", f"Episode {window['episode_number']} — {category}"
        ),
        "opening_hook": opening_hook,
        "main_dramatic_moment": main_moment,
        "ending_cliffhanger_or_payoff": ending,
        "emotional_category": category,
        "promotional_justification": justification,
        "why_it_works": why,
        "hook_type": editorial.get("hook_type", "unknown"),
        "cliffhanger_type": editorial.get("cliffhanger_type", "unknown"),
        "dialogue": dialogue,
        "characters": characters,
        "hook_strength": scores.get("hook_strength", 0),
        "emotional_impact": scores.get("emotional_impact", 0),
        "suspense_curiosity": scores.get("suspense_curiosity", 0),
        "cliffhanger_payoff": scores.get("cliffhanger_payoff", 0),
        "standalone_clarity": scores.get("standalone_clarity", 0),
        "promotional_relevance": scores.get("promotional_relevance", 0),
        "final_score": scores.get("final_score", 0),
        "analysis_mode": "DETERMINISTIC_FALLBACK",
    }


def create_candidate(episode, window, evaluation, analysis_mode):
    """Construct a PromoCandidate using Python-owned timestamps."""

    segments = window["segments"]
    source_ids = [segment.segment_id for segment in segments]
    dialogue = safe_dialogue(segments)
    characters = extract_characters(segments)

    title = str(evaluation.get("title", "Untitled Promo"))[:150]
    duration = float(window["duration_seconds"])

    scores = {
        "hook_strength": evaluation.get("hook_strength", 0),
        "emotional_impact": evaluation.get("emotional_impact", 0),
        "suspense_curiosity": evaluation.get("suspense_curiosity", 0),
        "cliffhanger_payoff": evaluation.get("cliffhanger_payoff", 0),
        "standalone_clarity": evaluation.get("standalone_clarity", 0),
        "promotional_relevance": evaluation.get("promotional_relevance", 0),
        "final_score": evaluation.get(
            "final_score",
            window.get("score_breakdown", {}).get("final_score", 0),
        ),
    }

    if not float(scores.get("final_score") or 0) and any(
        float(scores.get(key) or 0)
        for key in (
            "hook_strength",
            "emotional_impact",
            "suspense_curiosity",
            "cliffhanger_payoff",
            "standalone_clarity",
            "promotional_relevance",
        )
    ):
        from src.scoring.scorer import WEIGHTS
        scores["final_score"] = round(sum(
            float(scores.get(key) or 0) * weight
            for key, weight in WEIGHTS.items()
        ), 2)

    if not _valid_scores(scores):
        scores = window.get("score_breakdown", {})

    why = str(evaluation.get("why_it_works") or "")
    justification = str(
        evaluation.get("promotional_justification") or why
    )
    if not why:
        why = justification

    candidate = PromoCandidate(
        # window_id is already W0001; add the episode prefix exactly once.
        promo_id=f"E{episode.episode_number:03d}_{window['window_id']}",
        title=title,
        episode_number=episode.episode_number,
        start_timestamp=window["start_timestamp"],
        end_timestamp=window["end_timestamp"],
        start_seconds=window["start_seconds"],
        end_seconds=window["end_seconds"],
        duration_seconds=duration,
        opening_hook=str(evaluation.get("opening_hook", "")),
        main_dramatic_moment=str(evaluation.get("main_dramatic_moment", "")),
        ending_cliffhanger_or_payoff=str(
            evaluation.get("ending_cliffhanger_or_payoff", "")
        ),
        promotional_justification=justification,
        dialogue=dialogue,
        characters=characters,
        emotional_category=str(evaluation.get("emotional_category", "Drama")),
        source_segment_ids=source_ids,
        source_segments=_source_segments(
            segments,
            start=float(window["start_seconds"]),
            end=float(window["end_seconds"]),
        ),
        hook_type=str(evaluation.get("hook_type", "unknown")),
        cliffhanger_type=str(evaluation.get("cliffhanger_type", "unknown")),
        why_it_works=why,
        analysis_mode=analysis_mode,
        score_breakdown=scores,
        validation_status="PENDING",
        human_review_label=None,
    )

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
    max_windows=5,
):
    """Discover promotional candidates for one episode."""

    cache_dir = Path(cache_dir or settings.CACHE_DIR / "promo_discovery")
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"episode_{episode.episode_number:03d}.json"

    source_hash = hashlib.sha256(
        episode.raw_text.encode("utf-8")
    ).hexdigest()

    if cache_file.exists() and not force:
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            if (
                cached.get("source_hash") == source_hash
                and cached.get("schema_version") == 2
            ):
                candidates = [
                    PromoCandidate.model_validate(item)
                    for item in cached["candidates"]
                ]
                return (
                    candidates,
                    cached.get("metadata", []),
                    cached.get("rejected_windows", []),
                )
        except Exception:
            pass

    windows = generate_candidate_windows(episode, max_windows=max_windows)
    if not windows:
        return [], [], []

    prompt = build_episode_prompt(episode, windows)
    ai_result = provider.analyze(prompt)

    evaluations = {}
    if ai_result:
        for evaluation in ai_result.get("evaluations", []):
            if isinstance(evaluation, dict) and evaluation.get("window_id"):
                evaluations[evaluation["window_id"]] = evaluation

    candidates = []
    metadata = []
    rejected_windows = []

    for window in windows:
        evaluation = evaluations.get(window["window_id"])
        mode = "DETERMINISTIC_FALLBACK"

        if evaluation is not None:
            if evaluation.get("is_good_promo") is False:
                rejected_windows.append({
                    "episode_number": episode.episode_number,
                    "window_id": window["window_id"],
                    "start_timestamp": window["start_timestamp"],
                    "end_timestamp": window["end_timestamp"],
                    "reason": "Evaluator rejected the window as not promo-worthy.",
                    "analysis_mode": "GEMINI",
                })
                continue

            if evaluation.get("is_good_promo") is True:
                mode = "GEMINI"
                # Fill any missing text fields from the deterministic
                # evaluation so a partial AI response cannot create blanks.
                fallback = fallback_evaluation(window)
                for key, value in fallback.items():
                    evaluation.setdefault(key, value)
                evaluation["analysis_mode"] = "GEMINI"

        if evaluation is None or evaluation.get("is_good_promo") is not True:
            evaluation = fallback_evaluation(window)
            mode = "DETERMINISTIC_FALLBACK"

        candidate, provenance = create_candidate(
            episode=episode,
            window=window,
            evaluation=evaluation,
            analysis_mode=mode,
        )
        candidates.append(candidate)
        metadata.append({"promo_id": candidate.promo_id, **provenance})

    save_json(
        {
            "schema_version": 2,
            "episode_number": episode.episode_number,
            "source_hash": source_hash,
            "candidate_count": len(candidates),
            "candidates": [
                candidate.model_dump(mode="json")
                for candidate in candidates
            ],
            "metadata": metadata,
            "rejected_windows": rejected_windows,
        },
        cache_file,
    )

    return candidates, metadata, rejected_windows


def discover_all_promos(
    episodes,
    force=False,
    processed_dir=None,
    cache_dir=None,
    provider_mode=None,
    max_episodes=None,
    max_windows=5,
):
    """Run discovery across all episodes."""

    provider = create_provider(provider_mode)
    processed_dir = Path(processed_dir or settings.PROCESSED_DIR)
    cache_dir = Path(cache_dir or settings.CACHE_DIR / "promo_discovery")

    all_candidates = []
    all_metadata = []
    all_rejected = []
    episode_results = []

    selected_episodes = list(episodes)
    if max_episodes is not None:
        selected_episodes = selected_episodes[: int(max_episodes)]

    for episode in selected_episodes:
        try:
            candidates, metadata, rejected = discover_episode_promos(
                episode=episode,
                provider=provider,
                cache_dir=cache_dir,
                force=force,
                max_windows=max_windows,
            )
            all_candidates.extend(candidates)
            all_metadata.extend(metadata)
            all_rejected.extend(rejected)
            episode_results.append({
                "episode_number": episode.episode_number,
                "candidate_count": len(candidates),
                "rejected_window_count": len(rejected),
                "status": "SUCCESS",
            })
        except Exception as exc:
            episode_results.append({
                "episode_number": episode.episode_number,
                "candidate_count": 0,
                "rejected_window_count": 0,
                "status": "FAILED",
                "error": str(exc),
            })

    save_json(
        [candidate.model_dump(mode="json") for candidate in all_candidates],
        processed_dir / "promo_candidates.json",
    )
    save_json(all_metadata, processed_dir / "promo_analysis_metadata.json")
    save_json(all_rejected, processed_dir / "rejected_windows.json")
    save_json(
        {
            "total_episodes": len(selected_episodes),
            "successful_episodes": sum(
                1 for item in episode_results if item["status"] == "SUCCESS"
            ),
            "failed_episodes": sum(
                1 for item in episode_results if item["status"] == "FAILED"
            ),
            "total_candidates": len(all_candidates),
            "rejected_window_count": len(all_rejected),
            "analysis_mode_counts": {
                mode: sum(
                    1 for m in all_metadata
                    if m.get("analysis_mode") == mode
                )
                for mode in ("GEMINI", "DETERMINISTIC_FALLBACK")
            },
            "episode_results": episode_results,
            "provider_status": provider.status(),
        },
        processed_dir / "discovery_summary.json",
    )

    return all_candidates, all_metadata, provider.status()
