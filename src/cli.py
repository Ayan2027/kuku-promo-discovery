"""End-to-end command line interface.

Examples
--------
Run the real pack from ZIP to ranked exports:

    python -m src.cli run --zip data/input/screenplays.zip --provider local --force

Re-rank already generated candidates:

    python -m src.cli rank

Build and run the public synthetic demo:

    python -m src.cli demo
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from src.config import settings
from src.demo_data import write_demo_zip
from src.discovery.promo_discovery import discover_all_promos
from src.discovery.run_batch4 import get_episodes, load_json, run_batch4
from src.ingestion.dataset_processor import process_zip


def _copy_raw_outputs(processed_dir: Path, export_dir: Path, raw_dir: Path):
    raw_dir.mkdir(parents=True, exist_ok=True)

    export_files = [
        "ranked_promos.json",
        "ranked_promos.csv",
        "batch4_summary.json",
        "quality_check.json",
        "quality_check.md",
        "rejected_candidates.json",
    ]
    processed_files = [
        "discovery_summary.json",
        "dataset_summary.json",
        "promo_analysis_metadata.json",
        "rejected_windows.json",
        "parsing_warnings.json",
    ]

    copied = []
    for name in export_files:
        source = export_dir / name
        if source.exists():
            shutil.copy2(source, raw_dir / name)
            copied.append(name)
    for name in processed_files:
        source = processed_dir / name
        if source.exists():
            shutil.copy2(source, raw_dir / name)
            copied.append(name)

    readme = raw_dir / "README.md"
    readme.write_text(
        "# Raw outputs\n\n"
        "These are the unedited machine outputs from one end-to-end run.\n"
        "No input screenplays are included in this folder.\n\n"
        f"- Packaged at: {datetime.now(timezone.utc).isoformat()}\n"
        f"- Files: {', '.join(copied)}\n\n"
        "`ranked_promos.json` / `.csv` are the ranked output. "
        "`quality_check.json` / `.md` are the honest failure analysis. "
        "`rejected_candidates.json` contains overlapping duplicates that "
        "were removed from the ranked list.\n",
        encoding="utf-8",
    )
    return copied


def cmd_run(args):
    settings.PROMO_MIN_SCORE = args.min_score

    zip_path = Path(args.zip)
    input_dir = Path(args.input_dir or settings.INPUT_DIR)
    processed_dir = Path(args.processed_dir or settings.PROCESSED_DIR)
    cache_dir = Path(args.cache_dir or settings.CACHE_DIR / "promo_discovery")
    export_dir = Path(args.export_dir or settings.EXPORT_DIR)

    print("[1/4] Ingesting", zip_path)
    episodes, summary, warnings = process_zip(
        zip_path=zip_path,
        input_dir=input_dir,
        processed_dir=processed_dir,
    )
    print(
        f"      parsed {summary.processed_episodes}/{summary.total_episodes} "
        f"episodes, {summary.total_segments} segments, "
        f"{len(warnings)} warnings"
    )

    print("[2/4] Discovering candidates")
    discover_all_promos(
        episodes,
        force=args.force,
        processed_dir=processed_dir,
        cache_dir=cache_dir,
        provider_mode=args.provider,
        max_episodes=args.max_episodes,
        max_windows=args.max_windows,
    )

    print("[3/4] Ranking, validating and de-duplicating")
    result = run_batch4(
        processed_dir=processed_dir,
        export_dir=export_dir,
        min_duration=settings.PROMO_MIN_DURATION,
        max_duration=settings.PROMO_MAX_DURATION,
        drop_repetitive=not args.keep_duplicates,
    )

    if args.raw_outputs:
        print("[4/4] Packaging raw outputs")
        copied = _copy_raw_outputs(
            processed_dir,
            export_dir,
            Path(args.raw_outputs),
        )
        print("      copied:", ", ".join(copied))
    else:
        print("[4/4] Skipping raw-output packaging")

    return result


def cmd_rank(args):
    result = run_batch4(
        processed_dir=Path(args.processed_dir or settings.PROCESSED_DIR),
        export_dir=Path(args.export_dir or settings.EXPORT_DIR),
        min_duration=settings.PROMO_MIN_DURATION,
        max_duration=settings.PROMO_MAX_DURATION,
        drop_repetitive=not args.keep_duplicates,
    )
    if args.raw_outputs:
        copied = _copy_raw_outputs(
            Path(args.processed_dir or settings.PROCESSED_DIR),
            Path(args.export_dir or settings.EXPORT_DIR),
            Path(args.raw_outputs),
        )
        print("Copied:", ", ".join(copied))
    return result


def cmd_demo(args):
    root = Path(args.root)
    root.mkdir(parents=True, exist_ok=True)

    zip_path = write_demo_zip(root)
    print("[1/5] Wrote synthetic demo pack:", zip_path)

    input_dir = root / "input"
    processed_dir = root / "processed"
    cache_dir = root / "cache"
    export_dir = root / "exports"

    episodes, summary, _ = process_zip(
        zip_path=zip_path,
        input_dir=input_dir,
        processed_dir=processed_dir,
    )
    print(
        f"[2/5] Parsed {summary.processed_episodes} demo episodes, "
        f"{summary.total_segments} segments"
    )

    discover_all_promos(
        episodes,
        force=True,
        processed_dir=processed_dir,
        cache_dir=cache_dir,
        provider_mode="local",
        max_windows=5,
    )
    print("[3/5] Generated demo candidates")

    result = run_batch4(
        processed_dir=processed_dir,
        export_dir=export_dir,
        min_duration=settings.PROMO_MIN_DURATION,
        max_duration=settings.PROMO_MAX_DURATION,
        drop_repetitive=True,
    )
    print("[4/5] Ranked and exported demo")

    from src.static_prototype import build_static_prototype

    prototype = build_static_prototype(export_dir, Path(args.prototype))
    print("[5/5] Built static prototype:", prototype)

    _copy_raw_outputs(processed_dir, export_dir, Path(args.raw_outputs or "raw_outputs"))
    return result


def build_parser():
    parser = argparse.ArgumentParser(
        prog="python -m src.cli",
        description="Kuku promo discovery pipeline",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="ZIP -> parsed -> candidates -> ranked exports")
    run.add_argument("--zip", required=True)
    run.add_argument("--input-dir")
    run.add_argument("--processed-dir")
    run.add_argument("--cache-dir")
    run.add_argument("--export-dir")
    run.add_argument("--raw-outputs", default="raw_outputs")
    run.add_argument(
        "--provider",
        choices=["auto", "local", "gemini"],
        default="auto",
        help="AI provider. 'local' is fully deterministic and offline.",
    )
    run.add_argument("--max-episodes", type=int)
    run.add_argument("--max-windows", type=int, default=5)
    run.add_argument("--min-score", type=float, default=0.0)
    run.add_argument("--force", action="store_true")
    run.add_argument("--keep-duplicates", action="store_true")
    run.set_defaults(func=cmd_run)

    rank = sub.add_parser("rank", help="Re-rank existing candidates")
    rank.add_argument("--processed-dir")
    rank.add_argument("--export-dir")
    rank.add_argument("--raw-outputs", default="raw_outputs")
    rank.add_argument("--keep-duplicates", action="store_true")
    rank.set_defaults(func=cmd_rank)

    demo = sub.add_parser("demo", help="Build the synthetic public demo")
    demo.add_argument("--root", default="demo")
    demo.add_argument("--prototype", default="prototype/index.html")
    demo.add_argument("--raw-outputs", default="raw_outputs")
    demo.set_defaults(func=cmd_demo)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    main()
