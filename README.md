# Survivor Pool Optimizer

A Python application that fetches NFL odds data and optimizes team selection for survivor pool fantasy football games using multiple algorithmic strategies.

## Overview

Survivor pools (also known as elimination pools) are fantasy football contests where participants pick one NFL team to win each week. The catch: once you pick a team, you cannot pick them again for the remainder of the season. If your picked team loses, you're eliminated from the pool. This tool helps optimize team selections to maximize your chances of surviving the entire 18-week NFL regular season.

## Features

- **Data Fetching**: Retrieves NFL odds and spread data from CBS Sports
- **SQLite Database Storage**: Persistent storage of odds data with automatic table creation and data management
- **Multiple Optimization Algorithms**:
  - **Best Spread**: Prioritizes teams with the highest point spreads (safest picks)
  - **Back-to-Front**: Strategic timing-based approach that considers week positioning
  - **Weighted Future Value**: Advanced algorithm that considers a team's future value and availability
- **Interactive Analysis Tools**:
  - Table-based visualization with color-coded differences
  - Algorithm comparison and pick analysis
  - Split-week analysis for strategic planning
  - CSV export functionality
- **User-Defined Picks**: Support for manual pick overrides and existing selections

## Installation

### Prerequisites

- Python 3.7 or higher
- pip package manager

### Setup

1. Clone or download the repository:
```bash
git clone <repository-url>
cd survivor-py
```

2. Install required dependencies:
```bash
pip install requests termcolor beautifulsoup4
```

3. Run the application:
```bash
python main.py --help
```

## Usage

### Basic Commands

#### Refresh Data
Fetch the latest odds data from CBS Sports:
```bash
python main.py --refresh --year 2024
```

#### View Algorithm Comparison Table
Display a colorized comparison table of different algorithms:
```bash
python main.py --print-table
```

#### Analyze Specific Week
View detailed picks for a specific split week:
```bash
python main.py --split-week 10
```

#### Compare Algorithm Performance
See numerical comparison between algorithms:
```bash
python main.py --compare
```

#### Compare Specific Picks
View side-by-side pick differences:
```bash
python main.py --compare-picks
```

#### Export to CSV
Generate CSV files with pick data:
```bash
python main.py --export
```

### Command Line Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `--refresh` | Fetch fresh odds data from CBS Sports | False |
| `--print-table` | Display algorithm comparison table | False |
| `--split-week N` | Analyze specific split week (1-18) | 16 |
| `--compare` | Compare algorithm totals | False |
| `--compare-picks` | Compare individual picks between algorithms | False |
| `--export` | Export data to CSV files | False |
| `--year YYYY` | Specify NFL season year | Current year |

### Example Workflows

#### Weekly Analysis Workflow
```bash
# 1. Refresh data for current week
python main.py --refresh --year 2024

# 2. View comparison table
python main.py --print-table

# 3. Analyze current split week in detail
python main.py --split-week 4

# 4. Export for external analysis
python main.py --export
```

#### Algorithm Comparison Workflow
```bash
# Compare total spreads
python main.py --compare

# Compare individual picks
python main.py --compare-picks

# View visual table comparison
python main.py --print-table
```

## Algorithms Explained

### 1. Best Spread Algorithm
**Strategy**: Prioritize teams with the highest point spreads (most favored teams).
**Logic**: Higher spreads typically indicate safer bets, maximizing week-to-week survival probability.
**Best For**: Conservative players who want to maximize individual week success rates.

### 2. Back-to-Front Algorithm
**Strategy**: Consider week positioning and timing when making picks.
**Logic**: Makes strategic decisions about when to use strong teams based on their position in the season.
**Best For**: Players who want to balance immediate safety with long-term strategic positioning.

### 3. Weighted Future Value Algorithm
**Strategy**: Advanced algorithm that considers both current spread and a team's future value.
**Logic**: Calculates a "future value" score based on:
- Number of games where the team will be favored in remaining weeks
- Degree of favorability (spread values) in future games
- Scaling factor that prioritizes earlier weeks in the split
**Best For**: Advanced players who want to optimize for the entire season rather than individual weeks.

## Project Structure

