import argparse
import csv
import json
import os
from datetime import datetime
from typing import List, Dict, Any

import termcolor

from models import EventOdds, Pick
from optimizer import PickOptimizer
from services import CBSSportsService, DatabaseService


def parse_arguments():
    parser = argparse.ArgumentParser(description="Fetch and save odds data.")
    parser.add_argument("--refresh", action="store_true", help="Refresh odds data")
    parser.add_argument(
        "--print-table", action="store_true", help="Print algorithm table"
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
    parser.add_argument("--set-week", type=int, help="Set current week (1-18)")
    parser.add_argument("--add-pick", type=str, help="Add pick in format TEAM:WEEK:SPREAD")
    parser.add_argument("--clear-pick", type=str, help="Clear pick for week number or 'all'")
    parser.add_argument("--status", action="store_true", help="Show current configuration")
    return parser.parse_args()


def validate_picks(picks: List[Pick]) -> None:
    """Validate user picks for common errors."""
    weeks_used = set()
    for pick in picks:
        if not (1 <= pick.week <= 18):
            raise ValueError(f"Invalid week: {pick.week}. Week must be between 1 and 18.")
        if pick.week in weeks_used:
            raise ValueError(f"Duplicate week found: {pick.week}. Each week can only be used once.")
        weeks_used.add(pick.week)
        
        # Basic team name validation (2-3 character abbreviation)
        if not isinstance(pick.team, str) or len(pick.team) < 2 or len(pick.team) > 3:
            raise ValueError(f"Invalid team abbreviation: {pick.team}. Must be 2-3 characters.")


def validate_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and normalize configuration data."""
    # Validate current_week
    if not isinstance(config.get('current_week'), int):
        print("Warning: current_week should be an integer, defaulting to 1")
        config['current_week'] = 1

    if not (1 <= config['current_week'] <= 18):
        print(f"Warning: current_week {config['current_week']} invalid, defaulting to 1")
        config['current_week'] = 1

    # Ensure picks is a list
    if 'picks' not in config:
        config['picks'] = []
    elif not isinstance(config['picks'], list):
        print("Warning: picks should be a list, defaulting to empty list")
        config['picks'] = []

    # Validate algorithm
    valid_algorithms = ["best-spread", "weighted-future-value", "back-to-front"]
    if not isinstance(config.get('algorithm'), str) or config.get('algorithm') not in valid_algorithms:
        config['algorithm'] = "best-spread"

    # Validate split_week
    if not isinstance(config.get('split_week'), int):
        config['split_week'] = 10

    if not (1 <= config['split_week'] <= 18):
        config['split_week'] = 10

    return config


def load_config() -> Dict[str, Any]:
    """Load configuration from config.json file."""
    config_path = "config.json"
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            config = validate_config(config)
            
            # Convert picks dictionaries to Pick objects
            picks = []
            for pick_data in config.get('picks', []):
                try:
                    if isinstance(pick_data, dict):
                        pick = Pick(
                            team=pick_data['team'],
                            week=pick_data['week'],
                            spread=pick_data.get('spread', 0.0)
                        )
                        picks.append(pick)
                except (KeyError, TypeError) as e:
                    print(f"Warning: Invalid pick data {pick_data}: {e}")
            
            # Validate all picks
            try:
                validate_picks(picks)
            except ValueError as e:
                print(f"Configuration error: {e}")
                picks = []
            
            return {
                'current_week': config['current_week'],
                'user_picks': picks,
                'algorithm': config['algorithm'],
                'split_week': config['split_week']
            }
        
        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"Warning: Could not load config.json: {e}")
            print("Using default configuration")
    
    # Return default configuration
    return {
        'current_week': 1,
        'user_picks': [],
        'algorithm': 'best-spread',
        'split_week': 10
    }


def update_current_week(week: int) -> None:
    """Update current week in config.json file."""
    if not (1 <= week <= 18):
        raise ValueError(f"Invalid week: {week}. Week must be between 1 and 18.")
    
    config_path = "config.json"
    config = {}
    
    # Load existing config if it exists
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            pass
    
    # Update current week
    config['current_week'] = week
    
    # Ensure picks array exists
    if 'picks' not in config:
        config['picks'] = []
    
    # Save updated config
    try:
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"Updated current week to {week}")
    except IOError as e:
        print(f"Error updating config file: {e}")
        raise


def update_algorithm(algorithm: str) -> None:
    """Update algorithm setting in config.json file."""
    valid_algorithms = ["best-spread", "weighted-future-value", "back-to-front"]
    if algorithm not in valid_algorithms:
        raise ValueError(f"Invalid algorithm: {algorithm}. Must be one of: {', '.join(valid_algorithms)}")

    config_path = "config.json"
    config = {}

    # Load existing config if it exists
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            pass

    # Update algorithm
    config['algorithm'] = algorithm

    # Ensure required fields exist
    if 'current_week' not in config:
        config['current_week'] = 1
    if 'picks' not in config:
        config['picks'] = []
    if 'split_week' not in config:
        config['split_week'] = 10

    # Save updated config
    try:
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
    except IOError as e:
        print(f"Error updating config file: {e}")
        raise


def update_split_week(split_week: int) -> None:
    """Update split week setting in config.json file."""
    if not (1 <= split_week <= 18):
        raise ValueError(f"Invalid split week: {split_week}. Week must be between 1 and 18.")

    config_path = "config.json"
    config = {}

    # Load existing config if it exists
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            pass

    # Update split week
    config['split_week'] = split_week

    # Ensure required fields exist
    if 'current_week' not in config:
        config['current_week'] = 1
    if 'picks' not in config:
        config['picks'] = []
    if 'algorithm' not in config:
        config['algorithm'] = 'best-spread'

    # Save updated config
    try:
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
    except IOError as e:
        print(f"Error updating config file: {e}")
        raise


def add_pick_to_config(pick_string: str) -> None:
    """Add pick to config.json file from TEAM:WEEK:SPREAD format."""
    try:
        parts = pick_string.split(':')
        if len(parts) != 3:
            raise ValueError("Pick must be in format TEAM:WEEK:SPREAD")
        
        team, week_str, spread_str = parts
        
        # Validate and parse components
        team = team.strip().upper()
        if len(team) < 2 or len(team) > 3:
            raise ValueError(f"Invalid team abbreviation: {team}. Must be 2-3 characters.")
        
        week = int(week_str.strip())
        if not (1 <= week <= 18):
            raise ValueError(f"Invalid week: {week}. Week must be between 1 and 18.")
        
        spread = float(spread_str.strip())
        
    except (ValueError, IndexError) as e:
        print(f"Error parsing pick '{pick_string}': {e}")
        print("Format should be: TEAM:WEEK:SPREAD (e.g., SEA:1:6.0)")
        return
    
    config_path = "config.json"
    config = {}
    
    # Load existing config if it exists
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            pass
    
    # Ensure required fields exist
    if 'picks' not in config:
        config['picks'] = []
    if 'current_week' not in config:
        config['current_week'] = 1
    
    # Check if week already has a pick and replace it
    existing_pick_index = None
    for i, pick in enumerate(config['picks']):
        if pick.get('week') == week:
            existing_pick_index = i
            break
    
    new_pick = {
        'team': team,
        'week': week,
        'spread': spread
    }
    
    if existing_pick_index is not None:
        old_pick = config['picks'][existing_pick_index]
        config['picks'][existing_pick_index] = new_pick
        print(f"Replaced existing pick for week {week}: {old_pick['team']} -> {team}")
    else:
        config['picks'].append(new_pick)
        print(f"Added pick for week {week}: {team} ({spread:+.1f})")
    
    # Save updated config
    try:
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
    except IOError as e:
        print(f"Error updating config file: {e}")
        raise


def clear_pick_from_config(week_or_all: str) -> None:
    """Clear pick(s) from config.json file."""
    config_path = "config.json"
    config = {}
    
    # Load existing config if it exists
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            pass
    
    # Ensure picks array exists
    if 'picks' not in config:
        config['picks'] = []
    
    if week_or_all.lower() == 'all':
        # Clear all picks
        picks_count = len(config['picks'])
        config['picks'] = []
        print(f"Cleared all {picks_count} picks")
    else:
        # Clear specific week
        try:
            week = int(week_or_all)
            if not (1 <= week <= 18):
                raise ValueError(f"Invalid week: {week}. Week must be between 1 and 18.")
        except ValueError as e:
            print(f"Error: {e}")
            print("Use a week number (1-18) or 'all'")
            return
        
        # Find and remove the pick for the specified week
        original_count = len(config['picks'])
        config['picks'] = [pick for pick in config['picks'] if pick.get('week') != week]
        
        if len(config['picks']) < original_count:
            print(f"Cleared pick for week {week}")
        else:
            print(f"No pick found for week {week}")
    
    # Save updated config
    try:
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
    except IOError as e:
        print(f"Error updating config file: {e}")
        raise


def show_configuration_status() -> None:
    """Display current configuration status."""
    config = load_config()
    
    print("=== Configuration Status ===")
    print(f"Current Week: {config['current_week']}")
    print(f"Total Picks: {len(config['user_picks'])}")
    
    if config['user_picks']:
        print("\nExisting Picks:")
        # Sort picks by week for better display
        sorted_picks = sorted(config['user_picks'], key=lambda p: p.week)
        for pick in sorted_picks:
            print(f"  Week {pick.week:2d}: {pick.team} ({pick.spread:+.1f})")
    else:
        print("\nNo picks configured")
    
    print()


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

    print_table(algorithm_1, "Algorithm 1", differences, changes_best_spread)
    print_table(
        algorithm_2,
        "Algorithm 2",
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

    # Handle configuration management commands first
    if args.status:
        show_configuration_status()
        return
    
    if args.set_week is not None:
        try:
            update_current_week(args.set_week)
        except ValueError as e:
            print(f"Error: {e}")
            return
    
    if args.add_pick:
        add_pick_to_config(args.add_pick)
        return
    
    if args.clear_pick:
        clear_pick_from_config(args.clear_pick)
        return

    # Load configuration from config.json
    config = load_config()
    current_week = config['current_week']
    user_defined_picks = config['user_picks']

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
