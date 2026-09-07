import sqlite3
import tempfile
import unittest
from contextlib import closing, contextmanager
from pathlib import Path
from unittest.mock import patch

import app as application
import services.sqlite as sqlite_service
from models import EventOdds, GameEvent, Pick
from optimizer import ALGORITHM_DISPATCH
from services.sqlite import save_odds_data, setup_database

# Fixed UTC strings keep the point-in-time cases deterministic and serializable.
REFRESH_ONE = "2025-09-01T12:00:00+00:00"
REFRESH_TWO = "2025-09-02T12:00:00+00:00"
KICKOFF = "2025-09-03T12:00:00+00:00"
AFTER_KICKOFF = "2025-09-03T12:01:00+00:00"
CORRECTION = "2025-09-08T12:00:00+00:00"


@contextmanager
def temporary_database():
    with tempfile.TemporaryDirectory() as directory:
        yield Path(directory) / "odds.db"


def fixture_event(
    event_id: int,
    season_year: int,
    week: int,
    spread: float,
    away_team: str,
    home_team: str,
) -> EventOdds:
    return EventOdds(
        event_id=event_id,
        season_year=season_year,
        week=week,
        short_name=f"{away_team} @ {home_team}",
        spread=spread,
    )


def complete_snapshot(season_year: int = 2025) -> list[EventOdds]:
    event_id = (season_year - 2020) * 1000
    return [
        fixture_event(event_id + 1, season_year, 1, 3.0, "SEA", "DEN"),
        fixture_event(event_id + 2, season_year, 2, 4.5, "KC", "BUF"),
        fixture_event(event_id + 3, season_year, 3, 2.0, "MIA", "NYJ"),
    ]


def database_rows(
    db_path: Path, query: str, parameters: tuple[object, ...] = ()
) -> list[tuple[object, ...]]:
    with closing(sqlite3.connect(db_path)) as connection:
        return connection.execute(query, parameters).fetchall()


def required_sqlite_function(test_case: unittest.TestCase, name: str, owner: str):
    function = getattr(sqlite_service, name, None)
    if function is None:
        test_case.fail(
            f"Expected failure owned by {owner}: "
            f"services.sqlite.{name} is not implemented yet"
        )
    return function


