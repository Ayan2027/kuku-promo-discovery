"""Rank, validate, de-duplicate and export one discovery run."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from src.config import settings
from src.discovery.ranker import rank_and_validate
from src.exports.promo_exporter import export_promos, export_rejected
from src.quality.output_audit import build_output_audit, write_output_audit


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def get_episodes(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("episodes"), list):
        return data["episodes"]
    raise ValueError("Unexpected parsed_screenplays.json structure.")


def get_candidates(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("candidates"), list):
        return data["candidates"]
    raise ValueError("Unexpected promo_candidates.json structure.")


def _ends_mid_dialogue(candidate: dict) -> bool:
    end = float(candidate.get("end_seconds", 0))
    for segment in candidate.get("source_segments") or []:
        if segment.get("segment_type") != "DIALOGUE":
            continue
        if float(segment.get("start_seconds", 0)) < end < float(
            segment.get("end_seconds", 0)
        ) - 0.01:
            return True
    return False


def _scene_count(candidate: dict) -> int:
    return len({
        segment.get("scene_id")
        for segment in candidate.get("source_segments") or []
        if segment.get("scene_id")
    })


def _hook_offset(candidate: dict) -> float | None:
    """Seconds from the clip start to its opening hook, if it can be located."""

    hook = str(candidate.get("opening_hook", "")).strip()
    segments = candidate.get("source_segments") or []

    if hook:
        for segment in segments:
            speaker = str(segment.get("speaker") or "").strip()
            content = str(segment.get("content", "")).replace(
                "\n", " "
            ).strip()
            label = f"{speaker}: {content}" if speaker else content
            if label.strip() == hook:
                return round(
                    float(segment.get("start_seconds", 0))
                    - float(candidate.get("start_seconds", 0)),
                    2,
                )

    beats = [
        segment for segment in segments
        if str(segment.get("segment_type", "")).upper()
        in ("DIALOGUE", "ACTION")
    ]
    if not beats:
        return None
    first = min(
        beats, key=lambda s: float(s.get("start_seconds", 0))
    )
    return round(
        float(first.get("start_seconds", 0))
        - float(candidate.get("start_seconds", 0)),
        2,
    )


def _bad_pick_examples(candidates: list[dict], limit: int = 5) -> list[dict]:
    weak = [
        candidate for candidate in candidates
        if candidate.get("human_review_label") in {"Bad Promo", "Weak Promo"}
    ]
    weak.sort(key=lambda c: float(
        (c.get("score_breakdown") or {}).get("final_score", 0)
    ))

    examples = []
    for candidate in weak[:limit]:
        scores = candidate.get("score_breakdown") or {}
        examples.append({
            "rank": candidate.get("rank"),
            "promo_id": candidate.get("promo_id"),
            "episode_number": candidate.get("episode_number"),
            "score": scores.get("final_score"),
            "label": candidate.get("human_review_label"),
            "opening_hook": candidate.get("opening_hook"),
            "ending": candidate.get("ending_cliffhanger_or_payoff"),
            "why_it_fails": (
                f"Hook scored {scores.get('hook_strength', 0)}/10 and "
                f"ending scored {scores.get('cliffhanger_payoff', 0)}/10. "
                f"Ends mid-dialogue: {_ends_mid_dialogue(candidate)}. "
                f"Crosses {_scene_count(candidate)} scene(s)."
            ),
            "validation_issues": candidate.get("validation_issues", []),
        })
    return examples


def build_quality_check(
    ranked: list[dict],
    dropped: list[dict],
    scoring_counts: dict,
) -> dict:
    scores = [
        float((candidate.get("score_breakdown") or {}).get("final_score", 0))
        for candidate in ranked
    ]
    labels = Counter(
        candidate.get("human_review_label", "Unlabelled")
        for candidate in ranked
    )
    durations = [
        float(candidate.get("duration_seconds", 0))
        for candidate in ranked
    ]
    hooks = [
        str(candidate.get("opening_hook", "")).strip()
        for candidate in ranked
    ]
    mid_dialogue = sum(_ends_mid_dialogue(c) for c in ranked)
    scene_crossings = sum(_scene_count(c) > 1 for c in ranked)
    short_hooks = sum(len(hook.split()) <= 2 for hook in hooks)
    late_hooks = [
        offset for offset in (
            _hook_offset(candidate) for candidate in ranked
        )
        if offset is not None and offset > 3.0
    ]
    closure_endings = sum(
        candidate.get("cliffhanger_type") == "closure"
        for candidate in ranked
    )
    duplicate_dropped = len(dropped)

    return {
        "total_candidates": len(ranked),
        "label_counts": dict(labels),
        "score_min": round(min(scores), 2) if scores else 0,
        "score_max": round(max(scores), 2) if scores else 0,
        "score_mean": round(sum(scores) / len(scores), 2) if scores else 0,
        "duration_min": round(min(durations), 2) if durations else 0,
        "duration_max": round(max(durations), 2) if durations else 0,
        "duration_distinct_values": len({round(d, 1) for d in durations}),
        "episodes_covered": len({
            candidate.get("episode_number") for candidate in ranked
        }),
        "clips_ending_mid_dialogue": mid_dialogue,
        "clips_crossing_scene_boundaries": scene_crossings,
        "hooks_two_words_or_less": short_hooks,
        "hooks_beyond_3_seconds": len(late_hooks),
        "closure_endings": closure_endings,
        "duplicates_removed": duplicate_dropped,
        "scoring_sources": scoring_counts,
        "bad_pick_examples": _bad_pick_examples(ranked),
        "note": (
            "Scores are deterministic screenplay-text heuristics, not "
            "measured promotional performance. 'Good Promo' means the clip "
            "cleared the internal quality thresholds; it is not a guarantee."
        ),
    }


def _write_quality_markdown(quality: dict, path: Path):
    labels = quality["label_counts"]
    lines = [
        "# Quality check",
        "",
        f"- Candidates ranked: **{quality['total_candidates']}**",
        f"- Episodes covered: **{quality['episodes_covered']}**",
        f"- Good / Weak / Bad / Needs review: **{labels.get('Good Promo', 0)} / "
        f"{labels.get('Weak Promo', 0)} / {labels.get('Bad Promo', 0)} / "
        f"{labels.get('Needs Review', 0)}**",
        f"- Score range: **{quality['score_min']}–{quality['score_max']}** "
        f"(mean {quality['score_mean']})",
        f"- Duration range: **{quality['duration_min']}–"
        f"{quality['duration_max']}s** "
        f"({quality['duration_distinct_values']} distinct values)",
        f"- Clips ending mid-dialogue: **{quality['clips_ending_mid_dialogue']}**",
        f"- Clips crossing scene boundaries: "
        f"**{quality['clips_crossing_scene_boundaries']}**",
        f"- Hooks of two words or fewer: "
        f"**{quality['hooks_two_words_or_less']}**",
        f"- Hooks starting after 3 seconds: "
        f"**{quality['hooks_beyond_3_seconds']}**",
        f"- Closure endings: **{quality['closure_endings']}**",
        f"- Duplicates removed from the ranked list: "
        f"**{quality['duplicates_removed']}**",
        "",
        "## Where it still picks badly",
        "",
    ]
    if quality["bad_pick_examples"]:
        for item in quality["bad_pick_examples"]:
            lines.append(
                f"- **Rank {item['rank']} / {item['promo_id']}** "
                f"(score {item['score']}, {item['label']}): "
                f"{item['why_it_fails']}"
            )
    else:
        lines.append(
            "- No candidate fell below the weak threshold in this run. "
            "That is not proof of quality; it means the scorer needs a "
            "harder gold set."
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def run_batch4(
    processed_dir=None,
    export_dir=None,
    min_duration=20.0,
    max_duration=60.0,
    drop_repetitive=True,
):
    processed_dir = Path(processed_dir or settings.PROCESSED_DIR)
    export_dir = Path(export_dir or settings.EXPORT_DIR)

    episodes = get_episodes(load_json(processed_dir / "parsed_screenplays.json"))
    candidates = get_candidates(load_json(processed_dir / "promo_candidates.json"))

    ranked, dropped, scoring_counts = rank_and_validate(
        candidates,
        episodes,
        min_duration=min_duration,
        max_duration=max_duration,
        drop_repetitive=drop_repetitive,
        return_dropped=True,
    )

    json_path, csv_path = export_promos(ranked, output_dir=export_dir)
    rejected_path = export_rejected(dropped, output_dir=export_dir)

    quality = build_quality_check(ranked, dropped, scoring_counts)
    quality_path = export_dir / "quality_check.json"
    quality_path.write_text(
        json.dumps(quality, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    _write_quality_markdown(quality, export_dir / "quality_check.md")

    audit = build_output_audit(
        ranked=ranked,
        episodes=episodes,
        export_dir=export_dir,
        quality=quality,
    )
    audit_json, audit_md = write_output_audit(audit, export_dir)

    summary = {
        "total_candidates": len(ranked),
        "duplicates_removed": len(dropped),
        "validation_status_counts": dict(Counter(
            candidate.get("validation_status", "UNKNOWN") for candidate in ranked
        )),
        "human_review_label_counts": quality["label_counts"],
        "average_heuristic_score": quality["score_mean"],
        "highest_score": quality["score_max"],
        "lowest_score": quality["score_min"],
        "scoring_method": "Deterministic screenplay-text heuristics",
        "score_weights": {
            "hook_strength": 0.25,
            "emotional_impact": 0.15,
            "suspense_curiosity": 0.15,
            "cliffhanger_payoff": 0.20,
            "standalone_clarity": 0.15,
            "promotional_relevance": 0.10,
        },
        "recommended_first": [
            {
                "rank": candidate.get("rank"),
                "promo_id": candidate.get("promo_id"),
                "episode_number": candidate.get("episode_number"),
                "score": (candidate.get("score_breakdown") or {}).get(
                    "final_score"
                ),
                "reason": candidate.get("rank_reason"),
                "start": candidate.get("start_timestamp"),
                "end": candidate.get("end_timestamp"),
            }
            for candidate in ranked[:5]
        ],
        "quality_check": {
            "clips_ending_mid_dialogue": quality[
                "clips_ending_mid_dialogue"
            ],
            "clips_crossing_scene_boundaries": quality[
                "clips_crossing_scene_boundaries"
            ],
            "hooks_two_words_or_less": quality["hooks_two_words_or_less"],
            "hooks_beyond_3_seconds": quality["hooks_beyond_3_seconds"],
            "closure_endings": quality["closure_endings"],
            "duration_distinct_values": quality["duration_distinct_values"],
        },
        "note": (
            "Scores are heuristic ranking signals, not measured promo "
            "quality or human-validated accuracy. All candidates require "
            "human review before final selection."
        ),
        "requirements_check": {
            "status": audit["status"],
            "passed_checks": audit["passed_checks"],
            "total_checks": audit["total_checks"],
            "failed_checks": audit["failed_checks"],
        },
        "json_export": json_path,
        "csv_export": csv_path,
        "rejected_export": rejected_path,
        "quality_check_export": str(quality_path),
        "requirements_check_export": audit_json,
        "requirements_check_markdown": audit_md,
    }

    summary_path = export_dir / "batch4_summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n===== RANKING COMPLETE =====")
    print("Ranked candidates:", len(ranked))
    print("Duplicates removed:", len(dropped))
    print("Review labels:", summary["human_review_label_counts"])
    print("Average score:", summary["average_heuristic_score"])
    print("JSON:", json_path)
    print("CSV:", csv_path)
    print("Quality check:", quality_path)
    print(
        "Requirements check:",
        audit["status"],
        f"({audit['passed_checks']}/{audit['total_checks']})",
        "-",
        audit_json,
    )
    print("Summary:", summary_path)

    return {
        "ranked": ranked,
        "dropped": dropped,
        "summary": summary,
        "quality": quality,
        "audit": audit,
        "json_path": json_path,
        "csv_path": csv_path,
        "summary_path": str(summary_path),
        "quality_path": str(quality_path),
        "rejected_path": rejected_path,
        "audit_path": audit_json,
    }


if __name__ == "__main__":
    run_batch4()
