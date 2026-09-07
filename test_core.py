import json
import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import app as application
import optimizer
from config_store import (
    load_config,
    update_algorithm,
    update_current_week,
    update_pick,
    update_split_week,
)
from models import EventOdds, Pick

ALGORITHM_METHODS = {
    "best-spread": "find_optimal_picks_best_spread",
    "back-to-front": "find_optimal_picks_back_to_front",
    "weighted-future-value": "find_optimal_picks_weighted_future_value",
    "global-assignment": "find_optimal_picks_global_assignment",
}

EXPECTED_API_ROUTES = {
    ("GET", "/api/config"),
    ("PUT", "/api/config/week/{week}"),
    ("PUT", "/api/config/algorithm"),
    ("PUT", "/api/config/split-week"),
    ("POST", "/api/config/picks"),
    ("DELETE", "/api/config/picks/{week}"),
    ("DELETE", "/api/config/picks"),
    ("POST", "/api/data/refresh"),
    ("GET", "/api/data/events"),
    ("GET", "/api/optimize/{split_week}/{algorithm}"),
}


@contextmanager
def temporary_config():
    previous_directory = os.getcwd()
    with tempfile.TemporaryDirectory() as directory:
        os.chdir(directory)
        try:
            yield Path(directory) / "config.json"
        finally:
            os.chdir(previous_directory)


def fixture_event(event_id, week, favored_team, spread, opponent):
    return EventOdds(
        event_id=event_id,
        season_year=2025,
        week=week,
        short_name=f"{favored_team} @ {opponent}",
        spread=spread,
    )


def horizon_events():
    events = []
    for week in range(1, 19):
        if week == 14:
            events.extend(
                [
                    fixture_event(140, 14, "SAV", 6.0, "O14"),
                    fixture_event(141, 14, "NOW", 5.0, "N14"),
                ]
            )
        elif week >= 15:
            events.extend(
                [
                    fixture_event(week * 10, week, "SAV", 12.0, f"O{week}"),
                    fixture_event(week * 10 + 1, week, f"F{week}", 11.0, f"N{week}"),
                ]
            )
        else:
            events.append(
                fixture_event(
                    week * 10, week, f"T{week:02}", 4.0 + week / 100, f"O{week}"
                )
            )
    return events


def pick_for_week(picks, week):
    return next(pick for pick in picks if pick.week == week)


class OptimizerTests(unittest.TestCase):
    def test_algorithms_preserve_user_pick_and_pick_invariants(self):
        events = horizon_events()
        user_pick = Pick(team="LCK", week=5, spread=99.0)

        for split_week in (10, 14, 18):
            for slug, method_name in ALGORITHM_METHODS.items():
                with self.subTest(split_week=split_week, algorithm=slug):
                    picks = getattr(optimizer, method_name)(
                        events, split_week, [user_pick]
                    )
                    weeks = [pick.week for pick in picks]
                    teams = [pick.team for pick in picks]

                    self.assertIn(user_pick, picks)
                    self.assertEqual(weeks, sorted(weeks))
                    self.assertEqual(len(weeks), len(set(weeks)))
                    self.assertEqual(len(teams), len(set(teams)))
                    self.assertEqual(weeks, list(range(1, 19)))

    def test_post_horizon_user_pick_is_preserved_in_the_18_week_grid(self):
        events = horizon_events()
        user_pick = Pick(team="LCK", week=16, spread=99.0)

        for split_week in (10, 14):
            for slug, method_name in ALGORITHM_METHODS.items():
                with self.subTest(split_week=split_week, algorithm=slug):
                    picks = getattr(optimizer, method_name)(
                        events, split_week, [user_pick]
                    )
                    self.assertIn(user_pick, picks)
                    self.assertEqual([pick.week for pick in picks], list(range(1, 19)))
                    self.assertEqual(len({pick.team for pick in picks}), len(picks))

    def test_split_week_controls_future_value_through_10_14_and_18(self):
        events = horizon_events()

        self.assertEqual(
            {
                split_week: optimizer.calculate_future_value(
                    "SAV", 13, events, split_week
                )
                for split_week in (10, 14, 18)
            },
            {10: 0, 14: 6, 18: 12},
        )

        week_14_horizon = optimizer.find_optimal_picks_weighted_future_value(events, 14)
        full_season_horizon = optimizer.find_optimal_picks_weighted_future_value(
            events, 18
        )

        self.assertEqual(pick_for_week(week_14_horizon, 14).team, "SAV")
        self.assertEqual(pick_for_week(full_season_horizon, 14).team, "NOW")
        self.assertIn("SAV", {pick.team for pick in full_season_horizon})

    def test_future_value_uses_best_future_favorite_only(self):
        events = [
            fixture_event(1, 1, "A", 3.0, "O1"),
            fixture_event(2, 2, "A", 6.0, "O2"),
            EventOdds(3, 2025, 3, "O3 @ A", 11.0),
        ]
        self.assertEqual(optimizer.calculate_future_value("A", 1, events, 3), 6.0)

    def test_global_assignment_preserves_a_team_for_a_better_later_matchup(self):
        events = [
            fixture_event(1, 1, "A", 10.0, "O1"),
            fixture_event(2, 1, "B", 9.0, "O2"),
            fixture_event(3, 2, "A", 9.0, "O3"),
            fixture_event(4, 2, "C", 1.0, "O4"),
        ]
        picks = optimizer.find_optimal_picks_global_assignment(events, 2)
        self.assertEqual(
            [(pick.week, pick.team) for pick in picks],
            [(1, "B"), (2, "A")],
        )

    def test_stable_algorithm_slugs_dispatch_through_the_retained_route(self):
        events = horizon_events()
        expected_names = {
            "best-spread": "Best Spread",
            "back-to-front": "Back to Front",
            "weighted-future-value": "Weighted Future Value",
            "global-assignment": "Global Max Survival",
        }

        for slug in ALGORITHM_METHODS:
            with self.subTest(algorithm=slug):
                with (
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
                    patch.object(
                        application,
                        "fetch_odds_data",
                        return_value=events,
                    ),
                ):
                    result = application.optimize_single_algorithm(14, slug, year=2025)

                self.assertEqual(result.algorithm, expected_names[slug])

    def test_current_api_route_inventory_is_explicit(self):
        actual_api_routes = {
            (method, getattr(route, "path", ""))
            for route in application.app.routes
            if getattr(route, "path", "").startswith("/api/")
            for method in getattr(route, "methods", ()) or ()
        }

        self.assertEqual(actual_api_routes, EXPECTED_API_ROUTES)
        self.assertEqual(
            sum(getattr(route, "path", "") == "" for route in application.app.routes), 1
        )


