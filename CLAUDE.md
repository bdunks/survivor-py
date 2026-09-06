# CLAUDE.md

This repository is an NFL survivor pool optimizer delivered as a small FastAPI application with a vanilla HTML, CSS, and JavaScript frontend.

## Tooling and commands

The project requires Python 3.13 or newer. Mise provides the latest UV and Ruff 0.16.6.

```bash
mise install
uv sync --locked
mise run dev
```

The development server runs at <http://127.0.0.1:8000/>. Use these checks before committing:

```bash
mise run lint
mise run format-check
mise run test
mise run check
python -m compileall -q .
```

`mise run format` applies Ruff formatting. `mise run check` composes linting, formatting checks, and the standard-library test suite. The `dev` task runs `uv run uvicorn app:app --reload --host 127.0.0.1 --port 8000`.

## Architecture

- `app.py`: FastAPI application, team allowlist, route handlers, response construction, and the static frontend mount at `/`.
- `api_models.py`: Pydantic request and response models for picks, configuration, events, and optimization results.
- `config_store.py`: Function-only JSON configuration loading, validation, updates, and atomic saves.
- `models.py`: Domain values: `EventOdds` and `Pick`.
- `optimizer.py`: The three module-level optimization functions and the single `ALGORITHM_DISPATCH` mapping.
- `services/cbssports.py`: CBS Sports HTTP fetching and HTML parsing.
- `services/sqlite.py`: Fixed-purpose SQLite setup, odds upsert, and season-filtered reads.
- `services/__init__.py`: Explicit service exports.
- `static/index.html`: Same-origin frontend with season/current-week controls, algorithm selection, projected-end control, manual picks, sorting, and the 18-week grid.
- `test_simp01.py`, `test_simp04.py`: Deterministic standard-library regression tests.

The retained API surface is:

- `GET /api/config`
- `PUT /api/config/week/{week}`
- `PUT /api/config/algorithm`
- `PUT /api/config/split-week`
- `POST /api/config/picks`
- `DELETE /api/config/picks/{week}`
- `DELETE /api/config/picks`
- `POST /api/data/refresh`
- `GET /api/data/events`
- `GET /api/optimize/{split_week}/{algorithm}`

FastAPI serves the frontend and API from the same origin. Interactive OpenAPI documentation is available at `/docs`.

## Runtime behavior

The browser loads configuration, loads stored events for the selected season, and requests one selected algorithm at a time. Users compare the three suggestions manually through the algorithm selector; the frontend does not present a side-by-side comparison. Manual picks can be locked, unlocked, sorted by team or week, and reset.

`split_week` is exposed in the UI as **Projected Pool End Week**. It means the expected last week of the survivor pool and the optimization horizon. The optimizer prioritizes weeks through that horizon rather than reserving teams solely for later weeks, while the frontend continues to render all 18 weeks.

Refreshing reads `current_week` from the configuration, fetches CBS data from that week through week 18, and stores the events in `odds_data.db`. Optimization reads the selected season's stored events and saved picks, then dispatches through `ALGORITHM_DISPATCH`.

## Configuration and local data

`config.example.json` is the canonical example. The configuration keys are:

- `current_week`
- `picks`
- `algorithm`
- `split_week`

`config.json` is the local JSON configuration written by the app. `odds_data.db` is the local SQLite odds database. Both files are ignored and must remain local.

## CBS Sports limitations

Refreshing requires network access and depends on CBS Sports' HTML shape. Missing or malformed games are skipped, and a network failure skips the affected week. The scraper has no retries, caching, proxy support, or rate-limit support.

## Dependencies

The five direct runtime dependencies in `pyproject.toml` each have a concrete use:

- `beautifulsoup4`: parses CBS Sports HTML.
- `fastapi`: provides the web application, routes, validation integration, and static serving.
- `pydantic`: defines and validates API models.
- `requests`: fetches CBS Sports pages.
- `uvicorn`: runs the FastAPI development server through the Mise `dev` task.

`uv.lock` is the lockfile for these dependencies. Do not add a dependency when the standard library or an existing package is sufficient.
