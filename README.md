# NFL Survivor Pool Optimizer

A comprehensive Python application with both **web interface** and **command-line interface** for optimizing NFL survivor pool picks using multiple algorithmic strategies.

## Overview

Survivor pools (also known as elimination pools) are fantasy football contests where participants pick one NFL team to win each week. The catch: once you pick a team, you cannot pick them again for the remainder of the season. If your picked team loses, you're eliminated from the pool. This tool helps optimize team selections to maximize your chances of surviving the entire 18-week NFL regular season.

## Features

### 🌐 **Web Interface** (Recommended)
- **Modern Web UI**: Interactive dashboard with responsive design using Pico CSS
- **Real-time Optimization**: Live updates as you adjust split weeks and user picks  
- **User Pick Management**: Add/remove picks with dropdown selections
- **Algorithm Comparison**: Side-by-side visualization of all three optimization strategies
- **Color-coded Results**: Visual indicators for algorithm differences and week-to-week changes
- **CSV Export**: Download optimized picks directly from the browser
- **FastAPI Backend**: Type-safe REST API with automatic documentation

### 📊 **Core Optimization Engine**
- **Data Fetching**: Retrieves NFL odds and spread data from CBS Sports
- **SQLite Database Storage**: Persistent storage of odds data with automatic table creation
- **Multiple Optimization Algorithms**:
  - **Best Spread**: Prioritizes teams with the highest point spreads (safest picks)
  - **Back-to-Front**: Strategic timing-based approach that considers week positioning  
  - **Weighted Future Value**: Advanced algorithm that considers a team's future value and availability
- **User-Defined Picks**: Full support for manual pick overrides and existing selections

### 🖥️ **Command Line Interface**
- **Interactive Analysis Tools**: Table-based visualization with color-coded differences
- **Algorithm Comparison**: Detailed pick analysis and performance metrics
- **Split-week Analysis**: Strategic planning across different timeframes
- **Export Functionality**: Multiple CSV format options

## Installation

### Prerequisites

- Python 3.8 or higher
- UV package manager (recommended) or pip

### Quick Start (Web Interface)

1. Clone or download the repository:
```bash
git clone <repository-url>
cd survivor-py
```

2. Install dependencies:
```bash
# Using UV (recommended)
uv add fastapi uvicorn[standard] pydantic python-multipart requests termcolor beautifulsoup4

# Or using pip
pip install -r requirements.txt
```

3. Start the web interface:
```bash
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

4. Open your browser to: **http://127.0.0.1:8000/**

### Command Line Interface

For CLI-only usage:
```bash
python main.py --help
```

## Usage

### 🌐 Web Interface (Recommended)

#### Getting Started
1. Start the server: `uvicorn app:app --reload --host 127.0.0.1 --port 8000`
2. Navigate to: **http://127.0.0.1:8000/**
3. The interface loads automatically with current configuration

#### Key Features

**User Pick Management:**
- Use dropdown menus for each week to select teams
- Picks are automatically saved and incorporated into optimization
- Clear picks by selecting "Select Team" option

**Split Week Analysis:**
- Adjust the slider to see how different split weeks affect optimization
- Real-time updates show all three algorithms simultaneously
- Color coding indicates:
  - 🔴 **Red**: Algorithm disagreements (different team choices)
  - 🟡 **Yellow**: Changes from previous split week
  - ⚪ **Gray**: Consensus picks

**Data Management:**
- **Refresh Data**: Updates odds from CBS Sports for selected year
- **Export CSV**: Downloads optimized picks for all algorithms
- **Season Selection**: Choose different years (2023-2025)

**Algorithm Comparison:**
View all three strategies side-by-side:
- **Best Spread**: Conservative, highest-spread picks
- **Back-to-Front**: Strategic timing-based approach  
- **Weighted Future Value**: Advanced algorithm considering future team value

#### API Documentation
Access interactive API docs at: **http://127.0.0.1:8000/docs**

### 🖥️ Command Line Interface

#### Basic Commands

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
├── app.py                  # FastAPI web application and REST API
├── api_models.py           # Pydantic models for API validation
├── main.py                 # Command-line interface (original)
├── models.py               # Core data models (EventOdds, Pick)
├── optimizer.py            # Pick optimization algorithms  
├── requirements.txt        # Python dependencies
├── config.json            # User configuration and picks (auto-created)
├── odds_data.db           # SQLite database (auto-created)
├── static/
│   └── index.html         # Web interface frontend
├── services/
│   ├── __init__.py        # Service module initialization
│   ├── cbssports.py       # CBS Sports data fetching service
│   └── sqlite.py          # Database service and operations
└── llm_context/
    ├── front_end.html     # Original frontend template
    └── implementation_plan.md  # Development documentation
```

### Key Components

#### Web Application (`app.py`)
- **FastAPI Application**: Modern REST API with automatic OpenAPI documentation
- **Static File Serving**: Hosts the web interface at root path
- **API Endpoints**: Full CRUD operations for configuration and optimization
- **Error Handling**: Structured error responses with proper HTTP status codes

#### API Models (`api_models.py`)
- **Pydantic Models**: Type-safe request/response validation
- **ConfigResponse, PickRequest, OptimizationResponse**: Structured API data models
- **Input Validation**: Automatic validation for team codes, weeks, and parameters

#### Core Models (`models.py`)
- **`EventOdds`**: Represents NFL game data with teams, spreads, and metadata
- **`Pick`**: Represents a survivor pool pick with team, week, and spread information

#### Optimizer (`optimizer.py`)
- **`PickOptimizer`**: Main optimization engine with three algorithm implementations
- **Future Value Calculation**: Advanced metrics for team value assessment

#### Services (`services/`)
- **`CBSSportsService`**: Data source for NFL odds and spreads
- **`DatabaseService`**: SQLite database operations and data persistence

#### Frontend (`static/index.html`)
- **Responsive Design**: Modern UI using Pico CSS framework
- **Real-time Updates**: JavaScript integration with FastAPI backend
- **Interactive Features**: User pick management, split week analysis, CSV export

## Data Sources

### CBS Sports
- **URL Pattern**: `https://www.cbssports.com/nfl/scoreboard/{year}/regular/{week}/`
- **Data**: Point spreads, team matchups, game IDs
- **Parsing**: HTML scraping using BeautifulSoup

## Configuration

### Web Interface Configuration
Configuration is managed through the web interface and automatically saved to `config.json`:

**Via Web UI:**
1. Open http://127.0.0.1:8000/
2. Select teams from dropdown menus for each week
3. Picks are automatically saved and applied to optimization
4. Current week and all picks persist between sessions

**Configuration File (`config.json`):**
```json
{
  "current_week": 4,
  "picks": [
    {"team": "SEA", "week": 1, "spread": 6.0},
    {"team": "HOU", "week": 2, "spread": 6.5}
  ]
}
```

### Command Line Configuration
For CLI usage, modify the configuration in `main.py`:

```python
user_defined_picks = [
    Pick(team="SEA", week=1, spread=6.0),
    Pick(team="HOU", week=2, spread=6.5),
    Pick(team="CLE", week=3, spread=6.5),
    # Add more picks as needed
]

current_week = 4  # Update this each week
```

### CLI Configuration Management
```bash
# Set current week
python main.py --set-week 5

# Add a pick
python main.py --add-pick "SEA:1:6.0"

# Clear a specific week's pick
python main.py --clear-pick 1

# Clear all picks
python main.py --clear-pick all

# View current configuration
python main.py --status
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