```
survivor-py/
├── main.py                 # Main application entry point and CLI
├── models.py               # Data models (EventOdds, Pick)
├── optimizer.py            # Pick optimization algorithms
├── logger.py               # Custom CSV logging utility
├── requirements.txt        # Python dependencies
├── odds_data.db           # SQLite database (created automatically)
└── services/
    ├── __init__.py        # Service module initialization
    ├── cbssports.py       # CBS Sports data fetching service
    └── sqlite.py          # Database service and operations
```

### Key Components

#### Models (`models.py`)
- **`EventOdds`**: Represents NFL game data with teams, spreads, and metadata
- **`Pick`**: Represents a survivor pool pick with team, week, and spread information

#### Optimizer (`optimizer.py`)
- **`PickOptimizer`**: Main optimization engine with three algorithm implementations
- **Future Value Calculation**: Advanced metrics for team value assessment

#### Services (`services/`)
- **`CBSSportsService`**: Data source for NFL odds and spreads
- **`DatabaseService`**: SQLite database operations and data persistence

## Data Sources

### CBS Sports
- **URL Pattern**: `https://www.cbssports.com/nfl/scoreboard/{year}/regular/{week}/`
- **Data**: Point spreads, team matchups, game IDs
- **Parsing**: HTML scraping using BeautifulSoup

## Configuration

### User-Defined Picks
Modify the `user_defined_picks` list in `main.py` to include your existing picks:

```python
user_defined_picks = [
    Pick(team="SEA", week=1, spread=6.0),
    Pick(team="HOU", week=2, spread=6.5),
    Pick(team="CLE", week=3, spread=6.5),
    # Add more picks as needed
]
```

### Current Week
Update the `current_week` variable in `main.py` to reflect the current NFL week:

```python
current_week = 4  # Update this each week
```

## Output Formats

### Console Table
Color-coded table showing picks across all algorithms:
- **Red**: Picks that differ between algorithms
- **Yellow**: Picks that changed from the previous split week
- **White**: Standard picks

### CSV Export
Three data sets per algorithm:
1. Team abbreviations with spreads: `"SEA (6.0)"`
2. Team abbreviations only: `"SEA"`
3. Spreads only: `"6.0"`

## Advanced Usage

### Custom Algorithm Development
Extend the `PickOptimizer` class to implement custom algorithms:

```python
def find_optimal_picks_custom(self, events, split_week, user_defined_picks=None):
    return self.__find_optimal_picks(
        events=events,
        split_week=split_week,
        user_defined_picks=user_defined_picks,
        sort_key=lambda event: your_custom_logic(event)
    )
```

### Database Queries
Direct database access for custom analysis:

```python
from services import DatabaseService

db = DatabaseService()
events = db.fetch_odds_data(2024)
# Perform custom analysis
db.close()
```

## Troubleshooting

### Common Issues

#### Data Fetching Errors
- **Problem**: Network errors or site structure changes
- **Solution**: Check internet connection and verify CBS Sports site availability

#### Missing Spreads
- **Problem**: Some games show "PK" (Pick'em) instead of numerical spreads
- **Solution**: Application handles this automatically by converting to 0.0

#### Database Issues
- **Problem**: SQLite database corruption or access issues
- **Solution**: Delete `odds_data.db` and re-run with `--refresh`

### Error Messages

#### "Error - Week N - Type - event_id"
CBS Sports parsing failed for a specific game. Usually resolved by re-running the refresh.


## Contributing

### Development Setup
1. Fork the repository
2. Create a feature branch
3. Install development dependencies
4. Run tests (if available)
5. Submit a pull request

### Code Style
- Follow PEP 8 Python style guidelines
- Use type hints where applicable
- Add docstrings to new functions
- Maintain existing code organization

### Testing
Run manual tests with sample data:
```bash
python main.py --refresh --year 2023  # Use previous season
python main.py --print-table
```

## License

This project does not currently include a license file. Please contact the project maintainer for licensing information.

## Disclaimer

This tool is for educational and entertainment purposes only. Sports betting and fantasy football involve risk. Always verify data independently and gamble responsibly.

## Support

For issues, questions, or contributions, please:
1. Check existing documentation
2. Review troubleshooting section
3. Submit detailed issue reports with error messages and steps to reproduce

---

**Happy surviving!** 🏈