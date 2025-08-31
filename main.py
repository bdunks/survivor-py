import argparse
import csv
from datetime import datetime
from typing import List

from models import EventOdds, Pick
from optimizer import PickOptimizer
from services import DatabaseService, CBSSportsService


def parse_arguments():
    parser = argparse.ArgumentParser(description="Fetch and save odds data.")
    parser.add_argument("--refresh", action="store_true", help="Refresh odds data")
    parser.add_argument(
        "--print-table", action="store_true", help="Print algorithim table"
    )
    parser.add_argument(
        "--split-week", type=int, default=16, help="Print by split week"
    )
    parser.add_argument("--compare", action="store_true", help="Compare algorithms")
    parser.add_argument(
        "--compare-picks", action="store_true", help="Compare picks for each algorithm"
    )
    parser.add_argument("--export", action="store_true", help="Export data to CSV")
    parser.add_argument(
        "--year",
        type=int,
        default=datetime.now().year,
        help="Year for which to fetch odds data",
    )
    return parser.parse_args()


def print_to_console(all_picks):
    # Print header
    header = ["Split Week"] + [f"Week {i:02}" for i in range(1, 19)] + ["Total Spread"]
    print(" | ".join(header))

    # Print each split_week's picks side by side
    for split_week, picks in enumerate(all_picks, start=1):
        row = [f"{split_week:02}"]
        total_spread = 0
        for week in range(1, 19):
            # Find the pick for the current split_week or use a placeholder if not found
            pick = next((p for p in picks if p.week == week), None)
            if pick:
                formatted_spread = (
                    f"{pick.spread:.1f}"  # Format spread with one decimal
                )
                formatted_team = f"{pick.team[:3]:<3}"  # Strip whitespace and ensure team is three characters wide
                row.append(f"{formatted_team} ({formatted_spread})")
                total_spread += pick.spread
            else:
                row.append("N/A")
        row.append(f"{total_spread:.1f}")
        print(" | ".join(row))


def export_to_csv(all_picks: List[EventOdds], filename="picks_data.csv", append=False):
    with open(filename, mode="a" if append else "w", newline="") as file:
        writer = csv.writer(file)

        # Write header if file is empty or if not appending
        if not append or file.tell() == 0:
            header = (
                ["Split Week"]
                + [f"Week {i:02}" for i in range(1, 19)]
                + ["Total Spread"]
            )
            writer.writerow(header)

        # Write each row
        for split_week, picks in enumerate(all_picks, start=1):
            row = [f"{split_week}"]
            total_spread = 0
            for week in range(1, 19):
                pick = next((p for p in picks if p.week == week), None)
                if pick:
                    formatted_spread = f"{pick.spread:.1f}"
                    formatted_team = f"{pick.team[:3]:<3}"
                    row.append(f"{formatted_team} ({formatted_spread})")
                    total_spread += pick.spread
                else:
                    row.append("N/A")
            row.append(f"{total_spread:.1f}")

            # Add a second set of 18 columns, one for each week, to show the picks as team names only
            for week in range(1, 19):
                pick = next((p for p in picks if p.week == week), None)
                if pick:
                    formatted_team = f"{pick.team[:3]:<3}"
                    row.append(formatted_team)
                else:
                    row.append("N/A")

            # Add a third set of 18 columns, one for each week, to show the picks as spreads only
            for week in range(1, 19):
                pick = next((p for p in picks if p.week == week), None)
                if pick:
                    formatted_spread = f"{pick.spread:.1f}"
                    row.append(formatted_spread)
                else:
                    row.append("N/A")

            writer.writerow(row)


