# NFL Survivor Pool Optimizer

A small FastAPI web app for planning an NFL survivor pool. It fetches point spreads from CBS Sports and recommends one unused team per week with four optimization strategies. The frontend keeps an 18-week schedule grid for manual review, sorting, and pick locking.

## Requirements

- Python 3.13 or newer
- [Mise](https://mise.jdx.dev/)
- Network access to CBS Sports when refreshing odds

## Install

From the repository directory:

```bash
mise install
uv sync --locked
```

Mise installs the project tools: the latest UV and Ruff 0.16.6. Runtime dependencies are declared in `pyproject.toml` and locked in `uv.lock`.

## Run the web app

```bash
mise run dev
```

Open <http://127.0.0.1:8000/>. FastAPI serves the static frontend and API from the same origin. Interactive API documentation is available at <http://127.0.0.1:8000/docs>.

## Weekly workflow

1. Select the season and enter the current week.
2. Select **Refresh Data** to fetch the latest odds and finalize the previous week's results. Refresh requests `max(1, current_week - 1)` through week 18 from CBS Sports, updating current game state, closing lines (last pre-kickoff observations), and final results.
3. Choose an algorithm and review its suggested picks in the schedule grid.
4. Set **Projected Pool End Week** to the expected last week of your pool.
5. Change the algorithm selector to inspect each strategy and compare the suggestions manually. One selected algorithm is shown at a time.
6. Click grid cells to lock or unlock picks. When you save the first pick for a survivor week, the application freezes an immutable decision snapshot capturing the complete optimizer input at that time. Team and week columns are sortable, and **Reset Picks** clears all manual picks.

The grid always renders all 18 weeks. Projected Pool End Week is the optimization horizon: recommendations prioritize weeks through that week and do not reserve teams merely for weeks after it.
## Algorithms

- **Best Spread** chooses the highest point-spread favorite available for each week, favoring the safest individual matchups.
- **Back-to-Front** considers the schedule from later weeks back toward the beginning, using week position and spread to preserve a workable season plan.
- **Weighted Future Value** subtracts a tunable penalty for the team's best future favorite matchup from its current spread, reserving high-value teams when worthwhile.
- **Global Max Survival** assigns the complete optimization horizon at once, maximizing the combined estimated survival probability while using each team only once.

All algorithms respect manual picks and the one-team-per-season and one-pick-per-week constraints.

## Configuration and local data

`config.example.json` documents the UI preference keys:

- `current_week`: the first week used when refreshing CBS data
- `algorithm`: the selected algorithm slug
- `split_week`: the projected pool-end/optimization horizon

`config.json` retains these preferences. Actual picks are season-aware `pick_events` in SQLite, not configuration entries.

If an older `config.json` still has `picks`, choose its season explicitly and run the one-time migration endpoint:

```bash
curl -X POST "http://127.0.0.1:8000/api/config/picks/migrate?season_year=2025"
```

`season_year` is required; the app never infers it. Valid picks are imported with a migration timestamp, a legacy-marked snapshot, and the original pick order, then `config.json` picks are cleared. Invalid or duplicate picks leave the file unchanged. Repeating the migration is safe. Legacy-marked snapshots are excluded from strict backtests because their original decision times are unknown.

The app reads and writes `config.json` in the repository directory. Odds and pick history are stored in the local SQLite database `odds_data.db`. Both runtime files are ignored and should not be committed.

## CBS Sports data

Refreshing requires network access and depends on CBS Sports' HTML structure. Games with missing or malformed identifiers, matchups, or spreads are skipped. Network failures skip the affected week. The scraper provides no retries, caching, proxy support, or rate-limit support.


## Historical data and backtesting

The application preserves point-in-time observations for offline algorithm evaluation.

### Data model

- **Current state:** the latest successfully fetched schedule and spreads, updated in place on every refresh. This is what the live UI displays.
- **Decision snapshot:** an immutable complete optimizer input frozen when the first actual pick for a season/week is saved. Each survivor week has at most one authoritative snapshot.
- **Actual picks:** the season-aware pick event ledger recording every `set` and `clear` action with server timestamps.
- **Recorded recommendations:** the output of a live optimization request, persisted in `optimization_runs` with its algorithm, parameters, source revision, generation time, and snapshot ID; it is not an actual pick.
- **Closing lines:** the last spread observed before each game's kickoff. These are evaluation benchmarks, not decision inputs.
- **Final results:** authoritative game status and scores, with observed and correction timestamps.
- **Simulated picks:** selections generated during a backtest from each authoritative snapshot and prior simulated picks; they are report output, not actual `pick_events`.

### End-of-season workflow

After the regular season completes and final scores settle:

1. Select the completed season and set `current_week` to 1 in the configuration.
2. Run **Refresh Data** once to fetch weeks 1–18 and finalize all results.
3. Backup the database (see below).

### Running backtests

A strict authoritative-snapshot backtest uses the immutable decision snapshot for each week and never substitutes later current state. Run it from the repository directory:

```bash
uv run python backtest.py --season 2025 --algorithm best-spread --mode strict --output results.json
```

**Modes:**

- `strict` (default): requires a decision snapshot for every week; fails if any are missing.
- `degraded`: skips weeks with missing snapshots and reports which weeks were excluded.

**Output metrics (aggregate):**

- `first_elimination_week`: first week with a loss or tie; null if no elimination occurs.
- `wins`, `losses`, `ties`, `ungraded`: counts of each weekly outcome. Ties remain separately counted but trigger elimination like losses.
- `weeks_survived`: number of weekly selections represented in the report; selections after elimination are marked counterfactual.
- `avg_decision_spread`: mean absolute spread for selected teams from the authoritative decision snapshots.
- `avg_closing_spread`: mean absolute closing spread for selected games; weeks without a closing line are omitted.
- `avg_decision_to_closing`: mean change from decision to close, calculated as absolute closing spread minus absolute decision spread.
- `avg_selected_vs_best_alternative`: mean selected absolute spread minus the best legal same-week alternative in the snapshot.

**Output formats:**

- JSON (default): `--format json`
- CSV: `--format csv`

**Important limitations:**

- Spread metrics are not calibrated win probabilities. They measure relative optimizer behavior, not absolute skill.
- Closing lines represent the last spread this application observed, not guaranteed sportsbook market closes.
- Missing decision snapshots cannot be synthesized; strict mode correctly fails rather than substituting later data.

### Database backup and restore

The local SQLite database `odds_data.db` contains current observations, decision snapshots, actual picks, recorded recommendations, and results. Use the standard-library `Connection.backup()` helper:

```python
from services import backup_database

backup_database("odds_data.db", "odds_data_backup.db")
backup_database(
    "odds_data_backup.db", "odds_data_restored.db"
)  # verify/restore to a temp path
```

To restore the live database, stop the app first and restore into `odds_data.db`:

```python
backup_database("odds_data_backup.db", "odds_data.db")
```

A filesystem copy is also valid:

```bash
cp odds_data.db odds_data_backup.db
cp odds_data_backup.db odds_data.db  # restore after stopping the app
```

### Database growth

- One decision snapshot per season/survivor week (at most 18 per season).
- One pick event per actual `set` or `clear` action.
- One optimization run per algorithm evaluation shown to the user.
- **Refresh-run metadata:** one small retained record per refresh attempt, including requested weeks, times, status, and errors. Even 168 attempts per week is only a few thousand rows per season.
- Raw CBS HTML payloads are retained only for failed parser diagnosis; successful routine refresh payloads are not archived.
- Current game state, closing lines, and final results are one row per event, updated in place.

Bounded growth: the database scales with decision points, not refresh frequency.
## Development checks

Before committing, run:

```bash
mise run check
```

This runs `ruff check --fix --unsafe-fixes .`, `ruff format .`, and the standard-library tests in order. Ruff's unsafe fixes are assumed safe; only issues remaining after autofix need manual attention. Run `mise run lint`, `mise run format`, or `mise run test` individually when needed.
