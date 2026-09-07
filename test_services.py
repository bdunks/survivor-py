import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import Mock, patch

import app as application
import services.sqlite as sqlite_service
from models import EventOdds, GameEvent
from services.cbssports import fetch_events, fetch_soup, parse_events
from services.sqlite import fetch_odds_data, save_odds_data, setup_database

FIXTURE_HTML = """
<div class="single-score-card" id="scorecard-101" data-abbrev="nfl_101_SEA @ DEN">
  <td class="in-progress-odds-home">PK</td>
</div>
<div class="single-score-card" id="scorecard-102" data-abbrev="nfl_102_KC @ BUF">
  <td class="in-progress-odds-home">-3.5</td>
</div>
<div class="single-score-card" id="scorecard-103" data-abbrev="nfl_103_MIA @ NYJ"></div>
<div class="single-score-card" id="scorecard-104" data-abbrev="nfl_104_DAL @ PHI">
  <td class="in-progress-odds-home">not-a-spread</td>
</div>
<div class="single-score-card" data-abbrev="nfl_105_MIN @ GB">
  <td class="in-progress-odds-home">2.0</td>
</div>
<div class="single-score-card" id="scorecard-106">
  <td class="in-progress-odds-home">2.0</td>
</div>
<div class="single-score-card" id="scorecard-107" data-abbrev="nfl_107_not a matchup">
  <td class="in-progress-odds-home">2.0</td>
</div>
"""

RICH_FIXTURE_HTML = """
<div class="single-score-card" id="scorecard-201"
     data-abbrev="nfl_201_SEA @ DEN"
     data-kickoff="2025-09-07T17:00:00Z"
     data-status="Scheduled"
     data-home-moneyline="-150"
     data-away-moneyline="+130"
     data-total="O 44.5">
  <td class="in-progress-odds-home">-3.5</td>
</div>
<div class="single-score-card" id="scorecard-202"
     data-abbrev="nfl_202_KC @ BUF"
     data-kickoff="2025-09-08T00:20:00Z"
     data-status="Final"
     data-home-score="24"
     data-away-score="17">
  <td class="in-progress-odds-home">PK</td>
</div>
"""


def fixture_event(
    event_id: int, season_year: int, week: int, spread: float
) -> EventOdds:
    return EventOdds(
        event_id=event_id,
        season_year=season_year,
        week=week,
        short_name="SEA @ DEN",
        spread=spread,
    )


class ScraperTests(unittest.TestCase):
    def test_fixture_parser_keeps_pk_and_numeric_spreads_only(self):
        events = parse_events(FIXTURE_HTML, season_year=2025, week_number=4)

        self.assertEqual(
            [(event.event_id, event.short_name, event.spread) for event in events],
            [(101, "SEA @ DEN", 0.0), (102, "KC @ BUF", -3.5)],
        )
        self.assertTrue(all(event.away_team != "UNK" for event in events))
        self.assertTrue(all(event.home_team != "UNK" for event in events))

    def test_parser_keeps_schedule_and_final_metadata(self):
        events = parse_events(RICH_FIXTURE_HTML, season_year=2025, week_number=1)
        self.assertEqual(len(events), 2)
        scheduled, final = events
        self.assertEqual(scheduled.kickoff_at, "2025-09-07T17:00:00+00:00")
        self.assertEqual(scheduled.game_status, "Scheduled")
        self.assertEqual(scheduled.home_moneyline, -150)
        self.assertEqual(scheduled.away_moneyline, 130)
        self.assertEqual(scheduled.total, 44.5)
        self.assertIsNone(scheduled.home_score)
        self.assertEqual(final.spread, 0.0)
        self.assertEqual(final.game_status, "Final")
        self.assertEqual((final.home_score, final.away_score), (24, 17))

    def test_fetch_events_reports_parser_failures(self):
        soup = Mock()
        soup._raw_content = b"parser fixture"
        with (
            patch("services.cbssports.fetch_soup", return_value=soup),
            patch(
                "services.cbssports.parse_events",
                side_effect=ValueError("parser changed"),
            ),
        ):
            result = fetch_events(2025, starting_week=18)

        self.assertEqual(result.successful_weeks, [])
        self.assertEqual(result.failed_weeks, [18])
        self.assertEqual(result.raw_failures[0]["payload"], b"parser fixture")

    def test_fetch_soup_uses_timeout_and_checks_http_status(self):
        response = Mock(content=FIXTURE_HTML.encode())
        with patch("services.cbssports.requests.get", return_value=response) as get:
            soup = fetch_soup("https://example.test/week")

        get.assert_called_once_with("https://example.test/week", timeout=30)
        response.raise_for_status.assert_called_once_with()
        self.assertEqual(len(soup.find_all("div", class_="single-score-card")), 7)


