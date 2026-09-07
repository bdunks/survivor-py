import math
from collections.abc import Callable
from typing import Any

from models import EventOdds, Pick

_SPREAD_WIN_PROBABILITY_SCALE = 6.0
_ASSIGNMENT_INVALID_WEIGHT = -1e9


def _survival_weight(event: EventOdds) -> float:
    # ponytail: fixed spread-to-probability scale; calibrate from historical outcomes when available.
    return 1.0 - math.log1p(
        math.exp(-abs(event.spread) / _SPREAD_WIN_PROBABILITY_SCALE)
    )


def _minimum_cost_assignment(costs: list[list[float]]) -> list[int]:
    row_count = len(costs)
    column_count = len(costs[0]) if costs else 0
    if row_count > column_count:
        raise ValueError("Assignment requires at least as many columns as rows")

    u = [0.0] * (row_count + 1)
    v = [0.0] * (column_count + 1)
    matching = [0] * (column_count + 1)
    previous = [0] * (column_count + 1)

    for row in range(1, row_count + 1):
        matching[0] = row
        column = 0
        minimum = [math.inf] * (column_count + 1)
        used = [False] * (column_count + 1)
        while True:
            used[column] = True
            matched_row = matching[column]
            delta = math.inf
            next_column = 0
            for candidate in range(1, column_count + 1):
                if used[candidate]:
                    continue
                current = (
                    costs[matched_row - 1][candidate - 1]
                    - u[matched_row]
                    - v[candidate]
                )
                if current < minimum[candidate]:
                    minimum[candidate] = current
                    previous[candidate] = column
                if minimum[candidate] < delta:
                    delta = minimum[candidate]
                    next_column = candidate
            for candidate in range(column_count + 1):
                if used[candidate]:
                    u[matching[candidate]] += delta
                    v[candidate] -= delta
                else:
                    minimum[candidate] -= delta
            column = next_column
            if matching[column] == 0:
                break

        while True:
            previous_column = previous[column]
            matching[column] = matching[previous_column]
            column = previous_column
            if column == 0:
                break

    assignment = [-1] * row_count
    for column in range(1, column_count + 1):
        if matching[column]:
            assignment[matching[column] - 1] = column - 1
    return assignment


def _global_assignment_events(
    events: list[EventOdds],
    weeks: list[int],
    unavailable_teams: set[str],
) -> list[EventOdds]:
    if not weeks:
        return []

    candidates: dict[tuple[int, str], EventOdds] = {}
    weights: dict[tuple[int, str], float] = {}
    week_set = set(weeks)
    for event in events:
        if event.week not in week_set or event.favored_team in unavailable_teams:
            continue
        edge = (event.week, event.favored_team)
        weight = _survival_weight(event)
        if edge not in weights or weight > weights[edge]:
            candidates[edge] = event
            weights[edge] = weight

    teams = sorted({team for _, team in candidates})
    if not teams:
        return []

    scores = [
        [weights.get((week, team), _ASSIGNMENT_INVALID_WEIGHT) for team in teams]
        + [0.0] * len(weeks)
        for week in weeks
    ]
    assignment = _minimum_cost_assignment([[-score for score in row] for row in scores])
    return [
        candidates[(week, teams[column])]
        for week, column in zip(weeks, assignment)
        if 0 <= column < len(teams) and (week, teams[column]) in candidates
    ]


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
    return max(
        (
            abs(event.spread)
            for event in events
            if event.favored_team == team and week < event.week <= split_week
        ),
        default=0.0,
    )


def find_optimal_picks_weighted_future_value(
    events: list[EventOdds],
    split_week: int,
    user_defined_picks: list[Pick] | None = None,
    *,
    future_value_weight: float = 1.0,
) -> list[Pick]:
    def sort_key(event: EventOdds) -> float:
        future_value = calculate_future_value(
            event.favored_team, event.week, events, split_week
        )
        return abs(event.spread) - future_value_weight * future_value

    return _find_optimal_picks(
        events,
        optimization_horizon=split_week,
        sort_key=sort_key,
        user_defined_picks=user_defined_picks,
        sort_key_second_half=lambda event: (-event.week, abs(event.spread)),
    )


def find_optimal_picks_global_assignment(
    events: list[EventOdds],
    split_week: int,
    user_defined_picks: list[Pick] | None = None,
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

    horizon_weeks = [
        week for week in range(1, split_week + 1) if week not in picked_weeks
    ]
    for event in _global_assignment_events(events, horizon_weeks, picked_teams):
        picks.append(Pick(event.favored_team, event.week, abs(event.spread)))
        picked_teams.add(event.favored_team)
        picked_weeks.add(event.week)

    for event in sorted(
        (event for event in events if split_week < event.week <= 18),
        key=lambda event: (event.week, abs(event.spread)),
        reverse=True,
    ):
        if event.favored_team in picked_teams or event.week in picked_weeks:
            continue
        picks.append(Pick(event.favored_team, event.week, abs(event.spread)))
        picked_teams.add(event.favored_team)
        picked_weeks.add(event.week)

    return sorted(picks, key=lambda pick: pick.week)


ALGORITHM_DISPATCH = {
    "best-spread": ("Best Spread", find_optimal_picks_best_spread),
    "back-to-front": ("Back to Front", find_optimal_picks_back_to_front),
    "weighted-future-value": (
        "Weighted Future Value",
        find_optimal_picks_weighted_future_value,
    ),
    "global-assignment": ("Global Max Survival", find_optimal_picks_global_assignment),
}
