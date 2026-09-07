"""Tests for the end-of-season comparison wrapper."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import call, patch

from backtest import run_backtest
from backtest_compare import (
    ALGORITHM_ORDER,
    run_comparison,
    write_comparison_json,
)
from models import EventOdds
from services.sqlite import (
    freeze_decision_snapshot,
    setup_database,
    upsert_current_game,
    upsert_game_result,
)


def _database_with_one_week() -> Path:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as temporary:
        database = Path(temporary.name)
    setup_database(database)
    event = EventOdds(601, 2025, 1, "KC @ BUF", -3.5)
    upsert_current_game(
        event,
        observed_at="2025-01-01T10:00:00Z",
        db_name=database,
    )
    freeze_decision_snapshot(
        season_year=2025,
        survivor_week=1,
        decision_at="2025-01-01T12:00:00Z",
        trigger="test",
        db_name=database,
    )
    upsert_game_result(
        601,
        "final",
        27,
        24,
        "2025-01-05T20:00:00Z",
        db_name=database,
    )
    return database


class BacktestComparisonTests(unittest.TestCase):
    def test_runs_all_algorithms_with_shared_inputs_and_stable_report(self):
        database = _database_with_one_week()
        self.addCleanup(database.unlink, missing_ok=True)

        with patch("backtest_compare.run_backtest", wraps=run_backtest) as runner:
            report = run_comparison(database, 2025, 17, "degraded")

        self.assertEqual(
            runner.call_args_list,
            [
                call(database, 2025, algorithm, 17, "degraded")
                for algorithm in ALGORITHM_ORDER
            ],
        )
        self.assertEqual(report["algorithms"], list(ALGORITHM_ORDER))
        self.assertEqual(
            [result["algorithm"] for result in report["results"]],
            list(ALGORITHM_ORDER),
        )
        self.assertEqual(
            report["inputs"],
            {
                "database": str(database),
                "mode": "degraded",
                "season": 2025,
                "split_week": 17,
            },
        )
        self.assertEqual(report["report"], "end-of-season-backtest-comparison")
        self.assertEqual(report["report_version"], 1)
        self.assertEqual(
            {result["source_revision"] for result in report["results"]},
            {report["source_revision"]},
        )

        for result in report["results"]:
            self.assertEqual(result["wins"], 1)
            self.assertEqual(result["losses"], 0)
            self.assertEqual(result["ties"], 0)
            self.assertEqual(result["ungraded"], 0)
            self.assertEqual(result["weeks_survived"], 1)
            for metric in (
                "avg_decision_spread",
                "avg_closing_spread",
                "avg_decision_to_closing",
                "avg_selected_vs_best_alternative",
            ):
                self.assertIn(metric, result)

    def test_json_report_is_byte_stable(self):
        database = _database_with_one_week()
        self.addCleanup(database.unlink, missing_ok=True)
        report = run_comparison(database, 2025, 18, "degraded")

        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.json"
            second = Path(directory) / "second.json"
            write_comparison_json(report, first)
            write_comparison_json(report, second)

            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertTrue(first.read_bytes().endswith(b"\n"))
            self.assertEqual(json.loads(first.read_text()), report)

    def test_strict_failure_propagates_before_report_creation(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as temporary:
            database = Path(temporary.name)
        setup_database(database)
        self.addCleanup(database.unlink, missing_ok=True)

        with (
            patch("backtest_compare.run_backtest", wraps=run_backtest) as runner,
            self.assertRaisesRegex(ValueError, "Missing snapshot.*week 1"),
        ):
            run_comparison(database, 2025, 18, "strict")

        self.assertEqual(runner.call_count, 1)
        self.assertEqual(
            runner.call_args, call(database, 2025, ALGORITHM_ORDER[0], 18, "strict")
        )


if __name__ == "__main__":
    unittest.main()
