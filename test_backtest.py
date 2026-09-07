"""Tests for backtest runner."""

import json
import tempfile
import unittest
from pathlib import Path

from backtest import run_backtest, write_csv, write_json
from models import EventOdds, GameEvent
from services.sqlite import (
    freeze_decision_snapshot,
    setup_database,
    update_closing_line,
    upsert_current_game,
    upsert_game_result,
)


def _setup_test_db():
    """Create in-memory test database with minimal fixtures."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as temp:
        db_path = temp.name

    setup_database(db_path)
    return db_path


def _create_snapshot(db_path, season, week, events):
    """Create a decision snapshot with events."""
    # First populate current state
    for event in events:
        upsert_current_game(
            event=event,
            observed_at=f"2025-0{week}-01T10:00:00Z",
            db_name=db_path,
        )
    # Then freeze into snapshot
    return freeze_decision_snapshot(
        season_year=season,
        survivor_week=week,
        decision_at=f"2025-0{week}-01T12:00:00Z",
        trigger="test",
        db_name=db_path,
    )


class BacktestTests(unittest.TestCase):
    def test_strict_mode_fails_on_missing_snapshot(self):
        db = _setup_test_db()
        with self.assertRaisesRegex(ValueError, "Missing snapshot"):
            run_backtest(db, 2025, "best-spread", 18, mode="strict")

    def test_strict_mode_fails_on_missing_later_snapshot(self):
        """Strict mode must fail on missing later snapshot, not silently stop."""
        db = _setup_test_db()

        # Create week 1 and 3, skip week 2
        events_w1 = [EventOdds(101, 2025, 1, "KC @ BUF", -3.5)]
        events_w3 = [EventOdds(301, 2025, 3, "SEA @ DEN", -7.0)]
        _create_snapshot(db, 2025, 1, events_w1)
        _create_snapshot(db, 2025, 3, events_w3)

        upsert_game_result(101, "final", 27, 24, "2025-01-05T20:00:00Z", db_name=db)

        with self.assertRaisesRegex(ValueError, "Missing snapshot.*week 2"):
            run_backtest(db, 2025, "best-spread", 18, mode="strict")

    def test_invalid_mode_rejected(self):
        """Unknown mode values must be rejected explicitly."""
        db = _setup_test_db()
        with self.assertRaisesRegex(ValueError, "Unknown mode"):
            run_backtest(db, 2025, "best-spread", 18, mode="lenient")

    def test_degraded_mode_skips_missing_snapshot(self):
        db = _setup_test_db()
        weekly, aggregate = run_backtest(db, 2025, "best-spread", 18, mode="degraded")
        self.assertEqual(len(weekly), 0)
        self.assertEqual(aggregate.weeks_survived, 0)

    def test_degraded_mode_partial_season(self):
        """Degraded mode runs available weeks and skips missing ones."""
        db = _setup_test_db()

        # Create week 1 and 3, skip week 2
        events_w1 = [EventOdds(101, 2025, 1, "KC @ BUF", -3.5)]
        events_w3 = [EventOdds(301, 2025, 3, "SEA @ DEN", -7.0)]
        _create_snapshot(db, 2025, 1, events_w1)
        _create_snapshot(db, 2025, 3, events_w3)

        upsert_game_result(101, "final", 27, 24, "2025-01-05T20:00:00Z", db_name=db)
        upsert_game_result(301, "final", 21, 20, "2025-01-19T20:00:00Z", db_name=db)

        weekly, aggregate = run_backtest(db, 2025, "best-spread", 18, mode="degraded")

        self.assertEqual(len(weekly), 2)
        self.assertEqual(weekly[0].week, 1)
        self.assertEqual(weekly[1].week, 3)
        self.assertEqual(aggregate.weeks_survived, 2)

    def test_snapshot_immutability_after_current_state_update(self):
        """Changing current state after snapshot freeze does not change backtest output."""
        db = _setup_test_db()

        # Create snapshot with original spread
        original_events = [
            EventOdds(101, 2025, 1, "KC @ BUF", -3.5),
            EventOdds(102, 2025, 1, "SEA @ DEN", -7.0),
        ]
        _create_snapshot(db, 2025, 1, original_events)

        # Run backtest once (degraded mode - only 1 week)
        weekly1, _ = run_backtest(db, 2025, "best-spread", 18, mode="degraded")
        pick1 = weekly1[0].selected_team
        spread1 = weekly1[0].decision_spread

        # Update current state with different spread (simulating later refresh)
        upsert_current_game(
            event=EventOdds(101, 2025, 1, "KC @ BUF", -10.0),
            observed_at="2025-01-02T12:00:00Z",
            db_name=db,
        )

        # Run backtest again - should use frozen snapshot, not current state
        weekly2, _ = run_backtest(db, 2025, "best-spread", 18, mode="degraded")
        pick2 = weekly2[0].selected_team
        spread2 = weekly2[0].decision_spread

        self.assertEqual(pick1, pick2, "Pick changed after current state update")
        self.assertEqual(spread1, spread2, "Spread changed after current state update")
        self.assertNotEqual(
            spread2, -10.0, "Backtest incorrectly used updated current state"
        )

    def test_byte_stable_output_on_repeated_runs(self):
        """Repeated identical backtest runs produce identical JSON output."""
        db = _setup_test_db()

        events = [
            EventOdds(201, 2025, 1, "KC @ BUF", -3.5),
            EventOdds(202, 2025, 1, "SEA @ DEN", -7.0),
        ]
        _create_snapshot(db, 2025, 1, events)

        # Add grading data
        upsert_game_result(201, "final", 27, 24, "2025-01-05T20:00:00Z", db_name=db)
        upsert_current_game(
            event=GameEvent(
                event_id=201,
                season_year=2025,
                week=1,
                short_name="KC @ BUF",
                spread=-3.5,
                kickoff_at="2025-01-05T17:30:00Z",
            ),
            observed_at="2025-01-05T10:00:00Z",
            db_name=db,
        )
        update_closing_line(
            201, -3.5, "2025-01-05T17:00:00Z", "2025-01-05T17:30:00Z", db
        )

        # Run twice (degraded mode - only 1 week)
        weekly1, agg1 = run_backtest(db, 2025, "best-spread", 18, mode="degraded")
        weekly2, agg2 = run_backtest(db, 2025, "best-spread", 18, mode="degraded")

        # Compare JSON serialization
        json1 = json.dumps(
            {"aggregate": agg1.__dict__, "weekly": [w.__dict__ for w in weekly1]},
            sort_keys=True,
        )
        json2 = json.dumps(
            {"aggregate": agg2.__dict__, "weekly": [w.__dict__ for w in weekly2]},
            sort_keys=True,
        )

        self.assertEqual(json1, json2, "Repeated runs produced different output")

    def test_tie_counts_as_loss(self):
        """Ties are treated as elimination."""
        db = _setup_test_db()

        events = [EventOdds(301, 2025, 1, "KC @ BUF", -3.5)]
        _create_snapshot(db, 2025, 1, events)

        # Add tie result
        upsert_game_result(301, "final", 24, 24, "2025-01-05T20:00:00Z", db_name=db)

        weekly, aggregate = run_backtest(db, 2025, "best-spread", 18, mode="degraded")

        self.assertEqual(weekly[0].outcome, "tie")
        self.assertEqual(aggregate.ties, 1)
        self.assertEqual(aggregate.first_elimination_week, 1, "Tie should eliminate")

    def test_ungraded_explicit_status(self):
        """Postponed/cancelled/missing results marked explicitly."""
        db = _setup_test_db()

        events = [
            EventOdds(401, 2025, 1, "KC @ BUF", -3.5),
            EventOdds(402, 2025, 2, "SEA @ DEN", -7.0),
        ]
        _create_snapshot(db, 2025, 1, events)
        _create_snapshot(db, 2025, 2, events)

        # Week 1: postponed
        upsert_game_result(
            401, "postponed", None, None, "2025-01-05T12:00:00Z", db_name=db
        )

        # Week 2: no result at all

        weekly, aggregate = run_backtest(db, 2025, "best-spread", 18, mode="degraded")

        self.assertEqual(weekly[0].outcome, "postponed")
        self.assertEqual(weekly[1].outcome, "ungraded")
        self.assertEqual(aggregate.ungraded, 2)

    def test_team_reuse_prevented(self):
        """Used teams excluded from later weeks."""
        db = _setup_test_db()

        # Week 1 and 2 both have KC
        events_w1 = [
            EventOdds(501, 2025, 1, "KC @ BUF", -10.0),  # Best spread
            EventOdds(502, 2025, 1, "SEA @ DEN", -3.5),
        ]
        events_w2 = [
            EventOdds(503, 2025, 2, "KC @ BUF", -12.0),  # Best spread
            EventOdds(504, 2025, 2, "SEA @ DEN", -3.5),
        ]
        _create_snapshot(db, 2025, 1, events_w1)
        _create_snapshot(db, 2025, 2, events_w2)

        upsert_game_result(501, "final", 30, 20, "2025-01-05T20:00:00Z", db_name=db)
        upsert_game_result(504, "final", 27, 24, "2025-01-12T20:00:00Z", db_name=db)
        weekly, _ = run_backtest(db, 2025, "best-spread", 18, mode="degraded")

        self.assertEqual(weekly[0].selected_team, "BUF")  # Best spread week 1
        self.assertEqual(
            weekly[1].selected_team, "DEN", "BUF should be excluded week 2"
        )
        self.assertIn("BUF", weekly[1].previously_used)

    def test_prior_picks_preserve_week_and_spread(self):
        """Locked prior picks retain actual week and spread, not enumerate order."""
        db = _setup_test_db()

        events_w1 = [EventOdds(601, 2025, 1, "KC @ BUF", -7.0)]
        events_w2 = [EventOdds(602, 2025, 2, "SEA @ DEN", -5.0)]
        _create_snapshot(db, 2025, 1, events_w1)
        _create_snapshot(db, 2025, 2, events_w2)

        upsert_game_result(601, "final", 27, 20, "2025-01-05T20:00:00Z", db_name=db)
        upsert_game_result(602, "final", 21, 20, "2025-01-12T20:00:00Z", db_name=db)

        weekly, _ = run_backtest(db, 2025, "best-spread", 18, mode="degraded")

        # Week 2's previously_used should have the actual week 1 pick
        self.assertEqual(weekly[1].week, 2)
        self.assertIn(weekly[0].selected_team, weekly[1].previously_used)
        # previously_used is deterministic order
        self.assertEqual(weekly[1].previously_used, [weekly[0].selected_team])

    def test_scoring_margin_from_selected_team_perspective(self):
        """Scoring margin calculated from selected team's perspective, not home."""
        db = _setup_test_db()

        events = [EventOdds(701, 2025, 1, "KC @ BUF", -3.5)]
        _create_snapshot(db, 2025, 1, events)

        # KC (away) wins 27-24
        upsert_game_result(701, "final", 24, 27, "2025-01-05T20:00:00Z", db_name=db)

        weekly, _ = run_backtest(db, 2025, "best-spread", 18, mode="degraded")

        # Selected BUF (home team), margin should be home - away = 24 - 27 = -3
        self.assertEqual(weekly[0].selected_team, "BUF")
        self.assertEqual(weekly[0].scoring_margin, -3.0)
        self.assertEqual(weekly[0].outcome, "loss")

    def test_zero_spread_handled_explicitly(self):
        """Zero spreads not treated as None via truthiness."""
        db = _setup_test_db()

        events = [EventOdds(801, 2025, 1, "KC @ BUF", 0.0)]
        _create_snapshot(db, 2025, 1, events)
        upsert_game_result(801, "final", 24, 24, "2025-01-05T20:00:00Z", db_name=db)
        upsert_current_game(
            event=GameEvent(
                event_id=801,
                season_year=2025,
                week=1,
                short_name="KC @ BUF",
                spread=0.0,
                kickoff_at="2025-01-05T17:30:00Z",
            ),
            observed_at="2025-01-05T10:00:00Z",
            db_name=db,
        )
        update_closing_line(
            801, 0.0, "2025-01-05T17:00:00Z", "2025-01-05T17:30:00Z", db
        )

        weekly, _ = run_backtest(db, 2025, "best-spread", 18, mode="degraded")

        self.assertEqual(weekly[0].decision_spread, 0.0)
        self.assertEqual(weekly[0].closing_spread, 0.0)

    def test_source_revision_determined(self):
        """Source revision is determined, not hardcoded unknown."""
        db = _setup_test_db()

        events = [EventOdds(901, 2025, 1, "KC @ BUF", -3.5)]
        _create_snapshot(db, 2025, 1, events)
        upsert_game_result(901, "final", 27, 24, "2025-01-05T20:00:00Z", db_name=db)

        weekly, _aggregate = run_backtest(db, 2025, "best-spread", 18, mode="degraded")

        # Should be a git hash (40 hex chars) or "unidentified"
        self.assertIn(len(weekly[0].source_revision), [40, len("unidentified")])
        self.assertNotEqual(weekly[0].source_revision, "unknown")

    def test_parameters_in_output(self):
        """Parameters included in weekly and aggregate output."""
        db = _setup_test_db()

        events = [EventOdds(1001, 2025, 1, "KC @ BUF", -3.5)]
        _create_snapshot(db, 2025, 1, events)
        upsert_game_result(1001, "final", 27, 24, "2025-01-05T20:00:00Z", db_name=db)

        weekly, aggregate = run_backtest(db, 2025, "best-spread", 12, mode="degraded")
        self.assertIn("algorithm", weekly[0].parameters)
        self.assertIn("split_week", weekly[0].parameters)
        self.assertEqual(weekly[0].parameters["algorithm"], "best-spread")
        self.assertEqual(weekly[0].parameters["split_week"], 12)

        self.assertIn("algorithm", aggregate.parameters)
        self.assertIn("split_week", aggregate.parameters)

    def test_counterfactual_marking(self):
        """Weeks after first elimination marked counterfactual."""
        db = _setup_test_db()

        events_w1 = [EventOdds(1101, 2025, 1, "KC @ BUF", -3.5)]
        events_w2 = [EventOdds(1102, 2025, 2, "SEA @ DEN", -7.0)]
        events_w3 = [EventOdds(1103, 2025, 3, "DAL @ PHI", -5.0)]
        _create_snapshot(db, 2025, 1, events_w1)
        _create_snapshot(db, 2025, 2, events_w2)
        _create_snapshot(db, 2025, 3, events_w3)

        # Week 1: win
        upsert_game_result(1101, "final", 27, 24, "2025-01-05T20:00:00Z", db_name=db)
        # Week 2: loss (first elimination)
        upsert_game_result(1102, "final", 21, 24, "2025-01-12T20:00:00Z", db_name=db)
        # Week 3: win (counterfactual)
        upsert_game_result(1103, "final", 27, 20, "2025-01-19T20:00:00Z", db_name=db)

        weekly, aggregate = run_backtest(db, 2025, "best-spread", 18, mode="degraded")

        self.assertEqual(weekly[0].counterfactual, False)
        self.assertEqual(weekly[1].counterfactual, False)
        self.assertEqual(weekly[2].counterfactual, True)
        self.assertEqual(aggregate.first_elimination_week, 2)

    def test_json_output_format(self):
        """JSON output has required structure and deterministic keys."""
        db = _setup_test_db()

        events = [EventOdds(601, 2025, 1, "KC @ BUF", -3.5)]
        _create_snapshot(db, 2025, 1, events)
        upsert_game_result(601, "final", 27, 24, "2025-01-05T20:00:00Z", db_name=db)

        weekly, aggregate = run_backtest(db, 2025, "best-spread", 18, mode="degraded")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_path = Path(f.name)

        write_json(weekly, aggregate, temp_path)

        with temp_path.open() as f:
            output = json.load(f)

        self.assertIn("aggregate", output)
        self.assertIn("weekly", output)
        self.assertIn("algorithm", output["aggregate"])
        self.assertIn("parameters", output["aggregate"])
        self.assertIn("wins", output["aggregate"])
        self.assertEqual(len(output["weekly"]), 1)
        self.assertIn("selected_team", output["weekly"][0])
        self.assertIn("parameters", output["weekly"][0])
        self.assertIn("counterfactual", output["weekly"][0])

        temp_path.unlink()

    def test_csv_output_includes_aggregate(self):
        """CSV output includes aggregate section with required fields."""
        db = _setup_test_db()

        events = [EventOdds(701, 2025, 1, "KC @ BUF", -3.5)]
        _create_snapshot(db, 2025, 1, events)
        upsert_game_result(701, "final", 27, 24, "2025-01-05T20:00:00Z", db_name=db)

        weekly, aggregate = run_backtest(db, 2025, "best-spread", 18, mode="degraded")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            temp_path = Path(f.name)

        write_csv(weekly, aggregate, temp_path)

        with temp_path.open() as f:
            content = f.read()

        self.assertIn("AGGREGATE", content)
        self.assertIn("WEEKLY", content)
        self.assertIn("first_elimination_week", content)
        self.assertIn("parameters", content)
        self.assertIn("selected_team", content)
        self.assertIn("counterfactual", content)

        # Verify structure
        lines = content.strip().split("\n")
        self.assertEqual(lines[0], "AGGREGATE")
        # Aggregate key-value pairs
        self.assertIn("algorithm,", lines[1])
        # Find WEEKLY section
        weekly_idx = next(i for i, line in enumerate(lines) if line == "WEEKLY")
        self.assertGreater(weekly_idx, 1, "WEEKLY section should come after AGGREGATE")

        temp_path.unlink()


if __name__ == "__main__":
    unittest.main()
