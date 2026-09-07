"""Run every survivor algorithm and write one comparable summary report."""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from backtest import _get_git_revision, run_backtest
from optimizer import ALGORITHM_DISPATCH
from services.sqlite import DEFAULT_DB_NAME

ALGORITHM_ORDER = tuple(ALGORITHM_DISPATCH)


def run_comparison(
    db_name: str | Path,
    season: int,
    split_week: int,
    mode: str = "strict",
) -> dict:
    """Run all retained algorithms with one shared set of backtest inputs."""
    source_revision = _get_git_revision()
    results = []

    for algorithm in ALGORITHM_ORDER:
        _, aggregate = run_backtest(db_name, season, algorithm, split_week, mode)
        result = asdict(aggregate)
        result["source_revision"] = source_revision
        results.append(result)

    return {
        "algorithms": list(ALGORITHM_ORDER),
        "inputs": {
            "database": str(db_name),
            "mode": mode,
            "season": season,
            "split_week": split_week,
        },
        "report": "end-of-season-backtest-comparison",
        "report_version": 1,
        "results": results,
        "source_revision": source_revision,
    }


def write_comparison_json(report: dict, path: Path) -> None:
    """Write a deterministic comparison report."""
    Path(path).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run and compare all survivor pool algorithms"
    )
    parser.add_argument("--db", default=DEFAULT_DB_NAME, help="SQLite database path")
    parser.add_argument("--season", type=int, required=True, help="Season year")
    parser.add_argument(
        "--split-week", type=int, default=18, help="Optimization horizon"
    )
    parser.add_argument(
        "--mode",
        choices=["strict", "degraded"],
        default="strict",
        help="strict: require snapshots; degraded: skip missing",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("backtest-comparison.json"),
        help="Comparison JSON output path",
    )
    args = parser.parse_args()

    try:
        report = run_comparison(args.db, args.season, args.split_week, args.mode)
        write_comparison_json(report, args.output)
        print(
            f"Wrote comparison for {len(ALGORITHM_ORDER)} algorithms to {args.output}"
        )
    except (ValueError, FileNotFoundError, KeyError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
