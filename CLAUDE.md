# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python-based NFL survivor pool optimizer that fetches odds data from CBS Sports and provides algorithmic strategies for team selection. The application helps users optimize their picks across the entire 18-week NFL regular season using three different algorithms.

## Development Commands

### Core Commands

```bash
# Install dependencies
pip install requests termcolor beautifulsoup4

# Run the application with help
python main.py --help

# Refresh odds data from CBS Sports
python main.py --refresh --year 2024

# View algorithm comparison table
python main.py --print-table

# Analyze specific week
python main.py --split-week 10

# Compare algorithms
python main.py --compare

# Export data to CSV
python main.py --export
```

### Code Formatting

The project uses Ruff for code formatting and linting (configured in VS Code settings):

```bash
# Format code (if ruff is installed)
ruff format .

# Lint code (if ruff is installed)
ruff check .
```

## Architecture

### Core Components

**Main Entry Point (`main.py`)**

- CLI argument parsing and command orchestration
- Contains user configuration variables (`current_week`, `user_defined_picks`)
- Handles data export and console output formatting

**Data Models (`models.py`)**

- `EventOdds`: Represents NFL game data with automatic team/spread parsing
- `Pick`: Simple NamedTuple for survivor pool selections

**Optimization Engine (`optimizer.py`)**

- `PickOptimizer`: Core optimization logic with three algorithms:
  - Best Spread: Prioritizes highest spreads (safest picks)
  - Back-to-Front: Strategic timing-based approach
  - Weighted Future Value: Advanced algorithm considering future team value

**Services (`services/`)**

- `CBSSportsService`: Web scraper for NFL odds from CBS Sports
- `DatabaseService`: SQLite operations for persistent data storage

### Data Flow

1. CBS Sports scraper fetches odds → SQLite database
2. Database provides events to optimizer
3. Optimizer applies algorithms with user-defined picks
4. Results exported to console tables or CSV files

### Key Configuration Points

**User Picks (`main.py`)**

```python
user_defined_picks = [
    Pick(team="SEA", week=1, spread=6.0),
    # Add existing picks here
]
```

**Current Week (`main.py`)**

```python
current_week = 4  # Update weekly
```

## Database Schema

SQLite database (`odds_data.db`) with `averaged_odds` table:

- event_id (PRIMARY KEY)
- season_year, week
- home_team, away_team, short_name
- spread (point spread)
- created_at, updated_at timestamps

## Dependencies

Core dependencies (requirements.txt):

- `requests`: HTTP client for CBS Sports API
- `termcolor`: Console output coloring
- `beautifulsoup4`: HTML parsing for web scraping

## Testing

The project currently uses manual testing workflows:

```bash
# Test with previous season data
python main.py --print-table
```

## Common Development Tasks

### Adding New Algorithms

Extend `PickOptimizer` class with new methods following the pattern:

```python
def find_optimal_picks_custom(self, events, split_week, user_defined_picks=None):
    return self.__find_optimal_picks(
        events=events,
        split_week=split_week,
        user_defined_picks=user_defined_picks,
        sort_key=lambda event: your_custom_logic(event)
    )
```

### Modifying Data Sources

The CBS Sports URL pattern is: `https://www.cbssports.com/nfl/scoreboard/{year}/regular/{week}/`
Parsing logic in `CBSSportsService.fetch_events()` handles HTML structure changes.

### Database Operations

Direct database access available via `DatabaseService`:

```python
from services import DatabaseService
db = DatabaseService()
events = db.fetch_odds_data(2024)
# Custom analysis
db.close()
```

## Output Formats

**Console Table**: Color-coded picks comparison

- Red: Algorithm differences
- Yellow: Changes from previous split week
- White: Standard picks

**CSV Export**: Three formats per algorithm

1. Team abbreviations with spreads: `"SEA (6.0)"`
2. Team abbreviations only: `"SEA"`
3. Spreads only: `"6.0"`
