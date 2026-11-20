
import json
from collections import Counter
from pathlib import Path

from src.discovery.ranker import rank_and_validate
from src.exports.promo_exporter import export_promos


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


def run_batch4():
    episodes = get_episodes(
        load_json("data/processed/parsed_screenplays.json")
    )
    candidates = get_candidates(
        load_json("data/processed/promo_candidates.json")
    )

    ranked = rank_and_validate(
        candidates,
        episodes,
        min_duration=20,
        max_duration=60,
    )

    json_path, csv_path = export_promos(ranked)

    validation_counts = Counter(
        item.get("validation_status", "UNKNOWN") for item in ranked
    )
    review_counts = Counter(
        item.get("human_review_label", "Unlabelled") for item in ranked
    )

    scores = [
        float(item.get("score_breakdown", {}).get("final_score", 0))
        for item in ranked
    ]

    summary = {
        "total_candidates": len(ranked),
        "validation_status_counts": dict(validation_counts),
        "human_review_label_counts": dict(review_counts),
        "average_heuristic_score": round(
            sum(scores) / len(scores), 2
        ) if scores else 0,
        "highest_score": max(scores, default=0),
        "lowest_score": min(scores, default=0),
        "scoring_method": "Deterministic screenplay-text heuristics",
        "score_weights": {
            "hook_strength": 0.20,
            "emotional_impact": 0.20,
            "suspense_curiosity": 0.20,
            "cliffhanger_payoff": 0.15,
            "standalone_clarity": 0.15,
            "promotional_relevance": 0.10,
        },
        "note": (
            "Scores are heuristic ranking signals, not measured promo "
            "quality or human-validated accuracy. All candidates require "
            "human review before final selection."
        ),
        "json_export": json_path,
        "csv_export": csv_path,
    }

    summary_path = Path("data/exports/batch4_summary.json")
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n===== BATCH 4 COMPLETED =====")
    print("Candidates:", len(ranked))
    print("Validation:", dict(validation_counts))
    print("Review labels:", dict(review_counts))
    print("Average heuristic score:", summary["average_heuristic_score"])
    print("JSON:", json_path)
    print("CSV:", csv_path)
    print("Summary:", summary_path)


if __name__ == "__main__":
    run_batch4()
