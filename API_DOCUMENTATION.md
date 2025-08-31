# API Documentation

This document provides detailed technical documentation for the Survivor Pool Optimizer's internal APIs and class interfaces.

## Table of Contents

1. [Core Models](#core-models)
2. [Pick Optimizer API](#pick-optimizer-api)
3. [Data Services](#data-services)
4. [Database Service](#database-service)
5. [Utility Classes](#utility-classes)
6. [Error Handling](#error-handling)

## Core Models

### EventOdds

The `EventOdds` dataclass represents a single NFL game with betting odds information.

```python
@dataclass
class EventOdds:
    event_id: int
    season_year: int
    week: int
    short_name: str
    spread: float
    away_team: str = field(init=False)
    home_team: str = field(init=False)
    favored_team: str = field(init=False)
```

#### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `event_id` | `int` | Unique identifier for the game |
| `season_year` | `int` | NFL season year (e.g., 2024) |
| `week` | `int` | Week number (1-18 for regular season) |
| `short_name` | `str` | Game description (e.g., "SEA@SF", "DAL VS NE") |
| `spread` | `float` | Point spread (positive = away team favored) |
| `away_team` | `str` | Away team abbreviation (auto-generated) |
| `home_team` | `str` | Home team abbreviation (auto-generated) |
| `favored_team` | `str` | Favored team abbreviation (auto-generated) |

#### Post-Initialization Processing

The `__post_init__` method automatically processes the `short_name` field to extract:
- Away and home team names (split by "@" or "VS")
- Favored team (determined by spread sign: negative = home favored, positive = away favored)

#### Example Usage

```python
event = EventOdds(
    event_id=12345,
    season_year=2024,
    week=1,
    short_name="SEA@SF",
    spread=-3.5
)

print(event.away_team)    # "SEA"
print(event.home_team)    # "SF"
print(event.favored_team) # "SF" (spread is negative)
```

### Pick

The `Pick` class represents a single survivor pool team selection.

```python
class Pick(NamedTuple):
    team: str
    week: int
    spread: Optional[float] = None
```

#### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `team` | `str` | Team abbreviation (e.g., "SEA", "DAL") |
| `week` | `int` | Week number for the pick |
| `spread` | `Optional[float]` | Point spread value (optional) |

#### Example Usage

```python
pick = Pick(team="SEA", week=1, spread=6.0)
user_pick = Pick(team="DAL", week=2)  # Spread optional
```

## Pick Optimizer API

### PickOptimizer

The main optimization engine that implements multiple algorithms for generating optimal survivor pool picks.

```python
class PickOptimizer:
    def find_optimal_picks_best_spread(
        self,
        events: List[EventOdds],
        split_week: int,
        user_defined_picks: Optional[List[Pick]] = None,
    ) -> List[Pick]

    def find_optimal_picks_back_to_front(
        self,
        events: List[EventOdds],
        split_week: int,
        user_defined_picks: Optional[List[Pick]] = None,
    ) -> List[Pick]

    def find_optimal_picks_weighted_future_value(
        self,
        events: List[EventOdds],
        split_week: int,
        user_defined_picks: Optional[List[Pick]] = None,
    ) -> List[Pick]

    def calculate_future_value(
        self,
        team: str,
        week: int,
        events: List[EventOdds],
        split_week: int = 18
    ) -> float

    def calculate_future_value_for_all_teams(
        self,
        week: int,
        future_events: List[EventOdds]
    ) -> List[float]
```

### Algorithm Methods

#### find_optimal_picks_best_spread()

**Purpose**: Generate picks prioritizing highest spreads (safest picks).

**Parameters**:
- `events` (`List[EventOdds]`): All available games for the season
- `split_week` (`int`): Week to split season strategy (1-18)
- `user_defined_picks` (`Optional[List[Pick]]`): Pre-selected picks to preserve

**Returns**: `List[Pick]` - Optimized picks for all 18 weeks

**Algorithm Logic**:
1. Preserves all user-defined picks
2. Sorts remaining games by absolute spread value (descending)
3. Selects highest spread games while avoiding:
   - Teams already picked
   - Weeks already filled
4. Ensures exactly 18 picks (one per week)

**Example Usage**:
```python
optimizer = PickOptimizer()
user_picks = [Pick(team="SEA", week=1, spread=6.0)]

picks = optimizer.find_optimal_picks_best_spread(
    events=season_events,
    split_week=10,
    user_defined_picks=user_picks
)
```

#### find_optimal_picks_back_to_front()

**Purpose**: Strategic algorithm considering week positioning and timing.

**Parameters**: Same as `find_optimal_picks_best_spread()`

**Algorithm Logic**:
1. Splits season at `split_week`
2. First half: Sorts by week, then spread (early weeks prioritized)
3. Second half: Sorts by reverse week, then spread (late weeks prioritized)
4. Balances immediate safety with strategic timing

#### find_optimal_picks_weighted_future_value()

**Purpose**: Advanced algorithm incorporating future team value calculations.

**Parameters**: Same as `find_optimal_picks_best_spread()`

**Algorithm Logic**:
1. Calculates future value for each team based on:
   - Future games where team is favored
   - Strength of future spreads
   - Scaling factor based on week position
2. Combines current spread with inverse future value
3. Uses power scaling (default: 2.5) for temporal weighting
4. Includes second-pass optimization for better picks

#### calculate_future_value()

**Purpose**: Calculate a team's future value based on upcoming favorable games.

**Parameters**:
- `team` (`str`): Team abbreviation to analyze
- `week` (`int`): Current week (analysis starts from week + 1)
- `events` (`List[EventOdds]`): All season events
- `split_week` (`int`): Week limit for analysis (default: 18)

**Returns**: `float` - Future value score

**Calculation Method**:
```python
future_value = favorable_game_count + sum(favorable_spreads)
```

**Example Usage**:
```python
optimizer = PickOptimizer()
future_value = optimizer.calculate_future_value(
    team="SEA",
    week=4,
    events=season_events,
    split_week=16
)
```

### Private Methods

#### __find_optimal_picks()

The core optimization engine used by all public algorithms. Handles the common logic:

**Parameters**:
- `events` (`List[EventOdds]`): All season events
- `split_week` (`int`): Strategy split point
- `user_defined_picks` (`Optional[List[Pick]]`): Pre-selected picks
- `sort_key` (`Optional[Callable]`): Primary sorting function
- `second_pass_sort_key` (`Optional[Callable]`): Secondary optimization function
- `sort_key_second_half` (`Optional[Callable]`): Second half sorting function

**Internal Logic**:
1. Preserves user-defined picks
2. Splits events by split week
3. Applies sorting strategies
4. Runs two-pass optimization (if specified)
5. Ensures no duplicate teams or weeks
6. Returns exactly 18 picks

## Data Services

### CBSSportsService

Primary data source for NFL odds and game information.

```python
class CBSSportsService:
    def __init__(self)
    def fetch_events(self, season_year: int, starting_week: int = 1) -> List[EventOdds]
    def fetch_soup(self, url: str) -> BeautifulSoup
    def check(self, event_id, short_name, spread) -> Optional[Error]
```

#### fetch_events()

**Purpose**: Scrape NFL game data from CBS Sports website.

**Parameters**:
- `season_year` (`int`): NFL season year
- `starting_week` (`int`): First week to fetch (default: 1)

**Returns**: `List[EventOdds]` - All games from specified weeks

**Process**:
1. Iterates through weeks (starting_week to 18)
2. Fetches HTML from CBS Sports scoreboard pages
3. Parses game cards using BeautifulSoup
4. Extracts event ID, team names, and spreads
5. Handles "PK" (pick'em) games as 0.0 spread
6. Returns structured EventOdds objects

**URL Pattern**:
```
https://www.cbssports.com/nfl/scoreboard/{year}/regular/{week}/
```

**Error Handling**:
- Network errors: Raises HTTP exceptions
- Parsing errors: Logs and continues processing
- Missing data: Uses Error class for tracking

#### Example Usage:
```python
service = CBSSportsService()
events = service.fetch_events(season_year=2024, starting_week=1)

for event in events:
    print(f"Week {event.week}: {event.short_name} ({event.spread})")
```

### EspnService

Alternative data source using ESPN's API.

```python
class EspnService:
    def __init__(self)
    def fetch_events(self, season_year: int, starting_week: int = 1) -> List[EventOdds]
    def fetch_json(self, url: str) -> dict
```

#### fetch_events()

**Purpose**: Fetch NFL game data from ESPN API with averaged spreads.

**Parameters**: Same as CBSSportsService

**Process**:
1. Fetches week data from ESPN API
2. For each game, retrieves detailed event data
3. Fetches odds data and calculates average spreads
4. Handles missing or incomplete data gracefully

**URL Pattern**:
```
http://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/{year}/types/2/weeks/{week}/events
```

**Advantages**:
- Structured JSON data
- Multiple odds sources averaged
- Comprehensive game metadata

**Disadvantages**:
- More complex API structure
- Requires multiple HTTP requests per game
- Potential for missing odds data

## Database Service

### DatabaseService

SQLite database management for persistent odds storage.

```python
class DatabaseService:
    def __init__(self, db_name: str = "odds_data.db")
    def setup_database(self) -> None
    def save_odds_data(self, data: List[EventOdds]) -> None
    def fetch_odds_data(self, year: int) -> List[EventOdds]
    def insert_or_replace_data(
        self,
        table_name: str,
        columns: List[str],
        data: List[Tuple]
    ) -> None
    def close(self) -> None
```

#### Database Schema

**Table: averaged_odds**
```sql
CREATE TABLE IF NOT EXISTS averaged_odds (
    event_id INTEGER PRIMARY KEY,
    season_year INTEGER,
    week INTEGER,
    home_team TEXT,
    away_team TEXT,
    short_name TEXT,
    spread REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP                            
)
```

#### save_odds_data()

**Purpose**: Store or update odds data in the database.

**Parameters**:
- `data` (`List[EventOdds]`): Event data to store

**Process**:
1. Converts EventOdds objects to database tuples
2. Uses INSERT OR REPLACE for upsert behavior
3. Automatically updates timestamps
4. Commits transaction

#### fetch_odds_data()

**Purpose**: Retrieve stored odds data for a specific season.

**Parameters**:
- `year` (`int`): Season year to retrieve

**Returns**: `List[EventOdds]` - All games for the specified year

**Process**:
1. Queries database by season_year
2. Converts database rows back to EventOdds objects
3. Returns sorted list

#### Example Usage:
```python
db = DatabaseService()

# Save new data
db.save_odds_data(events)

# Retrieve data
stored_events = db.fetch_odds_data(2024)

# Clean up
db.close()
```

## Utility Classes

### CSVLogger

Custom logging utility for CSV file output.

```python
class CSVLogger(logging.Logger):
    def __init__(self, name: str)
    def log(self, msg: Iterable[Any], level: int = logging.INFO) -> None
```

#### Purpose
Enable structured CSV logging for algorithm analysis and debugging.

#### Usage Pattern:
```python
import logging
from logger import CSVLogger

logging.setLoggerClass(CSVLogger)
csv_logger = logging.getLogger("algorithm_analysis")

# Log header
csv_logger.log([
    "Split Week", "Week", "Team", "Event", 
    "Spread", "Future Value", "Score"
])

# Log data rows
csv_logger.log([
    split_week, event.week, event.favored_team, 
    event.short_name, event.spread, future_value, score
])
```

#### Output Format
- Filename: `log/{logger_name}_{timestamp}.csv`
- Automatic file creation and management
- Real-time writing with flush for immediate availability

### Error Class

Simple error tracking for data validation.

```python
class Error:
    type: str
```

#### Usage:
```python
def check(self, event_id, short_name, spread):
    if event_id is None:
        return Error("event_id")
    if short_name is None:
        return Error("short_name")
    if spread is None:
        return Error("spread")
    return None  # No error
```

## Error Handling

### Network Errors
- **HTTP Errors**: Raised by `requests` library, caught by calling code
- **Connection Issues**: Service methods use `raise_for_status()` for immediate failure
- **Timeout Handling**: Not explicitly implemented, uses requests defaults

### Data Parsing Errors
- **CBS Sports**: Individual game parsing errors logged but don't stop processing
- **ESPN API**: KeyError and general exceptions caught per game
- **Missing Fields**: Error class tracks validation issues

### Database Errors
- **Connection Issues**: SQLite exceptions propagate to calling code  
- **Schema Problems**: `setup_database()` creates tables if they don't exist
- **Data Integrity**: Uses `INSERT OR REPLACE` for conflict resolution

### Application-Level Error Handling

```python
try:
    service = CBSSportsService()
    events = service.fetch_events(2024)
except requests.RequestException as e:
    print(f"Network error: {e}")
    # Handle gracefully - perhaps use cached data

try:
    db = DatabaseService()
    db.save_odds_data(events)
except sqlite3.Error as e:
    print(f"Database error: {e}")
    # Handle gracefully - perhaps continue without saving
finally:
    db.close()
```

## Best Practices

### Resource Management
- Always call `DatabaseService.close()` when done
- Use try/finally blocks for database connections
- CSV loggers automatically flush, but consider explicit file management

### Error Recovery
- Network failures: Implement retry logic or use cached data
- Parsing failures: Log errors but continue processing other games
- Database issues: Degrade gracefully, perhaps to in-memory operation

### Performance Considerations
- Database queries filter by year to minimize data transfer
- CBS Sports scraping processes weeks sequentially to be respectful
- ESPN API requires multiple requests per game - consider rate limiting

### Testing and Validation
- Validate data completeness after fetching
- Test algorithms with known data sets
- Verify user-defined picks are properly preserved
- Check for off-by-one errors in week calculations

---

This API documentation should be used in conjunction with the main README.md for complete understanding of the system architecture and usage patterns.