class DatabaseTests(unittest.TestCase):
    def test_setup_save_upsert_fetch_by_season_and_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "odds.db"
            setup_database(db_path)

            with closing(sqlite3.connect(db_path)) as connection:
                columns = [
                    row[1]
                    for row in connection.execute("PRAGMA table_info(averaged_odds)")
                ]
                trigger_count = connection.execute(
                    "SELECT count(*) FROM sqlite_master "
                    "WHERE type = 'trigger' AND name = 'update_averaged_odds'"
                ).fetchone()[0]

            self.assertEqual(
                columns,
                [
                    "event_id",
                    "season_year",
                    "week",
                    "home_team",
                    "away_team",
                    "short_name",
                    "spread",
                ],
            )
            self.assertEqual(trigger_count, 0)

            save_odds_data([fixture_event(1, 2025, 1, 3.0)], db_path)
            save_odds_data(
                [
                    fixture_event(1, 2025, 1, 7.5),
                    fixture_event(2, 2024, 1, 4.0),
                ],
                db_path,
            )

            events = fetch_odds_data(2025, db_path)
            self.assertEqual(
                [(event.event_id, event.spread) for event in events], [(1, 7.5)]
            )

            db_path.unlink()
            self.assertFalse(db_path.exists())

    def test_application_connections_enforce_foreign_keys_and_import_legacy_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "legacy.db"
            save_odds_data([fixture_event(1, 2025, 1, 3.0)], db_path)
            setup_database(db_path)
            setup_database(db_path)

            with sqlite_service._connection(db_path) as connection:
                self.assertEqual(
                    connection.execute("PRAGMA foreign_keys").fetchone()[0], 1
                )
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        """
                        INSERT INTO decision_snapshot_games (
                            snapshot_id, event_id, season_year, week, home_team,
                            away_team, short_name, spread
                        ) VALUES (999, 2, 2025, 1, 'SEA', 'DEN', 'SEA @ DEN', 3.0)
                        """
                    )

            with closing(sqlite3.connect(db_path)) as connection:
                self.assertEqual(
                    connection.execute(
                        "SELECT event_id, is_legacy FROM current_game_state"
                    ).fetchall(),
                    [(1, 1)],
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT count(*) FROM decision_snapshots"
                    ).fetchone()[0],
                    0,
                )

    def test_setup_keeps_legacy_columns_but_drops_legacy_trigger(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "legacy.db"
            with closing(sqlite3.connect(db_path)) as connection:
                connection.execute(
                    """
                    CREATE TABLE averaged_odds (
                        event_id INTEGER PRIMARY KEY,
                        season_year INTEGER,
                        week INTEGER,
                        home_team TEXT,
                        away_team TEXT,
                        short_name TEXT,
                        spread REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TRIGGER update_averaged_odds
                    AFTER UPDATE ON averaged_odds
                    FOR EACH ROW
                    BEGIN
                        UPDATE averaged_odds
                        SET updated_at = CURRENT_TIMESTAMP
                        WHERE event_id = OLD.event_id;
                    END
                    """
                )
                connection.commit()

            setup_database(db_path)
            with closing(sqlite3.connect(db_path)) as connection:
                columns = [
                    row[1]
                    for row in connection.execute("PRAGMA table_info(averaged_odds)")
                ]
                trigger_count = connection.execute(
                    "SELECT count(*) FROM sqlite_master "
                    "WHERE type = 'trigger' AND name = 'update_averaged_odds'"
                ).fetchone()[0]

            self.assertIn("created_at", columns)
            self.assertIn("updated_at", columns)
            self.assertEqual(trigger_count, 0)

    def test_current_state_freezes_an_immutable_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "snapshot.db"
            original = [
                fixture_event(1, 2025, 1, 3.0),
                fixture_event(2, 2025, 2, 4.5),
            ]
            replacement = [
                fixture_event(1, 2025, 1, 7.0),
                original[1],
            ]
            sqlite_service.save_current_state(
                original,
                observed_at="2025-09-01T12:00:00+00:00",
                refresh_id="refresh-1",
                db_name=db_path,
            )
            snapshot_id = sqlite_service.freeze_decision_snapshot(
                2025,
                1,
                "2025-09-01T13:00:00+00:00",
                db_name=db_path,
            )
            sqlite_service.save_current_state(
                replacement,
                observed_at="2025-09-02T12:00:00+00:00",
                refresh_id="refresh-2",
                db_name=db_path,
            )
            self.assertEqual(
                sqlite_service.freeze_decision_snapshot(
                    2025,
                    1,
                    "2025-09-03T13:00:00+00:00",
                    db_name=db_path,
                ),
                snapshot_id,
            )
            self.assertEqual(
                [
                    (event.event_id, event.spread)
                    for event in sqlite_service.fetch_decision_snapshot(
                        2025, 1, db_path
                    )
                ],
                [(event.event_id, event.spread) for event in original],
            )

    def test_partial_refresh_preserves_failed_week_and_updates_results(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "refresh.db"
            kickoff = "2025-09-10T12:00:00+00:00"
            first = GameEvent(
                event_id=1,
                season_year=2025,
                week=1,
                short_name="SEA @ DEN",
                spread=-3.0,
                kickoff_at=kickoff,
                game_status="Scheduled",
            )
            second = GameEvent(
                event_id=2,
                season_year=2025,
                week=2,
                short_name="KC @ BUF",
                spread=-2.5,
                kickoff_at=kickoff,
                game_status="Final",
                home_score=24,
                away_score=17,
            )
            sqlite_service.apply_refresh(
                2025,
                [first, second],
                "2025-09-09T12:00:00+00:00",
                status="partial",
                requested_weeks=[1, 2],
                successful_weeks=[1, 2],
                db_name=db_path,
            )
            failed_week = GameEvent(
                event_id=1,
                season_year=2025,
                week=1,
                short_name="SEA @ DEN",
                spread=9.0,
                kickoff_at=kickoff,
                game_status="Final",
                home_score=7,
                away_score=31,
            )
            result = sqlite_service.apply_refresh(
                2025,
                [failed_week, second],
                "2025-09-09T13:00:00+00:00",
                status="partial",
                requested_weeks=[1, 2],
                successful_weeks=[2],
                failed_weeks=[1],
                error="week 1 failed",
                source_urls=["https://example.test/week-1"],
                db_name=db_path,
            )
            self.assertEqual(result["failed_weeks"], [1])
            with closing(sqlite3.connect(db_path)) as connection:
                refresh = connection.execute(
                    "SELECT source_urls, status, error FROM refresh_runs "
                    "ORDER BY rowid DESC LIMIT 1"
                ).fetchone()
            self.assertEqual(refresh[0], '["https://example.test/week-1"]')
            self.assertEqual(refresh[1], "partial")
            self.assertEqual(refresh[2], "week 1 failed")
            self.assertEqual(
                [
                    (event.event_id, event.spread)
                    for event in sqlite_service.fetch_current_state(2025, db_path)
                ],
                [(1, -3.0), (2, -2.5)],
            )
            game_result = sqlite_service.fetch_game_result(2, db_path)
            assert game_result is not None
            self.assertEqual(game_result["home_score"], 24)
            self.assertIsNone(sqlite_service.fetch_game_result(1, db_path))
            with closing(sqlite3.connect(db_path)) as connection:
                self.assertEqual(
                    connection.execute(
                        "SELECT count(*) FROM decision_snapshots"
                    ).fetchone()[0],
                    0,
                )


class AppDataFlowTests(unittest.TestCase):
    def test_refresh_and_events_use_functional_services(self):
        event = fixture_event(1, 2025, 4, 3.0)
        with (
            patch.object(application, "load_config", return_value={"current_week": 4}),
            patch.object(application, "fetch_events", return_value=[event]) as fetch,
            patch.object(
                application,
                "apply_refresh",
                return_value={"parsed_count": 1},
            ) as apply,
        ):
            refresh_result = application.refresh_data(2025)

        fetch.assert_called_once_with(2025, starting_week=3)
        apply.assert_called_once()
        self.assertEqual(apply.call_args.args[:2], (2025, [event]))
        self.assertEqual(apply.call_args.kwargs["requested_weeks"], list(range(3, 19)))
        self.assertEqual(refresh_result["events_count"], 1)

        with patch.object(
            application, "fetch_odds_data", return_value=[event]
        ) as fetch:
            responses = application.get_events(2025)

        fetch.assert_called_once_with(2025)
        self.assertEqual(responses[0].event_id, 1)
        self.assertEqual(responses[0].favored_team, "SEA")


if __name__ == "__main__":
    unittest.main()