class ConfigurationTests(unittest.TestCase):
    def test_defaults_and_malformed_input_are_isolated_from_repository_config(self):
        defaults = {
            "current_week": 1,
            "picks": [],
            "algorithm": "best-spread",
            "split_week": 10,
        }

        with temporary_config() as config_path:
            self.assertEqual(load_config(), defaults)

            config_path.write_text("{not json", encoding="utf-8")
            self.assertEqual(load_config(), defaults)

            config_path.write_text(json.dumps({"current_week": 4}), encoding="utf-8")
            self.assertEqual(load_config(), {**defaults, "current_week": 4})

            config_path.write_text(
                json.dumps(
                    {
                        "current_week": 0,
                        "picks": "not a list",
                        "algorithm": "not-an-algorithm",
                        "split_week": 99,
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(load_config(), defaults)

    def test_load_save_preserves_unrelated_fields(self):
        original = {
            "current_week": 4,
            "picks": [{"team": "SEA", "week": 1, "spread": 6.0}],
            "algorithm": "back-to-front",
            "split_week": 14,
            "unrelated": {"keep": True},
        }

        with temporary_config() as config_path:
            config_path.write_text(json.dumps(original), encoding="utf-8")
            loaded = load_config()

            self.assertEqual(loaded["current_week"], 4)
            self.assertEqual(loaded["picks"], [Pick("SEA", 1, 6.0)])
            self.assertEqual(loaded["algorithm"], "back-to-front")
            self.assertEqual(loaded["split_week"], 14)

            update_current_week(6)
            saved = json.loads(config_path.read_text(encoding="utf-8"))

            self.assertEqual(saved["current_week"], 6)
            self.assertEqual(saved["unrelated"], original["unrelated"])
            self.assertEqual(saved["picks"], original["picks"])

    def test_pick_for_existing_week_is_replaced_without_dropping_other_data(self):
        original = {
            "current_week": 4,
            "picks": [
                {"team": "SEA", "week": 5, "spread": 6.0},
                {"team": "KC", "week": 2, "spread": 3.0},
            ],
            "algorithm": "best-spread",
            "split_week": 10,
            "unrelated": "keep me",
        }

        with temporary_config() as config_path:
            config_path.write_text(json.dumps(original), encoding="utf-8")
            update_pick(Pick("BUF", 5, 7.5))
            saved = json.loads(config_path.read_text(encoding="utf-8"))

            self.assertEqual(
                saved["picks"],
                [
                    {"team": "BUF", "week": 5, "spread": 7.5},
                    {"team": "KC", "week": 2, "spread": 3.0},
                ],
            )
            self.assertEqual(saved["unrelated"], original["unrelated"])

    def test_updates_validate_typed_values(self):
        with temporary_config():
            update_current_week(6)
            update_algorithm("back-to-front")
            update_split_week(14)
            update_pick(Pick("SEA", 1, 6.0))

            config = load_config()
            self.assertEqual(config["current_week"], 6)
            self.assertEqual(config["algorithm"], "back-to-front")
            self.assertEqual(config["split_week"], 14)
            self.assertEqual(config["picks"], [Pick("SEA", 1, 6.0)])

            with self.assertRaises(ValueError):
                update_current_week(0)
            with self.assertRaises(ValueError):
                update_split_week(19)
            with self.assertRaises(ValueError):
                update_algorithm("invalid")
            with self.assertRaises(ValueError):
                update_pick(Pick("X", 1, 1.0))
            with self.assertRaises(ValueError):
                update_pick(Pick("SEA", 19, 1.0))


class EventOddsTests(unittest.TestCase):
    def test_event_odds_parses_at_vs_and_surrounding_whitespace(self):
        cases = (
            ("SEA @ DEN", "SEA", "DEN"),
            (" sea   vs   den ", "sea", "den"),
            ("  NYJ @  BUF  ", "NYJ", "BUF"),
        )

        for short_name, away_team, home_team in cases:
            with self.subTest(short_name=short_name):
                event = EventOdds(1, 2025, 1, short_name, 3.0)
                self.assertEqual(event.away_team, away_team)
                self.assertEqual(event.home_team, home_team)

    def test_malformed_game_name_is_rejected_before_an_unk_pick_can_be_selected(self):
        with self.assertRaises(ValueError):
            EventOdds(1, 2025, 1, "not a matchup", 3.0)


if __name__ == "__main__":
    unittest.main()
