"""Self-contained exports for ranked promos and rejected candidates."""

from __future__ import annotations

import csv
import json
from pathlib import Path


DEFAULT_EXPORT_DIR = Path("data/exports")


def _timeline(candidate: dict) -> str:
    parts = []
    for segment in candidate.get("source_segments") or []:
        type_ = segment.get("segment_type", "")
        start = segment.get("start_timestamp", "")
        end = segment.get("end_timestamp", "")
        speaker = segment.get("speaker") or ""
        content = str(segment.get("content", "")).replace("\n", " ").strip()
        label = f"{speaker}: {content}" if speaker else content
        parts.append(f"[{type_}] {start}-{end} {label}")
    return " | ".join(parts)


def _scores(candidate: dict) -> dict:
    return candidate.get("score_breakdown") or {}


CSV_COLUMNS = [
    "rank",
    "promo_id",
    "episode_number",
    "title",
    "start_timestamp",
    "end_timestamp",
    "duration_seconds",
    "opening_hook",
    "hook_type",
    "main_dramatic_moment",
    "ending_cliffhanger_or_payoff",
    "cliffhanger_type",
    "emotional_category",
    "why_it_works",
    "promotional_justification",
    "analysis_mode",
    "score_source",
    "validation_status",
    "human_review_label",
    "final_score",
    "hook_strength",
    "emotional_impact",
    "suspense_curiosity",
    "cliffhanger_payoff",
    "standalone_clarity",
    "promotional_relevance",
    "rank_reason",
    "validation_issues",
    "source_segment_ids",
    "segment_timeline",
]


def export_promos(candidates: list[dict], output_dir=DEFAULT_EXPORT_DIR):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "ranked_promos.json"
    csv_path = output_dir / "ranked_promos.csv"

    json_path.write_text(
        json.dumps(candidates, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    with csv_path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_COLUMNS)
        writer.writeheader()

        for candidate in candidates:
            scores = _scores(candidate)
            row = {key: candidate.get(key, "") for key in CSV_COLUMNS}
            for key in CSV_COLUMNS:
                if key in scores:
                    row[key] = scores[key]

            row["validation_issues"] = " | ".join(
                candidate.get("validation_issues") or []
            )
            row["source_segment_ids"] = ", ".join(
                str(x) for x in candidate.get("source_segment_ids") or []
            )
            row["segment_timeline"] = _timeline(candidate)
            writer.writerow(row)

    return str(json_path), str(csv_path)


def export_rejected(candidates: list[dict], output_dir=DEFAULT_EXPORT_DIR):
    """Export duplicates/rejections separately, never inside the ranked list."""

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "rejected_candidates.json"
    path.write_text(
        json.dumps(candidates, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return str(path)
