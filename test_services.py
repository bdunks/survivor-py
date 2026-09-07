import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import Mock, patch

import app as application
from models import EventOdds
from services.cbssports import fetch_soup, parse_events
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


class AppDataFlowTests(unittest.TestCase):
    def test_refresh_and_events_use_functional_services(self):
        event = fixture_event(1, 2025, 4, 3.0)
        with (
            patch.object(application, "load_config", return_value={"current_week": 4}),
            patch.object(application, "fetch_events", return_value=[event]) as fetch,
            patch.object(application, "save_odds_data") as save,
        ):
            refresh_result = application.refresh_data(2025)

        fetch.assert_called_once_with(2025, starting_week=4)
        save.assert_called_once_with([event])
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