def compare_algorithms(
    picks_best_spread: List[Pick],
    picks_back_to_front: List[Pick],
    start_week: int = 1,
    end_week: int = 18,
):
    # Headers for the table
    print(
        f"{'Split Week':<12}{'Best Spread Total':<20}{'Back-to-Front Total':<20}{'Difference':<15}"
    )
    print("-" * 67)

    for split_week in range(start_week, end_week + 1):
        # Calculate total spread for each algorithm
        best_spread_total = sum(
            pick.spread for pick in picks_best_spread if pick.week == split_week
        )
        back_to_front_total = sum(
            pick.spread for pick in picks_back_to_front if pick.week == split_week
        )

        # Calculate the difference between the two totals
        difference = best_spread_total - back_to_front_total

        # Print the results in a table format
        print(
            f"{split_week:<12}{best_spread_total:<20.1f}{back_to_front_total:<20.1f}{difference:<15.1f}"
        )


def compare_picks(
    algo_1: List[Pick],
    algo_1_name: str,
    algo_2: List[Pick],
    algo_2_name: str,
    start_week: int = 1,
    end_week: int = 18,
):
    for split_week in range(start_week, end_week + 1):
        # print(picks_back_to_front)
        # Create dictionaries for easier comparison
        algo_1_dict = {pick.week: pick for pick in algo_1[split_week - 1]}
        algo_2_dict = {pick.week: pick for pick in algo_2[split_week - 1]}

        # Identify differences
        differences = []
        for week in range(1, 19):
            algo_1_pick = algo_1_dict.get(week)
            algo_2_pick = algo_2_dict.get(week)

            if algo_1_pick and algo_2_pick and algo_1_pick.team != algo_2_pick.team:
                differences.append((week, algo_1_pick.team, algo_2_pick.team))

        # Print the differences for the current split week
        if differences:
            print(f"Differences for Split Week {split_week}:")
            for week, algo_1_team, algo_2_team in differences:
                print(
                    f"Week {week:02}: {algo_1_name} > {algo_1_team} | {algo_2_name} > {algo_2_team}"
                )
            print()


import termcolor

# Constants for colors and formatting
DIFF_COLOR = "red"
CHANGE_COLOR = "yellow"
SAME_COLOR = "whilte"
DEFAULT_COLOR = "white"


def calculate_total_spread(picks_for_split_week):
    return sum(pick.spread or 0 for pick in picks_for_split_week)


def identify_differences(picks1, picks2):
    return [week1.team != week2.team for week1, week2 in zip(picks1, picks2)]


def identify_changes_from_previous_split_week(current_picks, previous_picks=None):
    if not previous_picks:
        return [False] * len(current_picks)

    return [curr.team != prev.team for curr, prev in zip(current_picks, previous_picks)]


def generate_changes_for_picks(picks):
    changes = []
    for i in range(len(picks)):
        previous = picks[i - 1] if i != 0 else None
        changes.append(identify_changes_from_previous_split_week(picks[i], previous))
    return changes


def print_table(picks, title, differences, changes_from_previous):
    # Print table title
    print(termcolor.colored(title, attrs=["bold", "underline"]))

    # Print header
    header = ["Split Week"] + [f"Week {i:02}" for i in range(1, 19)] + ["Total Spread"]
    print(" | ".join(header))

    # Print rows
    for split_week, picks_for_week in enumerate(picks, start=1):
        row = [f"{split_week:02}"]
        for week, pick in enumerate(picks_for_week, start=1):
            color = DEFAULT_COLOR
            if differences[split_week - 1][week - 1]:
                color = DIFF_COLOR
            elif changes_from_previous[split_week - 1][week - 1]:
                color = CHANGE_COLOR
            if pick.spread:
                formatted_cell = f"{pick.team[:3]:<3} ({pick.spread:>4.1f})"
            else:
                formatted_cell = f"{pick.team[:3]:<3} ( -- )"
            row.append(termcolor.colored(formatted_cell, color))
        row.append(f"{calculate_total_spread(picks_for_week):.1f}")
        print(" | ".join(row))
    print("\n")


def print_comparison(algorithm_1, algorithm_2):
    differences = [
        identify_differences(week1, week2)
        for week1, week2 in zip(algorithm_1, algorithm_2)
    ]
    changes_best_spread = generate_changes_for_picks(algorithm_1)
    changes_back_to_front = generate_changes_for_picks(algorithm_2)

    print_table(algorithm_1, "Algorithim 1", differences, changes_best_spread)
    print_table(
        algorithm_2,
        "Algorithim 2",
        differences,
        changes_back_to_front,
    )


