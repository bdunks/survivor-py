# NFL Survivor Pool Optimizer

A small FastAPI web app for planning an NFL survivor pool. It fetches point spreads from CBS Sports and recommends one unused team per week with three different optimization strategies. The frontend keeps an 18-week schedule grid for manual review, sorting, and pick locking.

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
2. Select **Refresh Data** to fetch odds from the current week through week 18.
3. Choose an algorithm and review its suggested picks in the schedule grid.
4. Set **Projected Pool End Week** to the expected last week of your pool.
5. Change the algorithm selector to inspect each strategy and compare the suggestions manually. One selected algorithm is shown at a time.
6. Click grid cells to lock or unlock picks. Team and week columns are sortable, and **Reset Picks** clears all manual picks.

The grid always renders all 18 weeks. Projected Pool End Week is the optimization horizon: recommendations prioritize weeks through that week and do not reserve teams merely for weeks after it.

## Algorithms

- **Best Spread** chooses the highest point-spread favorite available for each week, favoring the safest individual matchups.
- **Back-to-Front** considers the schedule from later weeks back toward the beginning, using week position and spread to preserve a workable season plan.
- **Weighted Future Value** balances a game's spread with the team's available future value and the position of the week, making a season-wide tradeoff rather than choosing only the largest current spread.

All algorithms respect manual picks and the one-team-per-season and one-pick-per-week constraints.

## Configuration and local data

`config.example.json` is the canonical configuration example. Its keys are:

- `current_week`: the first week used when refreshing CBS data
- `picks`: saved manual picks, each containing a team, week, and optional spread
- `algorithm`: the selected algorithm slug
- `split_week`: the projected pool-end/optimization horizon

The app reads and writes `config.json` in the repository directory. Odds are stored in the local SQLite database `odds_data.db`. Both runtime files are ignored and should not be committed.

## CBS Sports data

Refreshing requires network access and depends on CBS Sports' HTML structure. Games with missing or malformed identifiers, matchups, or spreads are skipped. Network failures skip the affected week. The scraper provides no retries, caching, proxy support, or rate-limit support.

## Development checks

Before committing, run:

```bash
mise run check
```

This runs `ruff check --fix --unsafe-fixes .`, `ruff format .`, and the standard-library tests in order. Ruff's unsafe fixes are assumed safe; only issues remaining after autofix need manual attention. Run `mise run lint`, `mise run format`, or `mise run test` individually when needed.
