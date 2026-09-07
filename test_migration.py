import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing, contextmanager
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

import app as application
import backtest
import services.sqlite as sqlite_service
from config_store import load_legacy_picks
from models import EventOdds, Pick
from services.sqlite import LEGACY_SNAPSHOT_TRIGGER, setup_database

MIGRATED_AT = "2025-09-01T12:00:00+00:00"
OBSERVED_AT = "2025-08-31T12:00:00+00:00"


@contextmanager
def temporary_paths():
    previous_directory = os.getcwd()
    with tempfile.TemporaryDirectory() as directory:
        os.chdir(directory)
        try:
            root = Path(directory)
            yield root / "config.json", root / "odds_data.db"
        finally:
            os.chdir(previous_directory)


def fixture_events():
    return [
        EventOdds(101, 2025, 1, "SEA @ DEN", 3.0),
        EventOdds(102, 2025, 2, "KC @ BUF", 4.5),
        EventOdds(103, 2025, 3, "MIA @ NYJ", 2.0),
    ]


class LegacyPickMigrationTests(unittest.TestCase):
    def test_api_migrates_picks_for_explicit_season_and_clears_config_picks(self):
        with temporary_paths() as (config_path, db_path):
            config_path.write_text(
                json.dumps(
                    {
                        "current_week": 4,
                        "picks": [
                            {"team": "SEA", "week": 1, "spread": 3.0},
                            {"team": "KC", "week": 2},
                        ],
                        "algorithm": "back-to-front",
                        "split_week": 14,
                        "unrelated": {"keep": True},
                    }
                ),
                encoding="utf-8",
            )
            sqlite_service.save_current_state(
                fixture_events(),
                observed_at=OBSERVED_AT,
                refresh_id="refresh-1",
                db_name=db_path,
            )

            with patch.object(application, "datetime") as clock:
                clock.now.return_value = datetime.fromisoformat(MIGRATED_AT)
                result = application.migrate_config_picks(2025)

            self.assertEqual(result["season_year"], 2025)
            self.assertEqual(result["legacy_picks_found"], 2)
            self.assertEqual(result["migrated_count"], 2)
            self.assertEqual(
                sqlite_service.fetch_current_picks(2025, db_path),
                [Pick("SEA", 1, 3.0), Pick("KC", 2, 0.0)],
            )
            saved_config = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(saved_config["picks"], [])
            self.assertEqual(saved_config["algorithm"], "back-to-front")
            self.assertEqual(saved_config["split_week"], 14)
            self.assertEqual(saved_config["unrelated"], {"keep": True})

            with closing(sqlite3.connect(db_path)) as connection:
                snapshots = connection.execute(
                    "SELECT snapshot_id, survivor_week, decision_at, trigger "
                    "FROM decision_snapshots ORDER BY survivor_week"
                ).fetchall()
                self.assertEqual(
                    [
                        (week, decision_at, trigger)
                        for _, week, decision_at, trigger in snapshots
                    ],
                    [
                        (1, MIGRATED_AT, LEGACY_SNAPSHOT_TRIGGER),
                        (2, MIGRATED_AT, LEGACY_SNAPSHOT_TRIGGER),
                    ],
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT count(*) FROM decision_snapshot_games WHERE snapshot_id IN (?, ?)",
                        (snapshots[0][0], snapshots[1][0]),
                    ).fetchone()[0],
                    6,
                )

    def test_migration_is_idempotent_and_does_not_duplicate_legacy_events(self):
        with temporary_paths() as (_, db_path):
            setup_database(db_path)
            sqlite_service.save_current_state(
                fixture_events(), observed_at=OBSERVED_AT, db_name=db_path
            )
            picks = [Pick("SEA", 1, 3.0)]

            self.assertEqual(
                sqlite_service.migrate_legacy_pick_events(
                    2025, picks, MIGRATED_AT, db_name=db_path
                ),
                1,
            )
            self.assertEqual(
                sqlite_service.migrate_legacy_pick_events(
                    2025,
                    picks,
                    "2025-09-02T12:00:00+00:00",
                    db_name=db_path,
                ),
                0,
            )
            with closing(sqlite3.connect(db_path)) as connection:
                self.assertEqual(
                    connection.execute("SELECT count(*) FROM pick_events").fetchone()[
                        0
                    ],
                    1,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT count(*) FROM decision_snapshots"
                    ).fetchone()[0],
                    1,
                )

    def test_invalid_or_duplicate_legacy_picks_are_rejected_without_changes(self):
        cases = (
            [{"team": "SEA", "week": 19, "spread": 3.0}],
            [{"team": "SEA", "week": 1, "spread": "bad"}],
            [{"team": "SEA", "week": 1, "spread": float("nan")}],
            [
                {"team": "SEA", "week": 1, "spread": 3.0},
                {"team": "KC", "week": 1, "spread": 4.0},
            ],
            [
                {"team": "SEA", "week": 1, "spread": 3.0},
                {"team": "SEA", "week": 2, "spread": 4.0},
            ],
        )
        for raw_picks in cases:
            with (
                self.subTest(raw_picks=raw_picks),
                temporary_paths() as (config_path, db_path),
            ):
                original = {"picks": raw_picks}
                encoded = json.dumps(original)
                config_path.write_text(encoded, encoding="utf-8")

                with self.assertRaises((TypeError, ValueError)):
                    load_legacy_picks(config_path)

                self.assertEqual(config_path.read_text(encoding="utf-8"), encoded)
                self.assertFalse(db_path.exists())

    def test_migration_requires_explicit_valid_season_and_nfl_teams(self):
        with self.assertRaises(HTTPException) as context:
            application.migrate_config_picks(2019)
        self.assertEqual(context.exception.status_code, 400)

        with temporary_paths() as (config_path, db_path):
            raw = {"picks": [{"team": "XXX", "week": 1, "spread": 3.0}]}
            config_path.write_text(json.dumps(raw), encoding="utf-8")

            with self.assertRaises(HTTPException) as context:
                application.migrate_config_picks(2025)

            self.assertEqual(context.exception.status_code, 400)
            self.assertIn("XXX", str(context.exception.detail))
            self.assertEqual(json.loads(config_path.read_text()), raw)
            self.assertFalse(db_path.exists())

    def test_legacy_snapshots_are_rejected_by_strict_backtests(self):
        with temporary_paths() as (_, db_path):
            setup_database(db_path)
            sqlite_service.save_current_state(
                fixture_events(), observed_at=OBSERVED_AT, db_name=db_path
            )
            sqlite_service.migrate_legacy_pick_events(
                2025, [Pick("SEA", 1, 3.0)], MIGRATED_AT, db_name=db_path
            )

            with self.assertRaisesRegex(ValueError, "Legacy snapshot for 2025 week 1"):
                backtest.run_backtest(db_path, 2025, "best-spread", 18, mode="strict")

            weekly, aggregate = backtest.run_backtest(
                db_path, 2025, "best-spread", 18, mode="degraded"
            )
            self.assertEqual(weekly, [])
            self.assertEqual(aggregate.weeks_survived, 0)


if __name__ == "__main__":
    unittest.main()
