"""Audit a finished run against the Problem 1 brief.

This module exists because a candidate generator can look healthy while
violating a hard requirement: a clip outside 20-60 seconds, a missing hook,
an unsorted source timeline, or an episode with no candidates at all. The
quality report describes how good the picks are; this audit checks whether
the output is even admissible.

Every check is deterministic and runs on the exported files, not on internal
state, so an evaluator can reproduce it from ``raw_outputs/`` alone.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from src.utils.timestamps import parse_timestamp


MIN_DURATION = 20.0
MAX_DURATION = 60.0
HOOK_WINDOW_SECONDS = 3.0


def _check(
    check_id: str,
    requirement: str,
    passed: bool,
    detail: str,
) -> dict:
    return {
        "id": check_id,
        "requirement": requirement,
        "passed": bool(passed),
        "detail": detail,
    }


def _source_segments(candidate: dict) -> list[dict]:
    return [
        segment for segment in candidate.get("source_segments") or []
        if isinstance(segment, dict)
    ]


def _segment_label(segment: dict) -> str:
    speaker = str(segment.get("speaker") or "").strip()
    content = str(segment.get("content") or "").replace("\n", " ").strip()
    return f"{speaker}: {content}" if speaker else content


def hook_offset(candidate: dict) -> float | None:
    """Seconds from the clip start to the first on-screen story beat."""

    start = float(candidate.get("start_seconds", 0))
    segments = _source_segments(candidate)
    hook = str(candidate.get("opening_hook") or "").strip()

    beats = [
        segment for segment in segments
        if str(segment.get("segment_type", "")).upper()
        in ("DIALOGUE", "ACTION")
    ]
    if not beats:
        return None

    if hook:
        for segment in beats:
            if _segment_label(segment) == hook:
                return round(
                    float(segment.get("start_seconds", 0)) - start,
                    2,
                )

    first = min(beats, key=lambda s: float(s.get("start_seconds", 0)))
    return round(float(first.get("start_seconds", 0)) - start, 2)


def _ends_mid_dialogue(candidate: dict) -> bool:
    end = float(candidate.get("end_seconds", 0))
    for segment in _source_segments(candidate):
        if str(segment.get("segment_type", "")).upper() != "DIALOGUE":
            continue
        if (
            float(segment.get("start_seconds", 0))
            < end
            < float(segment.get("end_seconds", 0)) - 0.01
        ):
            return True
    return False


def _expected_label(candidate: dict) -> str | None:
    status = candidate.get("validation_status")
    if status == "INVALID":
        return "Invalid"
    if status == "NEEDS_REVIEW":
        return "Needs Review"
    score = float(
        (candidate.get("score_breakdown") or {}).get("final_score", 0)
    )
    from src.config import settings

    if score >= float(settings.PROMO_GOOD_SCORE):
        return "Good Promo"
    if score >= float(settings.PROMO_WEAK_SCORE):
        return "Weak Promo"
    return "Bad Promo"


def _read_csv_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return {row.get("promo_id", "") for row in csv.DictReader(file)}


def build_output_audit(
    ranked: list[dict],
    episodes: list[dict],
    export_dir: str | Path | None = None,
    quality: dict | None = None,
) -> dict:
    """Return a pass/fail report for every hard requirement in the brief."""

    export_dir = Path(export_dir) if export_dir else None
    quality = quality or {}
    episode_numbers = {
        int(episode.get("episode_number", 0)) for episode in episodes
    }
    ranked_episode_numbers = {
        int(candidate.get("episode_number", 0)) for candidate in ranked
    }
    missing_episodes = sorted(episode_numbers - ranked_episode_numbers)

    checks: list[dict] = []

    checks.append(_check(
        "has_candidates",
        "The run produces at least one promo.",
        bool(ranked),
        f"{len(ranked)} ranked candidates.",
    ))
    checks.append(_check(
        "all_episodes_covered",
        "Every parsed episode contributes at least one candidate.",
        not missing_episodes,
        "All episodes covered." if not missing_episodes
        else f"No candidates for episodes: {missing_episodes}.",
    ))

    durations = [float(c.get("duration_seconds", 0)) for c in ranked]
    bad_durations = [
        c.get("promo_id") for c in ranked
        if not MIN_DURATION <= float(c.get("duration_seconds", 0))
        <= MAX_DURATION
    ]
    checks.append(_check(
        "duration_20_60",
        "Every promo is 20-60 seconds long.",
        not bad_durations,
        f"{len(durations)} clips in range."
        if not bad_durations else f"Out of range: {bad_durations[:10]}.",
    ))

    timestamp_failures = []
    for candidate in ranked:
        try:
            start = float(candidate["start_seconds"])
            end = float(candidate["end_seconds"])
            duration = float(candidate["duration_seconds"])
            parsed_start = parse_timestamp(str(candidate["start_timestamp"]))
            parsed_end = parse_timestamp(str(candidate["end_timestamp"]))
            if (
                abs(parsed_start - start) > 0.01
                or abs(parsed_end - end) > 0.01
                or abs((end - start) - duration) > 0.01
            ):
                timestamp_failures.append(candidate.get("promo_id"))
        except (KeyError, TypeError, ValueError):
            timestamp_failures.append(candidate.get("promo_id"))
    checks.append(_check(
        "timestamp_consistency",
        "Start, end and duration agree in every candidate.",
        not timestamp_failures,
        "All timestamps are internally consistent."
        if not timestamp_failures
        else f"Bad timestamps: {timestamp_failures[:10]}.",
    ))

    segment_failures = []
    timeline_failures = []
    for candidate in ranked:
        segments = _source_segments(candidate)
        if not segments:
            segment_failures.append(candidate.get("promo_id"))
            continue
        start = float(candidate.get("start_seconds", 0))
        end = float(candidate.get("end_seconds", 0))
        starts = [float(s.get("start_seconds", 0)) for s in segments]
        ends = [float(s.get("end_seconds", 0)) for s in segments]
        if (
            starts != sorted(starts)
            or min(starts) < start - 0.01
            or max(ends) > end + 0.01
            or abs(min(starts) - start) > 0.01
            or abs(max(ends) - end) > 0.01
        ):
            timeline_failures.append(candidate.get("promo_id"))

    checks.append(_check(
        "source_segments_present",
        "Every candidate names its ordered source segments.",
        not segment_failures,
        "All candidates embed source segments."
        if not segment_failures
        else f"Missing segments: {segment_failures[:10]}.",
    ))
    checks.append(_check(
        "source_timeline_covers_clip",
        "Embedded segments are ordered and cover the full clip.",
        not timeline_failures,
        "All source timelines are ordered and clipped to the cut."
        if not timeline_failures
        else f"Bad timelines: {timeline_failures[:10]}.",
    ))

    missing_hooks = [
        c.get("promo_id") for c in ranked
        if not str(c.get("opening_hook") or "").strip()
    ]
    missing_endings = [
        c.get("promo_id") for c in ranked
        if not str(c.get("ending_cliffhanger_or_payoff") or "").strip()
    ]
    bad_why = [
        c.get("promo_id") for c in ranked
        if not str(c.get("why_it_works") or "").strip()
        or "\n" in str(c.get("why_it_works"))
    ]
    checks.append(_check(
        "hook_present",
        "Every promo states its opening hook.",
        not missing_hooks,
        "All hooks present." if not missing_hooks
        else f"Missing hooks: {missing_hooks[:10]}.",
    ))
    checks.append(_check(
        "cliffhanger_present",
        "Every promo states its cliffhanger or ending beat.",
        not missing_endings,
        "All endings present." if not missing_endings
        else f"Missing endings: {missing_endings[:10]}.",
    ))
    checks.append(_check(
        "why_it_works_one_line",
        "Every promo carries a one-line reason.",
        not bad_why,
        "All one-line reasons present." if not bad_why
        else f"Missing or multi-line reasons: {bad_why[:10]}.",
    ))

    late_hooks = [
        (candidate.get("promo_id"), offset)
        for candidate in ranked
        for offset in [hook_offset(candidate)]
        if offset is not None and offset > HOOK_WINDOW_SECONDS
    ]
    unknown_hooks = [
        c.get("promo_id") for c in ranked if hook_offset(c) is None
    ]
    checks.append(_check(
        "hook_within_3s",
        "Every promo opens on a hook within the first 3 seconds.",
        not late_hooks and not unknown_hooks,
        "All hooks land within 3.0s."
        if not late_hooks and not unknown_hooks
        else f"Late hooks: {late_hooks[:10]}; no beat: {unknown_hooks[:10]}.",
    ))

    mid_dialogue = [
        c.get("promo_id") for c in ranked if _ends_mid_dialogue(c)
    ]
    checks.append(_check(
        "no_mid_dialogue_cut",
        "No promo cuts in the middle of a spoken line.",
        not mid_dialogue,
        "No mid-dialogue cuts." if not mid_dialogue
        else f"Mid-dialogue cuts: {mid_dialogue[:10]}.",
    ))

    ids = [str(c.get("promo_id", "")) for c in ranked]
    checks.append(_check(
        "unique_ids",
        "Promo IDs are unique.",
        len(ids) == len(set(ids)),
        f"{len(ids)} IDs, {len(set(ids))} unique.",
    ))

    ranks = [int(c.get("rank", 0)) for c in ranked]
    scores = [
        float((c.get("score_breakdown") or {}).get("final_score", 0))
        for c in ranked
    ]
    ranking_ok = ranks == list(range(1, len(ranked) + 1)) and all(
        scores[index] >= scores[index + 1]
        for index in range(len(scores) - 1)
    )
    checks.append(_check(
        "ranking_is_global",
        "Ranks are contiguous and ordered by score.",
        ranking_ok,
        "Global score order." if ranking_ok
        else "Ranks are not contiguous or not score-ordered.",
    ))

    label_mismatches = [
        c.get("promo_id") for c in ranked
        if c.get("human_review_label") != _expected_label(c)
    ]
    checks.append(_check(
        "labels_match_scores",
        "Quality labels agree with the configured thresholds.",
        not label_mismatches,
        "Labels are threshold-consistent." if not label_mismatches
        else f"Mismatched labels: {label_mismatches[:10]}.",
    ))

    invalid = [
        c.get("promo_id") for c in ranked
        if c.get("validation_status") == "INVALID"
    ]
    checks.append(_check(
        "no_invalid_candidates",
        "No candidate fails structural validation.",
        not invalid,
        "No invalid candidates." if not invalid
        else f"Invalid: {invalid[:10]}.",
    ))

    if export_dir is not None:
        csv_ids = _read_csv_ids(export_dir / "ranked_promos.csv")
        csv_ok = csv_ids == set(ids)
        checks.append(_check(
            "csv_matches_json",
            "The CSV contains exactly the ranked JSON candidates.",
            csv_ok,
            "CSV and JSON match."
            if csv_ok else "CSV and JSON promo IDs differ.",
        ))

        quality_file = export_dir / "quality_check.json"
        quality_ok = False
        if quality_file.exists():
            try:
                on_disk = json.loads(
                    quality_file.read_text(encoding="utf-8")
                )
                quality_ok = (
                    int(on_disk.get("total_candidates", -1)) == len(ranked)
                    and int(on_disk.get("episodes_covered", -1))
                    == len(ranked_episode_numbers)
                )
            except (OSError, ValueError, TypeError):
                quality_ok = False
        checks.append(_check(
            "quality_report_present",
            "The quality report exists and matches the run.",
            quality_ok,
            "Quality report matches."
            if quality_ok else "Quality report missing or inconsistent.",
        ))

    failed = [check for check in checks if not check["passed"]]
    return {
        "generated_from": "ranked_promos.json + parsed_screenplays.json",
        "total_checks": len(checks),
        "passed_checks": len(checks) - len(failed),
        "failed_checks": len(failed),
        "status": "PASS" if not failed else "FAIL",
        "counts": {
            "candidates": len(ranked),
            "episodes": len(ranked_episode_numbers),
            "parsed_episodes": len(episode_numbers),
            "duration_min": min(durations) if durations else 0,
            "duration_max": max(durations) if durations else 0,
            "hooks_beyond_3_seconds": len(late_hooks),
            "clips_ending_mid_dialogue": len(mid_dialogue),
        },
        "checks": checks,
    }


def write_output_audit(audit: dict, output_dir: str | Path) -> tuple[str, str]:
    """Write JSON and Markdown copies of the audit."""

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "requirements_check.json"
    md_path = output_dir / "requirements_check.md"

    json_path.write_text(
        json.dumps(audit, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    lines = [
        "# Problem 1 requirements check",
        "",
        f"**Status: {audit['status']}** — "
        f"{audit['passed_checks']}/{audit['total_checks']} checks passed.",
        "",
        "| Check | Requirement | Result | Detail |",
        "|---|---|---|---|",
    ]
    for check in audit["checks"]:
        result = "PASS" if check["passed"] else "FAIL"
        detail = str(check["detail"]).replace("|", "\\|")
        lines.append(
            f"| {check['id']} | {check['requirement']} | {result} | {detail} |"
        )
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")

    return str(json_path), str(md_path)