class PointInTimeContractTests(unittest.TestCase):
    def test_refresh_updates_current_state_without_schedule_history_copies(self):
        # BACK-02 owns current-state persistence.
        save_current_state = required_sqlite_function(
            self, "save_current_state", "BACK-02"
        )
        fetch_current_state = required_sqlite_function(
            self, "fetch_current_state", "BACK-02"
        )

        with temporary_database() as db_path:
            setup_database(db_path)
            first_rows = complete_snapshot()
            replacement = [
                fixture_event(101, 2025, 1, 6.0, "SEA", "DEN"),
                *first_rows[1:],
            ]
            save_current_state(
                first_rows,
                observed_at=REFRESH_ONE,
                refresh_id="refresh-1",
                db_name=db_path,
            )
            save_current_state(
                replacement,
                observed_at=REFRESH_TWO,
                refresh_id="refresh-2",
                db_name=db_path,
            )

            current_rows = fetch_current_state(2025, db_name=db_path)
            self.assertEqual(
                [(event.event_id, event.spread) for event in current_rows],
                [(event.event_id, event.spread) for event in replacement],
            )
            self.assertEqual(
                database_rows(db_path, "SELECT count(*) FROM current_game_state")[0][0],
                len(replacement),
            )
            self.assertEqual(
                database_rows(db_path, "SELECT count(*) FROM decision_snapshots")[0][0],
                0,
            )

    def test_first_pick_freezes_one_complete_snapshot_for_the_season_week(self):
        # Expected failure: BACK-04 owns first-pick snapshot creation and reuse.
        append_pick_event = required_sqlite_function(
            self, "append_pick_event", "BACK-04"
        )

        with temporary_database() as db_path:
            setup_database(db_path)
            original_rows = complete_snapshot()
            save_odds_data(original_rows, db_path)
            append_pick_event(
                season_year=2025,
                week=1,
                action="set",
                pick=Pick("SEA", 1, 3.0),
                recorded_at=REFRESH_ONE,
                db_name=db_path,
            )
            append_pick_event(
                season_year=2025,
                week=1,
                action="set",
                pick=Pick("DEN", 1, 6.0),
                recorded_at=REFRESH_TWO,
                db_name=db_path,
            )

            snapshot_id = database_rows(
                db_path,
                "SELECT snapshot_id FROM decision_snapshots "
                "WHERE season_year = ? AND survivor_week = ?",
                (2025, 1),
            )[0][0]
            snapshot_rows = database_rows(
                db_path,
                "SELECT event_id, season_year, week, short_name, spread "
                "FROM decision_snapshot_games WHERE snapshot_id = ? "
                "ORDER BY event_id",
                (snapshot_id,),
            )
            self.assertEqual(
                database_rows(
                    db_path,
                    "SELECT count(*) FROM decision_snapshots "
                    "WHERE season_year = ? AND survivor_week = ?",
                    (2025, 1),
                )[0][0],
                1,
            )
            self.assertEqual(
                snapshot_rows,
                [
                    (
                        event.event_id,
                        event.season_year,
                        event.week,
                        event.short_name,
                        event.spread,
                    )
                    for event in original_rows
                ],
            )

    def test_replacement_and_clear_reuse_an_immutable_snapshot(self):
        # Expected failure: BACK-04 owns pick-event history and snapshot immutability.
        append_pick_event = required_sqlite_function(
            self, "append_pick_event", "BACK-04"
        )

        with temporary_database() as db_path:
            setup_database(db_path)
            original_rows = complete_snapshot()
            save_odds_data(original_rows, db_path)
            append_pick_event(
                season_year=2025,
                week=1,
                action="set",
                pick=Pick("SEA", 1, 3.0),
                recorded_at=REFRESH_ONE,
                db_name=db_path,
            )
            save_odds_data(
                [
                    fixture_event(101, 2025, 1, 9.0, "SEA", "DEN"),
                    *original_rows[1:],
                ],
                db_path,
            )
            append_pick_event(
                season_year=2025,
                week=1,
                action="set",
                pick=Pick("DEN", 1, 9.0),
                recorded_at=REFRESH_TWO,
                db_name=db_path,
            )
            append_pick_event(
                season_year=2025,
                week=1,
                action="clear",
                pick=None,
                recorded_at=CORRECTION,
                db_name=db_path,
            )

            snapshot_id = database_rows(
                db_path,
                "SELECT snapshot_id FROM decision_snapshots "
                "WHERE season_year = ? AND survivor_week = ?",
                (2025, 1),
            )[0][0]
            self.assertEqual(
                database_rows(
                    db_path,
                    "SELECT count(*) FROM decision_snapshots "
                    "WHERE season_year = ? AND survivor_week = ?",
                    (2025, 1),
                )[0][0],
                1,
            )
            self.assertEqual(
                database_rows(
                    db_path,
                    "SELECT event_id, spread FROM decision_snapshot_games "
                    "WHERE snapshot_id = ? ORDER BY event_id",
                    (snapshot_id,),
                ),
                [(event.event_id, event.spread) for event in original_rows],
            )
            self.assertEqual(
                database_rows(
                    db_path,
                    "SELECT action FROM pick_events "
                    "WHERE season_year = ? AND week = ? ORDER BY recorded_at",
                    (2025, 1),
                ),
                [("set",), ("set",), ("clear",)],
            )

    def test_every_algorithm_comparison_receives_the_same_snapshot_rows(self):
        snapshot_rows = complete_snapshot()
        received_rows: list[tuple[EventOdds, ...]] = []

        def capture_rows(events, split_week, prior_picks):
            del split_week, prior_picks
            received_rows.append(tuple(events))
            return []

        dispatch = {
            slug: (name, capture_rows) for slug, (name, _) in ALGORITHM_DISPATCH.items()
        }
        with (
            patch.object(application, "ALGORITHM_DISPATCH", dispatch),
            patch.object(application, "fetch_odds_data", return_value=snapshot_rows),
            patch.object(
                application,
                "load_config",
                return_value={
                    "picks": [],
                    "current_week": 1,
                    "split_week": 10,
                    "algorithm": "best-spread",
                },
            ),
        ):
            for slug in dispatch:
                application.optimize_single_algorithm(1, slug, year=2025)

        self.assertEqual(
            received_rows,
            [tuple(snapshot_rows)] * len(ALGORITHM_DISPATCH),
        )

    def test_failed_refresh_does_not_forward_events_to_storage(self):
        with (
            patch.object(application, "load_config", return_value={"current_week": 3}),
            patch.object(
                application, "fetch_events", side_effect=RuntimeError("fixture failure")
            ),
            patch.object(application, "apply_refresh") as apply,
            self.assertRaisesRegex(RuntimeError, "fixture failure"),
        ):
            application.refresh_data(2025)

        apply.assert_called_once()
        self.assertEqual(apply.call_args.kwargs["status"], "failed")

    def test_closing_line_accepts_newer_pre_kickoff_observations_only(self):
        """BACK-02 owns closing-line observation rules."""
        update_closing_line = required_sqlite_function(
            self, "update_closing_line", "BACK-02"
        )

        with temporary_database() as db_path:
            setup_database(db_path)
            update_closing_line(
                event_id=101,
                spread=3.0,
                observed_at=REFRESH_ONE,
                kickoff_at=KICKOFF,
                db_name=db_path,
            )
            update_closing_line(
                event_id=101,
                spread=4.0,
                observed_at=REFRESH_ONE,
                kickoff_at=KICKOFF,
                db_name=db_path,
            )
            update_closing_line(
                event_id=101,
                spread=2.5,
                observed_at=REFRESH_TWO,
                kickoff_at=KICKOFF,
                db_name=db_path,
            )
            update_closing_line(
                event_id=101,
                spread=1.0,
                observed_at=AFTER_KICKOFF,
                kickoff_at=KICKOFF,
                db_name=db_path,
            )

            self.assertEqual(
                database_rows(
                    db_path,
                    "SELECT spread, observed_at FROM closing_lines WHERE event_id = ?",
                    (101,),
                ),
                [(2.5, REFRESH_TWO)],
            )

    def test_failed_refresh_preserves_current_state_and_closing_candidate(self):
        apply_refresh = required_sqlite_function(self, "apply_refresh", "BACK-03")

        with temporary_database() as db_path:
            setup_database(db_path)
            apply_refresh(
                season_year=2025,
                events=[
                    GameEvent(
                        event_id=101,
                        season_year=2025,
                        week=1,
                        short_name="SEA @ DEN",
                        spread=3.0,
                        kickoff_at=KICKOFF,
                    )
                ],
                observed_at=REFRESH_ONE,
                status="complete",
                db_name=db_path,
            )
            apply_refresh(
                season_year=2025,
                events=[
                    GameEvent(
                        event_id=101,
                        season_year=2025,
                        week=1,
                        short_name="SEA @ DEN",
                        spread=9.0,
                        kickoff_at=KICKOFF,
                    )
                ],
                observed_at=REFRESH_TWO,
                status="failed",
                error="fixture failure",
                db_name=db_path,
            )

            self.assertEqual(
                database_rows(
                    db_path,
                    "SELECT spread FROM current_game_state WHERE event_id = ?",
                    (101,),
                ),
                [(3.0,)],
            )
            self.assertEqual(
                database_rows(
                    db_path,
                    "SELECT spread FROM closing_lines WHERE event_id = ?",
                    (101,),
                ),
                [(3.0,)],
            )

    def test_pick_history_is_isolated_by_season(self):
        # Expected failure: BACK-04 owns season-aware pick events and reads.
        append_pick_event = required_sqlite_function(
            self, "append_pick_event", "BACK-04"
        )
        fetch_current_picks = required_sqlite_function(
            self, "fetch_current_picks", "BACK-04"
        )

        with temporary_database() as db_path:
            setup_database(db_path)
            save_odds_data(
                [*complete_snapshot(2024), *complete_snapshot(2025)], db_path
            )
            append_pick_event(
                season_year=2024,
                week=1,
                action="set",
                pick=Pick("SEA", 1, 3.0),
                recorded_at=REFRESH_ONE,
                db_name=db_path,
            )
            append_pick_event(
                season_year=2025,
                week=1,
                action="set",
                pick=Pick("KC", 1, 4.5),
                recorded_at=REFRESH_ONE,
                db_name=db_path,
            )

            self.assertEqual(
                fetch_current_picks(2024, db_name=db_path), [Pick("SEA", 1, 3.0)]
            )
            self.assertEqual(
                fetch_current_picks(2025, db_name=db_path), [Pick("KC", 1, 4.5)]
            )

    def test_set_replacement_and_clear_reconstruct_pick_history(self):
        # Expected failure: BACK-04 owns event-ledger reconstruction.
        append_pick_event = required_sqlite_function(
            self, "append_pick_event", "BACK-04"
        )
        fetch_current_picks = required_sqlite_function(
            self, "fetch_current_picks", "BACK-04"
        )

        with temporary_database() as db_path:
            setup_database(db_path)
            save_odds_data(complete_snapshot(), db_path)
            append_pick_event(
                season_year=2025,
                week=1,
                action="set",
                pick=Pick("SEA", 1, 3.0),
                recorded_at=REFRESH_ONE,
                db_name=db_path,
            )
            self.assertEqual(
                fetch_current_picks(2025, db_name=db_path), [Pick("SEA", 1, 3.0)]
            )
            append_pick_event(
                season_year=2025,
                week=1,
                action="set",
                pick=Pick("DEN", 1, 6.0),
                recorded_at=REFRESH_TWO,
                db_name=db_path,
            )
            self.assertEqual(
                fetch_current_picks(2025, db_name=db_path), [Pick("DEN", 1, 6.0)]
            )
            append_pick_event(
                season_year=2025,
                week=1,
                action="clear",
                pick=None,
                recorded_at=CORRECTION,
                db_name=db_path,
            )
            self.assertEqual(fetch_current_picks(2025, db_name=db_path), [])

    def test_clear_all_appends_clear_events_for_active_weeks(self):
        # Expected failure: BACK-04 owns clear-all history reconstruction.
        append_pick_event = required_sqlite_function(
            self, "append_pick_event", "BACK-04"
        )
        clear_all_pick_events = required_sqlite_function(
            self, "clear_all_pick_events", "BACK-04"
        )
        fetch_current_picks = required_sqlite_function(
            self, "fetch_current_picks", "BACK-04"
        )

        with temporary_database() as db_path:
            setup_database(db_path)
            save_odds_data(complete_snapshot(), db_path)
            for week, pick in ((1, Pick("SEA", 1, 3.0)), (2, Pick("KC", 2, 4.5))):
                append_pick_event(
                    season_year=2025,
                    week=week,
                    action="set",
                    pick=pick,
                    recorded_at=REFRESH_ONE,
                    db_name=db_path,
                )

            clear_all_pick_events(
                season_year=2025,
                recorded_at=CORRECTION,
                db_name=db_path,
            )

            self.assertEqual(fetch_current_picks(2025, db_name=db_path), [])
            self.assertEqual(
                database_rows(
                    db_path,
                    "SELECT action, week FROM pick_events "
                    "WHERE season_year = ? AND action = 'clear' "
                    "ORDER BY week",
                    (2025,),
                ),
                [("clear", 1), ("clear", 2)],
            )

    def test_optimization_run_identifies_snapshot_and_output_picks(self):
        # Expected failure: BACK-05 owns optimization-run provenance.
        save_optimization_run = required_sqlite_function(
            self, "save_optimization_run", "BACK-05"
        )
        fetch_optimization_run = required_sqlite_function(
            self, "fetch_optimization_run", "BACK-05"
        )

        with temporary_database() as db_path:
            setup_database(db_path)
            snapshot_id = sqlite_service.freeze_decision_snapshot(
                season_year=2025,
                survivor_week=1,
                decision_at=REFRESH_ONE,
                db_name=db_path,
            )
            run_id = save_optimization_run(
                season_year=2025,
                algorithm="best-spread",
                split_week=2,
                current_week=1,
                parameters={"fixture": True},
                code_revision="fixture-revision",
                generated_at=REFRESH_TWO,
                decision_snapshot_id=snapshot_id,
                recommendations=[Pick("SEA", 1, 3.0), Pick("KC", 2, 4.5)],
                db_name=db_path,
            )

            run = fetch_optimization_run(run_id, db_name=db_path)
            self.assertEqual(run["decision_snapshot_id"], snapshot_id)
            self.assertEqual(
                run["recommendations"],
                [Pick("SEA", 1, 3.0), Pick("KC", 2, 4.5)],
            )

    def test_final_result_corrections_keep_observed_and_corrected_timestamps(self):
        # BACK-02 owns final-result persistence and corrections.
        upsert_game_result = required_sqlite_function(
            self, "upsert_game_result", "BACK-02"
        )
        fetch_game_result = required_sqlite_function(
            self, "fetch_game_result", "BACK-02"
        )

        with temporary_database() as db_path:
            setup_database(db_path)
            upsert_game_result(
                event_id=101,
                status="final",
                home_score=24,
                away_score=17,
                observed_at=REFRESH_TWO,
                corrected_at=None,
                db_name=db_path,
            )
            upsert_game_result(
                event_id=101,
                status="final",
                home_score=27,
                away_score=17,
                observed_at=CORRECTION,
                corrected_at=CORRECTION,
                db_name=db_path,
            )

            result = fetch_game_result(101, db_name=db_path)
            self.assertEqual(result["home_score"], 27)
            self.assertEqual(result["away_score"], 17)
            self.assertEqual(result["observed_at"], CORRECTION)
            self.assertEqual(result["corrected_at"], CORRECTION)


if __name__ == "__main__":
    unittest.main()
