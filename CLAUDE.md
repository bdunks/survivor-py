# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a comprehensive NFL survivor pool optimizer with both **web interface** and **command-line interface**. The application fetches odds data from CBS Sports and provides algorithmic strategies for team selection using three different optimization algorithms across the entire 18-week NFL regular season.

## Development Commands

### Web Interface (Primary)

```bash
# Install tools
mise install
# Install dependencies from pyproject.toml
uv sync

# Start web server for development
mise run dev

# Access web interface
# http://127.0.0.1:8000/

# Access API documentation  
# http://127.0.0.1:8000/docs
```

### Command Line Interface (Legacy)

```bash
# Run CLI application with help
python main.py --help

# Configuration management
python main.py --status
python main.py --set-week 5
python main.py --add-pick "SEA:1:6.0"
python main.py --clear-pick 1

# Data operations
python main.py --refresh --year 2024

# Analysis and visualization
python main.py --print-table
python main.py --split-week 10
python main.py --compare
python main.py --export
```

### Code Formatting

The project uses Ruff for code formatting and linting via Mise tasks:

```bash
# Format code
mise run format

# Lint code
mise run lint
```

## Architecture

### Web Application Components

**FastAPI Application (`app.py`)**

- REST API with automatic OpenAPI documentation
- Static file serving for web interface  
- Complete API endpoints for configuration, optimization, and data management
- Type-safe request/response validation using Pydantic

**API Models (`api_models.py`)**

- Pydantic models for API validation: `ConfigResponse`, `PickRequest`, `OptimizationResponse`
- Input validation for team codes, weeks, and parameters
- Structured error responses

**Frontend (`static/index.html`)**

- Modern responsive web interface using Pico CSS
- Real-time JavaScript integration with FastAPI backend
- Interactive user pick management and split week analysis

### Core Components

**CLI Entry Point (`main.py`)**

- Command-line interface with argument parsing
- Configuration management via CLI commands
- Legacy console output and CSV export

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

**Web Interface:**
1. User interactions → FastAPI endpoints → Core services
2. Configuration automatically saved to `config.json`
3. Real-time optimization results returned as JSON
4. CSV export downloads generated on-demand

**CLI Interface:**
1. CBS Sports scraper fetches odds → SQLite database
2. Database provides events to optimizer
3. Optimizer applies algorithms with user-defined picks
4. Results exported to console tables or CSV files

### Configuration Management

**Web Interface (Recommended):**
- Configuration managed via web UI and automatically saved to `config.json`
- User picks added through dropdown menus
- Real-time persistence and validation

**CLI Configuration:**
```bash
# Configuration commands
python main.py --status
python main.py --set-week 5
python main.py --add-pick "SEA:1:6.0"
python main.py --clear-pick 1
```

**Configuration File (`config.json`):**
```json
{
  "current_week": 4,
  "picks": [
    {"team": "SEA", "week": 1, "spread": 6.0}
  ]
}
```

## Database Schema

SQLite database (`odds_data.db`) with `averaged_odds` table:

- event_id (PRIMARY KEY)
- season_year, week
- home_team, away_team, short_name
- spread (point spread)
- created_at, updated_at timestamps

## Dependencies

Dependencies are declared in `pyproject.toml`:

**Web Interface:**
- `fastapi`: Modern web framework for APIs
- `uvicorn`: ASGI server for FastAPI
- `pydantic`: Data validation using Python type hints

**Core Application:**
- `requests`: HTTP client for CBS Sports data
- `termcolor`: Console output coloring (CLI only)
- `beautifulsoup4`: HTML parsing for web scraping

## Testing

### Web Interface Testing

```bash
# Start development server
uvicorn app:app --reload --host 127.0.0.1 --port 8000

# Test API endpoints
curl http://127.0.0.1:8000/api/config
curl http://127.0.0.1:8000/api/teams
curl http://127.0.0.1:8000/api/status

# Access interactive API documentation
# http://127.0.0.1:8000/docs

# Test web interface
# http://127.0.0.1:8000/
```

### CLI Testing

```bash
# Test with previous season data
python main.py --print-table

# Test configuration commands
python main.py --status
python main.py --add-pick "SEA:1:6.0"
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
        sort_key=lambda event: your_custom_logic(event),
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
