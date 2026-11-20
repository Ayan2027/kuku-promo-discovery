
import csv
import json
from pathlib import Path


EXPORT_DIR = Path("data/exports")


def export_promos(candidates: list[dict], output_dir=EXPORT_DIR):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "ranked_promos.json"
    csv_path = output_dir / "ranked_promos.csv"

    json_path.write_text(
        json.dumps(candidates, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    columns = [
        "rank",
        "promo_id",
        "episode_number",
        "title",
        "start_timestamp",
        "end_timestamp",
        "duration_seconds",
        "opening_hook",
        "main_dramatic_moment",
        "ending_cliffhanger_or_payoff",
        "emotional_category",
        "promotional_justification",
        "validation_status",
        "human_review_label",
        "final_score",
        "hook_strength",
        "emotional_impact",
        "suspense_curiosity",
        "cliffhanger_payoff",
        "standalone_clarity",
        "promotional_relevance",
        "validation_issues",
        "source_segment_ids",
    ]

    with csv_path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()

        for candidate in candidates:
            scores = candidate.get("score_breakdown") or {}
            row = {key: candidate.get(key, "") for key in columns}
            for key in columns:
                if key in scores:
                    row[key] = scores[key]

            row["validation_issues"] = " | ".join(
                candidate.get("validation_issues") or []
            )
            row["source_segment_ids"] = ", ".join(
                str(x) for x in candidate.get("source_segment_ids") or []
            )
            writer.writerow(row)

    return str(json_path), str(csv_path)
