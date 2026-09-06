from collections.abc import Callable
from typing import Any

from models import EventOdds, Pick


class PickOptimizer:
    def __find_optimal_picks(
        self,
        events: list[EventOdds],
        split_week: int,
        user_defined_picks: list[Pick] | None = None,
        sort_key: Callable[[EventOdds], Any] | None = None,
        second_pass_sort_key: Callable[[EventOdds], Any] | None = None,
        sort_key_second_half: Callable[[EventOdds], Any] | None = None,
    ) -> list[Pick]:
        picks = user_defined_picks.copy() if user_defined_picks else []

        # Create a set to store the weeks of user-defined picks so they aren't later overwritten
        user_defined_weeks = {pick.week for pick in picks}

        # Create sets for teams and weeks from picks
        picked_teams = {pick.team for pick in picks}
        picked_weeks = {pick.week for pick in picks}

        # Split the events based on the split_week
        first_half_events = [event for event in events if event.week <= split_week]
        second_half_events = [event for event in events if event.week > split_week]

        # Sort events
        if sort_key is not None:
            sorted_first_half = sorted(first_half_events, key=sort_key, reverse=True)
            sorted_second_half = sorted(
                second_half_events,
                key=sort_key_second_half or sort_key,
                reverse=True,
            )
        else:
            sorted_first_half = first_half_events
            sorted_second_half = second_half_events

        if second_pass_sort_key is not None:
            sorted_second_pass = sorted(
                first_half_events, key=second_pass_sort_key, reverse=True
            )

        # Helper function to add picks
        def add_picks(sorted_events: list[EventOdds]):
            nonlocal picks, picked_teams, picked_weeks
            for event in sorted_events:
                if (
                    event.favored_team not in picked_teams
                    and event.week not in picked_weeks
                ):
                    picks.append(
                        Pick(
                            team=event.favored_team,
                            week=event.week,
                            spread=abs(event.spread),
                        )
                    )
                    picked_teams.add(event.favored_team)
                    picked_weeks.add(event.week)

                if len(picks) == 18:
                    break

        def second_pass(sorted_events: list[EventOdds], depth: int = 0):
            nonlocal picks, picked_teams, picked_weeks

            # Prevent infinite recursion with depth limit
            if depth > 50:  # Reasonable limit for NFL teams/weeks
                return

            replacement_made = False
            for event in sorted_events:
                if (
                    event.favored_team not in picked_teams
                    and event.week not in user_defined_weeks
                ):
                    # Get existing pick
                    existing_pick = next(
                        pick for pick in picks if pick.week == event.week
                    )
                    if existing_pick.spread < abs(event.spread):
                        # Replace existing pick
                        picks.remove(existing_pick)
                        picks.append(
                            Pick(
                                team=event.favored_team,
                                week=event.week,
                                spread=abs(event.spread),
                            )
                        )
                        picked_teams.remove(existing_pick.team)
                        picked_teams.add(event.favored_team)
                        replacement_made = True
            # Recursively call second_pass until no more replacements are made
            if replacement_made:
                second_pass(sorted_events, depth + 1)

        # Add picks from the first half
        add_picks(sorted_first_half)

        # Run second pass
        if second_pass_sort_key is not None:
            second_pass(sorted_second_pass)

        # Add remaining picks from the second half
        add_picks(sorted_second_half)

        return sorted(picks, key=lambda pick: pick.week)  # Sort by week

    def find_optimal_picks_best_spread(
        self,
        events: list[EventOdds],
        split_week,
        user_defined_picks: list[Pick] | None = None,
    ) -> list[Pick]:
        return self.__find_optimal_picks(
            events=events,
            split_week=split_week,
            user_defined_picks=user_defined_picks,
            sort_key=lambda event: abs(event.spread),
        )

    def find_optimal_picks_back_to_front(
        self,
        events: list[EventOdds],
        split_week,
        user_defined_picks: list[Pick] | None = None,
    ) -> list[Pick]:
        return self.__find_optimal_picks(
            events=events,
            split_week=split_week,
            user_defined_picks=user_defined_picks,
            sort_key=lambda event: (event.week, abs(event.spread)),
            sort_key_second_half=lambda event: (-event.week, abs(event.spread)),
        )

    def calculate_future_value(
        self, team: str, week: int, events: list[EventOdds], split_week: int = 18
    ) -> float:
        """
        Calculate the future value of a team based on future spreads.

        Parameters:
        - team (str): The team to calculate the future value for.
        - week (int): The current week.
        - future_events (List[EventOdds]): List of EventOdds for the season's future events.
        - split_week (int): The week to split the season at.

        Returns:
        - float: The future value of the team.
        """
        teams_future_events = [
            event
            for event in events
            if (event.home_team == team or event.away_team == team)
            and event.week > week
            and event.week <= split_week
        ]

        # Count all future events for the team and calculate favorability scores
        favorable_event_count = 0
        favorability_scores = []

        for event in teams_future_events:
            favorable_event_count += 1
            # Use spread magnitude regardless of favored status
            favorability_scores.append(abs(event.spread))

        # Calculate the total degree of favorability
        total_favorability = sum(favorability_scores)

        # Combine the count of favorable events and the total favorability
        # Here, we're giving equal weight to both metrics, but you can adjust the weights if needed
        future_value = favorable_event_count + total_favorability

        return future_value

    def calculate_future_value_for_all_teams(
        self, week: int, future_events: list[EventOdds]
    ) -> list[float]:
        """
        Calculate the future value of all teams based on future spreads.

        Parameters:
        - week (int): The current week.
        - future_events (List[EventOdds]): List of EventOdds for the season's future events.

        Returns:
        - List[float]: The future values of all teams.
        """
        teams = set()
        for event in future_events:
            teams.add(event.home_team)
            teams.add(event.away_team)

        future_values = [
            (team, self.calculate_future_value(team, week, future_events))
            for team in teams
        ]

        return future_values

    def find_optimal_picks_weighted_future_value(
        self,
        events: list[EventOdds],
        split_week,
        user_defined_picks: list[Pick] | None = None,
    ) -> list[Pick]:
        """
        Find optimal picks using a combination of best spread and future value.
        Specifically, the lowest future value should be considered when picking the best spread.
        """
        # Setup CSV Logger and log header
        # logging.setLoggerClass(CSVLogger)
        # csv_logger = logging.getLogger("csv_logger")

        # Define the sort key function that combines spread and future value
        def sort_key(event: EventOdds):
            if event is None:
                return 0.0
            # Define a power for the scaling factor
            power = 2.5  # Adjust this value to control the drop-off rate

            # Calculate the future value for the team from the current week onwards
            future_value = self.calculate_future_value(
                event.favored_team, event.week + 1, events, split_week
            )
            # Prevent division by zero
            if future_value == 0:
                future_value = 1
            # Calculate the scaling factor, ramping down to split week, and ignoring after split week
            scaling_factor = 0.0
            if event.week <= split_week:
                scaling_factor = ((split_week - event.week + 1) / split_week) ** power

            # Combine spread and future value using the scaling factor
            score = abs(event.spread) * ((1 / future_value) * scaling_factor)
            return score

        # Use the __find_optimal_picks method with the new sort key
        return self.__find_optimal_picks(
            events=events,
            split_week=split_week,
            user_defined_picks=user_defined_picks,
            sort_key=sort_key,
            second_pass_sort_key=lambda event: abs(
                event.spread
            ),  # Second pass sort by spread
            sort_key_second_half=lambda event: (
                -event.week,
                abs(event.spread),
            ),  # Sort second half by week, then spread
        )