def print_split_week(picks, split_week):
    # Print header
    header = ["Week", "Team", "Spread"]
    print(" | ".join(header))

    # Print rows
    total_spread = 0
    lowest_spread = 100
    for pick in picks[split_week - 1]:
        total_spread += pick.spread or 0
        if pick.spread and pick.spread < lowest_spread:
            lowest_spread = pick.spread
        row = [
            f"{pick.week:02}",
            f"{pick.team[:3]:<3}",
            f"{pick.spread:.2f}" if pick.spread else "",
        ]
        print(" | ".join(row))
    print(f"\nSpread: {total_spread} - Riskiest Game: {lowest_spread}")


def main():
    args = parse_arguments()
    refresh_requested = args.refresh
    year = args.year
    print_table_requested = args.print_table
    print_split_week_requested = args.split_week
    compare_requested = args.compare
    compare_picks_requested = args.compare_picks
    export_requested = args.export

    # set user defined picks:
    current_week = 1
    user_defined_picks = [
        # Pick(team="SEA", week=1, spread=6),
        # Pick(team="HOU", week=2, spread=6.5),
        # Pick(team="CLE", week=3, spread=6.5),  # LOST
        # Pick(team="CLE", week=4, spread=6.5),
        # Pick(team="MIA", week=5),
        # Pick(team="LAR", week=6),
        # Pick(team="SEA", week=7),
        # Pick(team="BAL", week=8),
        # Pick(team="CLE", week=9),
        # Pick(team="DAL", week=10),
        # Pick(team="DET", week=11),
        # Pick(team="KC", week=12),
    ]

    # Fetch fresh data from CBS Sports if a refresh is requested
    events: List[EventOdds] = []
    if refresh_requested:
        odds_service = CBSSportsService()
        events = odds_service.fetch_events(year, starting_week=current_week)

    # Use the DatabaseService class to save the data to the SQLite database
    db_service = DatabaseService()
    if refresh_requested:
        db_service.save_odds_data(events)

    # Always re-assign events using the full DB data for the year
    # The service may have only selected for a subset of weeks
    events = db_service.fetch_odds_data(year)
    db_service.close()

    # Use the PicksService class to find the optimal picks
    pick_optimizer = PickOptimizer()

    picks_best_spread = [
        pick_optimizer.find_optimal_picks_best_spread(
            events, split_week, user_defined_picks
        )
        for split_week in range(1, 19)
    ]
    picks_back_to_front = [
        pick_optimizer.find_optimal_picks_back_to_front(
            events, split_week, user_defined_picks
        )
        for split_week in range(1, 19)
    ]
    picks_best_spread_weighted_future_value = [
        pick_optimizer.find_optimal_picks_weighted_future_value(
            events, split_week, user_defined_picks
        )
        for split_week in range(1, 19)
    ]

    if print_table_requested:
        print_comparison(picks_best_spread, picks_best_spread_weighted_future_value)

    if print_split_week_requested:
        print(f"split week: {print_split_week_requested}")
        print("\n=== back-to-front === ")
        print_split_week(picks_back_to_front, print_split_week_requested)

        print("\n=== best spread === ")
        print_split_week(picks_best_spread, print_split_week_requested)

        print("\n=== weighted best spread === ")
        print_split_week(
            picks_best_spread_weighted_future_value, print_split_week_requested
        )

    if export_requested:
        export_to_csv(picks_best_spread)
        export_to_csv(picks_back_to_front, append=True)

    if compare_requested:
        compare_algorithms(picks_best_spread, picks_back_to_front)

    if compare_picks_requested:
        # compare_picks(
        #     picks_best_spread, "Best Spread", picks_back_to_front, "Back to Front"
        # )
        compare_picks(
            picks_best_spread,
            "Best Spread",
            picks_best_spread_weighted_future_value,
            "Weighted Best Spread",
        )


if __name__ == "__main__":
    main()
