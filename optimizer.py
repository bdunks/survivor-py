from collections.abc import Callable
from typing import Any

from models import EventOdds, Pick


def _find_optimal_picks(
    events: list[EventOdds],
    optimization_horizon: int,
    sort_key: Callable[[EventOdds], Any],
    user_defined_picks: list[Pick] | None = None,
    *,
    replacement_sort_key: Callable[[EventOdds], Any] | None = None,
    sort_key_second_half: Callable[[EventOdds], Any] | None = None,
) -> list[Pick]:
    picks = list(user_defined_picks or ())
    user_defined_weeks = {pick.week for pick in picks}
    picked_teams = {pick.team for pick in picks}
    picked_weeks = set(user_defined_weeks)

    if len(picks) != len(user_defined_weeks):
        raise ValueError("Each week can only have one pick")
    if len(picks) != len(picked_teams):
        raise ValueError("A team can only have one pick")
    if any(not 1 <= pick.week <= 18 for pick in picks):
        raise ValueError("Pick weeks must be between 1 and 18")

    first_half_events = sorted(
        (event for event in events if 1 <= event.week <= optimization_horizon),
        key=sort_key,
        reverse=True,
    )
    second_half_events = sorted(
        (event for event in events if optimization_horizon < event.week <= 18),
        key=sort_key_second_half or sort_key,
        reverse=True,
    )

    def add_picks(sorted_events: list[EventOdds]) -> None:
        for event in sorted_events:
            if event.favored_team in picked_teams or event.week in picked_weeks:
                continue
            picks.append(
                Pick(
                    team=event.favored_team,
                    week=event.week,
                    spread=abs(event.spread),
                )
            )
            picked_teams.add(event.favored_team)
            picked_weeks.add(event.week)

    def improve_picks(sorted_events: list[EventOdds]) -> None:
        while True:
            replacement_made = False
            for event in sorted_events:
                if (
                    event.favored_team in picked_teams
                    or event.week in user_defined_weeks
                    or event.week not in picked_weeks
                ):
                    continue

                existing_pick = next(pick for pick in picks if pick.week == event.week)
                spread = abs(event.spread)
                if existing_pick.spread < spread:
                    picks.remove(existing_pick)
                    picks.append(Pick(event.favored_team, event.week, spread))
                    picked_teams.remove(existing_pick.team)
                    picked_teams.add(event.favored_team)
                    replacement_made = True
            if not replacement_made:
                return

    add_picks(first_half_events)
    if replacement_sort_key is not None:
        improve_picks(sorted(first_half_events, key=replacement_sort_key, reverse=True))
    add_picks(second_half_events)
    return sorted(picks, key=lambda pick: pick.week)


def find_optimal_picks_best_spread(
    events: list[EventOdds],
    split_week: int,
    user_defined_picks: list[Pick] | None = None,
) -> list[Pick]:
    return _find_optimal_picks(
        events,
        optimization_horizon=split_week,
        sort_key=lambda event: abs(event.spread),
        user_defined_picks=user_defined_picks,
    )


def find_optimal_picks_back_to_front(
    events: list[EventOdds],
    split_week: int,
    user_defined_picks: list[Pick] | None = None,
) -> list[Pick]:
    return _find_optimal_picks(
        events,
        optimization_horizon=split_week,
        sort_key=lambda event: (event.week, abs(event.spread)),
        user_defined_picks=user_defined_picks,
        sort_key_second_half=lambda event: (-event.week, abs(event.spread)),
    )


def calculate_future_value(
    team: str,
    week: int,
    events: list[EventOdds],
    split_week: int = 18,
) -> float:
    return sum(
        1 + abs(event.spread)
        for event in events
        if (event.home_team == team or event.away_team == team)
        and week < event.week <= split_week
    )


def find_optimal_picks_weighted_future_value(
    events: list[EventOdds],
    split_week: int,
    user_defined_picks: list[Pick] | None = None,
) -> list[Pick]:
    def sort_key(event: EventOdds) -> float:
        future_value = (
            calculate_future_value(
                event.favored_team, event.week + 1, events, split_week
            )
            or 1
        )
        scaling_factor = (
            ((split_week - event.week + 1) / split_week) ** 2.5
            if event.week <= split_week
            else 0.0
        )
        return abs(event.spread) * (1 / future_value) * scaling_factor

    return _find_optimal_picks(
        events,
        optimization_horizon=split_week,
        sort_key=sort_key,
        user_defined_picks=user_defined_picks,
        replacement_sort_key=lambda event: abs(event.spread),
        sort_key_second_half=lambda event: (-event.week, abs(event.spread)),
    )


ALGORITHM_DISPATCH = {
    "best-spread": ("Best Spread", find_optimal_picks_best_spread),
    "back-to-front": ("Back to Front", find_optimal_picks_back_to_front),
    "weighted-future-value": (
        "Weighted Future Value",
        find_optimal_picks_weighted_future_value,
    ),
}


class PickOptimizer:
    """Compatibility namespace for the pre-SIMP-05 optimizer API."""

    find_optimal_picks_best_spread = staticmethod(find_optimal_picks_best_spread)
    find_optimal_picks_back_to_front = staticmethod(find_optimal_picks_back_to_front)
    calculate_future_value = staticmethod(calculate_future_value)
    find_optimal_picks_weighted_future_value = staticmethod(
        find_optimal_picks_weighted_future_value
    )
