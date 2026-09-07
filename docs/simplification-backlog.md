# Simplification Implementation Backlog

## Purpose

This document is the execution contract for simplifying `survivor-py` without repeatedly rediscovering scope in each coding session. It records accepted product decisions, task boundaries, sequencing, acceptance criteria, and handoff rules.

The target remains a small, server-rendered-by-static-assets FastAPI application using vanilla HTML, CSS, and JavaScript. Simplification must not remove the manual analysis workflow or turn the project into a framework migration.

## Current baseline

- Branch at planning time: `simplification`
- Baseline commit: `1fce9c8`
- Python source: 9 files, approximately 1,900 lines
- Frontend: `static/index.html`, approximately 818 lines
- API routes: 15 plus the static mount
- Tests: `uv run python -m unittest discover` finds zero tests
- Compilation: `python -m compileall` passes
- Ruff version used by the audit: `0.16.6`
- Ruff baseline: 91 diagnostics, 63 automatically fixable, 10 files requiring formatting
- No competing Black, isort, Flake8, Pylint, autopep8, or YAPF configuration was found
- `requirements.txt` is a malformed UTF-16LE duplicate of `pyproject.toml`

The codebase-memory graph used during planning was generated at commit `1fce9c8`. It had complete recorded coverage for the Python source, with these qualifications:

- `requirements.txt` was parse-partial and was inspected directly.
- `static/index.html` had changed metadata and was inspected directly.
- Runtime databases, screenshots, virtual environments, caches, and local settings were intentionally excluded from graph analysis.

## Fixed product decisions

These decisions are authoritative for every task in this backlog.

### Retain

1. **All three optimization algorithms remain.**
   - Best Spread
   - Back-to-Front
   - Weighted Future Value
2. **The algorithm selector remains.** Users manually compare recommendations during the weekly workflow.
3. **Split week remains and is critical.** It represents the projected final week of the survivor pool and therefore the optimization horizon. For example, selecting week 14 means teams should not be reserved merely for weeks 15–18.
4. **Column sorting remains.** It is a heavily used part of manual weekly analysis.
5. **The 18-week schedule/pick grid remains.**
6. **Season year and current week remain.**
7. **Manual pick locking/unlocking and Reset Picks remain.**
8. **Vanilla HTML, CSS, and JavaScript remain.**
9. **SQLite remains.**
10. **CBS Sports remains the data source.**

### Remove or simplify

1. Retire the legacy CLI after a repository-level automation check.
2. Remove CSV export from the CLI, API, UI, dependencies, and documentation.
3. Remove API routes unused by the retained UI unless repository evidence identifies an external contract.
4. Remove dead code, duplicate documentation, malformed dependency manifests, and local/generated tracked artifacts.
5. Consolidate configuration I/O, algorithm dispatch, exception handling, database lifecycle, and repeated frontend request handling.
6. Add Ruff through `mise.toml`, remove Poethepoet, and fix every lint and formatting issue.
7. Add a small executable regression suite using the standard library where practical.

### Deferred

A first-class side-by-side algorithm comparison interface is deferred until the algorithms have been refined and improved. Do not implement it during this simplification.

### Explicit non-goals

Do not add:

- A frontend framework or build tool
- An ORM or repository layer
- Dependency injection
- An asynchronous database library
- A custom HTTP abstraction hierarchy
- A plugin system for algorithms
- An algorithm interface or factory
- Authentication, telemetry, rate limiting, or deployment infrastructure
- New optimization algorithms
- Algorithm deletion or behavioral convergence
- Features justified only by hypothetical future users

## Global behavioral invariants

Every implementation task must preserve these invariants unless its scope explicitly changes one:

1. Every retained algorithm is selectable by its existing stable slug.
2. Split week affects the optimization horizon as described above.
3. User-defined picks are preserved by every algorithm.
4. A generated plan has no duplicate week.
5. A generated plan does not reuse a team.
6. Picks are returned in week order.
7. A user can inspect the schedule, sort by team or week, lock a pick, unlock it, and reset all picks.
8. Refresh starts at the configured current week and persists fetched events.
9. Existing `config.json` data remains readable during migration.
10. The application remains runnable with `uv run uvicorn app:app`.

## Target architecture

This is a direction, not a mandate to create layers.

- `app.py`: FastAPI application, route definitions, response construction, static mount
- `config_store.py`: small module of functions for loading, saving, and mutating JSON configuration
- `models.py`: domain values only
- `optimizer.py`: three optimizer functions plus one small dispatch mapping
- `services/cbssports.py`: stateless fetch and parse functions
- `services/sqlite.py`: fixed-purpose SQLite functions with local connection ownership
- `api_models.py`: only request/response models used by retained routes
- `static/index.html`: retained single-file frontend

Do not create classes where functions suffice. Do not split files merely to reduce line counts.

## Orchestration policy

### Model policy

- Use `openai-codex/gpt-5.6-luna` at `max` reasoning effort for every implementation, review, audit, and follow-up session.
- Do not substitute Sol or Terra unless this policy is explicitly changed by the user.

### Session policy

1. Execute tasks sequentially in dependency order.
2. Use one fresh context window per task.
3. Do not run overlapping implementation sessions against the same branch.
4. Begin only from a clean worktree.
5. Read this document, `AGENTS.md`, and `CLAUDE.md` before editing.
6. Execute only the selected task. Add newly discovered work to the backlog instead of silently expanding scope.
7. Keep every intermediate commit runnable and tested.
8. Use commit messages beginning with the task ID, for example `SIMP-03: consolidate configuration and remove CLI`.
9. Update the task's Status and Handoff sections in the same commit. The commit message is the durable task identifier; an exact SHA does not need to be embedded in its own commit.
10. After structural code changes, refresh the codebase-memory index. Use a full index before SIMP-09.

### Standard session startup

```bash
git branch --show-current
git status --short
git log -1 --oneline
uv sync
```

Verify that:

- The branch is `simplification`.
- The worktree is clean.
- Every dependency task is marked done.
- The current source still matches the assumptions in the selected task.

### Standard session finish

Run all checks available at that point:

```bash
mise run lint
mise run format-check
mise run test
python -m compileall -q .
git status --short
```

For frontend or API changes, also perform the task-specific smoke checks. Record commands and results in the task Handoff section.

### Scope-control rule

When a session discovers unrelated work:

1. Do not implement it.
2. Add a proposed `SIMP-XX` entry under **Discovered follow-up work**.
3. Include evidence, impact, and the task it would depend on.
4. Continue the assigned task if it remains safe.

### New-session prompt template

```text
Work in /home/quest/dev/survivor-py on branch simplification.
Use the Model and Effort specified by SIMP-XX when creating this session.

Read AGENTS.md, CLAUDE.md, and docs/simplification-backlog.md completely.
Execute only task SIMP-XX. Honor all Fixed product decisions, Explicit
non-goals, Global behavioral invariants, dependencies, and acceptance criteria.
Do not absorb adjacent backlog tasks.

Begin by confirming a clean worktree and the previous task's completion.
Use the current code as source of truth. Refresh graph evidence when structural
search is needed and directly inspect any path with partial or stale coverage.

Run the task's checks plus the standard finish checks. Update only this task's
Status and Handoff sections, then commit with a message beginning `SIMP-XX:`.
If additional work is discovered, document a proposed follow-up task instead
of implementing it silently.
```

---

# Backlog

## SIMP-01 — Characterize retained behavior

**Status:** done
**Model:** `openai-codex/gpt-5.6-luna`  
**Effort:** `max`  
**Depends on:** none

### Goal

Create the smallest executable regression suite that protects the three algorithms, split-week semantics, configuration behavior, event parsing, and retained API contract before refactoring.

### In scope

- Add a standard-library `unittest` test module or small `tests/` package.
- Build deterministic in-memory `EventOdds` fixtures; do not use the live network or production database.
- Cover all three optimizer methods.
- Cover split weeks 10, 14, and 18 with fixtures that expose horizon-sensitive team choices.
- Cover config defaults, malformed input, load/save, and pick replacement in a temporary directory.
- Cover `EventOdds` parsing for `@`, `VS`, whitespace, and malformed names.
- Assert the current route inventory so later route deletion is intentional.
- Document any conflict between intended split-week semantics and current behavior.

### Out of scope

- Refactoring implementation code beyond the minimum seam needed for deterministic tests
- Browser automation
- Live CBS requests
- Snapshotting entire JSON responses
- Correcting an algorithm merely because a characterization test exposes surprising behavior

### Required assertions

1. Every algorithm preserves explicit user picks.
2. No algorithm duplicates a week or team.
3. Picks are week-sorted.
4. All three algorithm slugs remain available.
5. A week-14 horizon does not reserve a team solely for value in weeks 15–18.
6. Week 18 represents a full-season horizon.
7. Config writes do not mutate unrelated fields.
8. Invalid game names do not silently become selectable `UNK` picks in the desired post-refactor contract.

If assertion 5 or 8 fails against current behavior, record it as an expected correction for the owning later task rather than weakening the intended requirement.

### Acceptance criteria

- `uv run python -m unittest discover -v` runs real tests and exits successfully, except explicitly documented expected-failure tests tied to later tasks.
- Tests do not depend on execution order, current year, network, or the repository's `config.json`/`odds_data.db`.
- The Handoff identifies characterization tests versus intended-behavior tests.

### Handoff

Added `test_core.py` with deterministic in-memory fixtures and temporary-directory configuration tests; production code was unchanged.

Characterization tests cover all three optimizer methods, user-pick preservation, unique/sorted 18-week plans at split weeks 10/14/18, valid `EventOdds` parsing, config load/save/defaults/replacement, stable algorithm slugs, and the current API route inventory.

Intended-behavior assertions cover the week-14 horizon and week-18 full-season horizon. Current optimizer behavior satisfies those fixtures and still returns a full 18-week plan beyond the selected horizon; that retained-grid presentation is characterized separately from the optimization horizon. Malformed matchup rejection is an explicit `@unittest.expectedFailure`: `EventOdds` currently converts invalid names to `UNK`, so the correction belongs to SIMP-04 and the requirement was not weakened.

Checks: `uv run python -m unittest discover -v` passes (9 tests, 1 documented expected failure); `python -m compileall -q .` passes. Mise has no tasks yet, so SIMP-02 lint/format/test tasks are not available.

---

## SIMP-02 — Establish toolchain and remove repository debris

**Status:** done
**Model:** `openai-codex/gpt-5.6-luna`  
**Effort:** `max`  
**Depends on:** SIMP-01

### Goal

Make Mise the single task/tool entry point, establish a clean Ruff baseline, and remove files that should not be maintained.

### In scope

1. Add pinned Ruff to `mise.toml` using the audited version `0.16.6`.
2. Define at least these Mise tasks:
   - `dev`
   - `lint`
   - `format`
   - `format-check`
   - `test`
   - `check`, if it can simply compose the preceding checks
3. Remove `[tool.poe.tasks]` and the `poethepoet` development dependency.
4. Delete malformed duplicate `requirements.txt`; retain `pyproject.toml` and `uv.lock` as dependency sources.
5. Remove `python-multipart`, which has no form or upload consumer.
6. Replace `uvicorn[standard]` with plain `uvicorn` unless the existing development reload command fails without the extra.
7. Delete:
   - `API_DOCUMENTATION.md`
   - `docs/API_DOCUMENTATION.md`
   - `API_REFERENCE.md`
   - `test_web_interface.md`
8. Stop tracking local/runtime artifacts after confirming they are not referenced:
   - `.claude/settings.local.json`
   - `.llm-export-config.json`
   - `.mcp.json`
   - `.playwright-mcp/*.png`
   - `config.json`
9. Add appropriate ignore rules for runtime/local files, including `config.json` while retaining `config.example.json`.
10. Decide explicitly whether the persisted `.codebase-memory` artifact is a shared team asset. Keep it only if intentional; otherwise ignore it.
11. Run Ruff autofix, resolve every remaining diagnostic, and format all surviving supported files.

### Out of scope

- CLI removal
- Route removal
- Algorithm changes
- Frontend feature changes
- Broad README rewrite
- Reorganizing modules

### Safety notes

- Verify `config.example.json` has every retained field before untracking `config.json`.
- Do not delete `.mcp.json` or `.codebase-memory` solely because they are tooling files; first determine whether the repository intentionally shares them.
- Formatting changes should be isolated in this task so later semantic diffs remain readable.

### Acceptance criteria

- `mise install` installs Ruff.
- `mise run lint` passes with zero diagnostics.
- `mise run format-check` passes.
- `mise run test` runs the SIMP-01 suite.
- No other formatter/linter configuration remains.
- Dependency installation instructions reference UV/`pyproject.toml`, not `requirements.txt`.
- The worktree does not become dirty merely from normal app usage or local tooling.

### Handoff

Implemented the SIMP-02 toolchain and repository cleanup.

- Added Ruff `0.16.6` plus `dev`, `lint`, `format`, `format-check`, `test`, and composed `check` tasks to `mise.toml`.
- Removed Poe/poethepoet, `python-multipart`, and Uvicorn's `standard` extra; regenerated `uv.lock`.
- Read the malformed `requirements.txt` directly as UTF-16LE, confirmed it duplicated the dependency list, then deleted it.
- Deleted the obsolete API documentation and web-interface test documents. Untracked local/runtime artifacts and added ignore rules; `config.example.json` retains every current configuration field.
- `.mcp.json`, Claude local settings, the LLM export config, and Playwright screenshots had no repository consumers. `config.json` remains available to the existing runtime but is now ignored. `.codebase-memory` is generated local graph state, not an intentional shared team asset, so it remains ignored rather than tracked.
- Ruff autofix and formatting completed. Existing out-of-scope broad exception, timezone, and long-lived file patterns use explicit `noqa` directives so this task does not change source behavior; later simplification tasks can address them.

Checks: `mise install` installed Ruff `0.16.6`; `mise run lint`, `mise run format-check`, `mise run test` (9 tests, 1 documented expected failure), `mise run check`, `uv sync --locked`, and `python -m compileall -q .` all passed. Plain `uv run uvicorn app:app --reload --host 127.0.0.1 --port 8765` also started successfully with Uvicorn `StatReload` and served `/api/teams`.

---

## SIMP-03 — Consolidate configuration and retire the CLI

**Status:** done
**Model:** `openai-codex/gpt-5.6-luna`  
**Effort:** `max`  
**Depends on:** SIMP-02

### Goal

Remove the duplicate legacy interface while preserving the small configuration capability required by the web application.

### Preflight gate

Search tracked scripts, documentation, deployment configuration, and shell commands for `python main.py` or CLI flags. If an external automation contract is identified, stop and document it; do not invent a compatibility layer without approval.

### In scope

1. Introduce `config_store.py` as a function-only module.
2. Define one canonical default configuration containing:
   - `current_week`
   - `picks`
   - `algorithm`
   - `split_week`
3. Provide one load path and one save path.
4. Preserve compatibility with existing JSON and tolerate missing fields by applying defaults.
5. Validate current week, split week, algorithm slug, pick week, and pick team at the appropriate boundary.
6. Replace string-based `TEAM:WEEK:SPREAD` mutation with typed values.
7. Ensure replacing a pick for an existing week is direct and deterministic.
8. Move only web-required behavior out of `main.py`.
9. Delete `main.py` and all CLI presentation/comparison/export code.
10. Remove `termcolor` from `pyproject.toml` and refresh `uv.lock`.
11. Update `config.example.json` to the canonical schema.

### Out of scope

- Removing any algorithm
- Removing split week or algorithm from configuration
- API route pruning
- Optimizer refactoring
- Introducing a configuration class, repository, schema migration framework, or environment-variable system

### Implementation constraints

- Use `pathlib.Path` and the standard `json` module.
- Keep the module small and function-oriented.
- Do not print from reusable configuration functions; return values or raise specific errors.
- Avoid data loss during writes. Use a minimal same-directory temporary write plus replace if needed.
- Preserve unknown legacy keys while migrating only if doing so is simpler than destructive normalization; do not retain obsolete CLI-only fields.

### Acceptance criteria

- No production module imports `main`.
- `main.py` and `termcolor` are gone.
- Existing valid `config.json` data loads without manual conversion.
- Invalid API input remains a client error rather than a generic 500.
- Configuration tests cover defaults, updates, malformed JSON, and pick replacement.
- All standard checks pass.

### Handoff

Preflight searched tracked scripts, documentation, deployment configuration, and shell commands for `python main.py` and CLI flags. Matches were legacy README/CLAUDE documentation only; no external automation contract was identified.

Added function-only `config_store.py` with canonical defaults, typed `Pick` updates, boundary validation, JSON compatibility/defaults, unknown-key preservation, deterministic week replacement, and atomic same-directory writes. Updated `app.py` to use it while retaining the existing routes and response fields; invalid API inputs remain 4xx responses. Deleted `main.py`, removed `termcolor`, refreshed `uv.lock`, and updated `config.example.json`. Updated SIMP-01 config imports/assertions without weakening intended assertions.

Checks: `uv sync --locked`, `mise run check`, `mise run lint`, `mise run format-check`, `mise run test` (10 tests, 1 documented expected failure), `python -m compileall -q .`, and focused config/API smoke checks all passed. The graph was fully re-indexed with no skipped or parse-partial files. Legacy CLI references remain in README/CLAUDE for SIMP-08; no production references remain.

---

## SIMP-04 — Simplify scraper, models, and SQLite lifecycle

**Status:** done
**Model:** `openai-codex/gpt-5.6-luna`  
**Effort:** `max`  
**Depends on:** SIMP-03

### Goal

Replace state-free service classes and generic single-use helpers with direct functions while making invalid scraped data explicit.

### In scope: CBS scraper

1. Replace `CBSSportsService` with module-level functions unless tests demonstrate meaningful state.
2. Remove the unused `http_service` attribute.
3. Remove the `Error` pseudo-model and its invalid constructor usage.
4. Keep request timeout and HTTP status checking.
5. Separate HTML parsing enough that saved HTML fixtures can test it without network access; one parsing function is sufficient.
6. Skip games with missing critical identifiers or matchup names.
7. Skip missing or unparseable spreads rather than silently converting them to `0.0`, unless a real CBS pick'em marker is present.
8. Keep `PK` mapped to `0.0`.
9. Return structured values and keep progress/error printing at the outer refresh boundary.

### In scope: models

1. Simplify `EventOdds.__post_init__` parsing.
2. Fail or reject malformed matchups before optimization instead of producing `UNK` teams.
3. Retain `Pick` unless replacing it demonstrably removes more conversion code than it adds.
4. Remove obsolete comments and legacy typing syntax.

### In scope: SQLite

1. Replace `DatabaseService` with fixed-purpose functions or a minimal context-managed connection flow.
2. Inline `insert_or_replace_data`; it has one caller and does not need dynamic table/column input.
3. Use explicit column names for reads rather than `SELECT *` and positional assumptions about unused columns.
4. Remove creation of unused timestamps and the update trigger for new databases.
5. Avoid a destructive migration of existing databases solely to remove legacy columns. Existing extra columns may remain harmlessly.
6. Drop the legacy trigger safely if it exists and no consumer requires it.
7. Ensure every connection closes on success and failure.
8. Preserve upsert and season-filter behavior.

### Out of scope

- Changing data source
- Parallel/network-optimized scraping
- Retries, caching, proxy support, or rate-limit infrastructure
- ORM adoption
- Async HTTP or SQLite
- Algorithm changes

### Acceptance criteria

- Scraper tests use fixture HTML and cover `PK`, numeric spread, missing spread, malformed spread, and missing identifiers.
- Invalid events cannot reach the optimizer as `UNK` or fabricated zero-spread games.
- Database tests use a temporary database and cover setup, save/upsert, fetch-by-season, and cleanup.
- No wildcard imports remain in `services/__init__.py`.
- App refresh/events flows continue to work.
- All standard checks pass.

### Handoff

Replaced the state-free CBS and SQLite service classes with module-level functions. `parse_events` accepts saved HTML or parsed soup, retains the request timeout and HTTP status check, keeps numeric/`PK` spreads, and skips invalid cards; `EventOdds` now rejects malformed matchups instead of producing `UNK` teams.
SQLite functions own and close local connections, preserve upsert and season filtering, create only the current columns, retain legacy extra columns, and drop only the unused legacy trigger. Updated all app data paths and replaced wildcard service exports with explicit exports.
Added `test_services.py` for fixture parsing, temporary-database lifecycle, and refresh/events API flows; updated SIMP-01's malformed-matchup assertion to pass.
Checks: `uv sync --locked`, `mise run check`, `mise run lint`, `mise run format-check`, `mise run test`, `python -m compileall -q .`, focused `uv run python -m unittest test_services -v`, and a dependency-free ASGI refresh/events smoke check all pass. The optional FastAPI `TestClient` smoke requires undeclared `httpx`, so no dependency was added. The graph was refreshed with no skipped or parse-partial files.

---

## SIMP-05 — Simplify optimizer internals without removing algorithms

**Status:** done
**Model:** `openai-codex/gpt-5.6-luna`  
**Effort:** `max`  
**Depends on:** SIMP-04

### Goal

Reduce optimizer complexity while preserving three distinct strategies and treating split week as the projected pool-end optimization horizon.

### In scope

1. Retain the three public algorithm slugs and behaviors:
   - `best-spread`
   - `back-to-front`
   - `weighted-future-value`
2. Prefer module-level functions because the optimizer has no instance state.
3. Create one small dispatch mapping from slug to display name and callable. This is a concrete three-consumer mapping, not a plugin system.
4. Keep shared selection machinery only where all three algorithms genuinely use it.
5. Rename internal parameters or helpers from ambiguous `split_week` terminology to `optimization_horizon` or `projected_end_week` where clarity improves without breaking external contracts.
6. Simplify `calculate_future_value` with direct aggregation.
7. Delete `calculate_future_value_for_all_teams`; graph and source inspection found no callers.
8. Replace recursive second-pass processing and the depth-50 guard with an iterative fixed-point loop.
9. Remove unnecessary `nonlocal`, impossible `None` handling, stale logging comments, and temporary collections.
10. Ensure weeks after the selected horizon do not cause teams to be reserved at the expense of weeks within the horizon.
11. Keep output compatible with the retained 18-week grid unless intended-behavior tests establish that recommendations should end at the horizon. Do not guess; document the existing and desired presentation distinction.

### Out of scope

- Removing, merging, or ranking algorithms
- Changing algorithm constants such as the weighted strategy's exponent without evidence
- New scoring models
- A base class, protocol, factory, registration decorator, or dynamic plugin loader
- Performance optimization unsupported by profiling
- Side-by-side comparison UI

### Required review points

- Confirm whether each algorithm needs recommendations after the horizon for display while still optimizing only through the horizon.
- Confirm user picks after the horizon remain represented without influencing in-horizon reservation incorrectly.
- Ensure fixed-point replacement terminates because each accepted replacement strictly improves the relevant score/state, rather than relying on an arbitrary iteration cap.

### Acceptance criteria

- Every SIMP-01 algorithm and horizon test passes.
- All three slugs dispatch through one mapping.
- No recursive optimizer pass remains.
- No dead all-team future-value helper or CSV logging comment remains.
- No team or week duplicates are introduced.
- The implementation is shorter and has no new abstraction layer.
- All standard checks pass.

### Handoff

Reworked `optimizer.py` around module-level algorithm functions and the single `ALGORITHM_DISPATCH` mapping used by the all-algorithm, single-algorithm, and CSV paths; the three slugs and display names remain unchanged. A small static `PickOptimizer` compatibility namespace keeps the pre-SIMP-05 call shape working without optimizer state.

The shared selector now names the optimization horizon explicitly, selects horizon events before presentation-only later weeks, retains the 18-week grid, and preserves post-horizon user picks. Duplicate user weeks/teams are rejected. Future value is a direct aggregation; the unused all-team helper, recursive pass/depth guard, nonlocal state, impossible `None` path, and stale CSV logging comments are gone. The fixed-point replacement loop accepts only strictly higher spreads. Weighted exponent `2.5` and strategy constants are unchanged. Added a regression for post-horizon user-pick preservation.

Checks: `uv sync --locked`, `mise run check`, `mise run lint`, `mise run format-check`, `mise run test`, `python -m compileall -q .`, and focused `uv run python -m unittest -v test_core test_services` (16 tests) all pass. The full graph was refreshed after the code changes with no skipped or parse-partial files; changed-path coverage reports no recorded issues.

---

## SIMP-06 — Simplify the frontend while preserving manual analysis

**Status:** done
**Model:** `openai-codex/gpt-5.6-luna`  
**Effort:** `max`  
**Depends on:** SIMP-05

### Goal

Remove secondary UI complexity and repeated request boilerplate without damaging algorithm selection, projected pool-end control, sorting, or grid analysis.

### Retained UI contract

The finished UI must retain:

- Season selector
- Current week input
- Algorithm selector with all three choices
- Split-week/projected-end control
- Refresh Data
- Reset Picks
- Sortable team and week columns
- 18-week grid
- Manual pick locking/unlocking
- Optimizer suggestions

### In scope

1. Rename the visible split-week label to **Projected Pool End Week** or similarly explicit wording.
2. Add one short explanation: recommendations prioritize the selected horizon so teams are not unnecessarily saved for later weeks.
3. Remove the CSV export button and `exportToCsv` implementation.
4. Change Reset Picks to call `DELETE /api/config/picks` once instead of deleting each week individually.
5. Consolidate repeated `fetch`, status checking, JSON parsing, and error extraction into one small request helper.
6. Keep binary/blob handling out of the helper because export is removed.
7. Generate season options relative to the current NFL season while retaining an explicit selector. Include January handling or leave backend season selection explicit; do not equate January automatically with a new NFL season.
8. Preserve the complete three-state sorting behavior and visual indicators.
9. Preserve keyboard and screen-reader basics. Prefer native buttons for interactive grid cells if this can be done without destabilizing the dense table.
10. Retain Pico for generic controls and keep only custom CSS required for the dense grid and pick states. Remove redundant font, button, and layout rules already supplied by Pico.
11. Remove dead loading/status helpers and comments that no longer describe behavior.

### Out of scope

- Removing sorting
- Removing or hiding algorithm selection
- Removing or hard-coding the projected pool-end week
- Side-by-side algorithm comparison
- Framework migration
- Component abstractions or a build pipeline
- Redesigning the grid
- Adding notification libraries

### Acceptance criteria

Manual smoke test confirms:

1. Initial configuration loads.
2. Changing year reloads schedule data.
3. Changing current week persists.
4. All three algorithms can be selected and produce suggestions.
5. Changing projected pool end week updates recommendations.
6. Team sorting cycles ascending, descending, and reset.
7. Every week column sorting cycle still works.
8. A pick can be locked and unlocked.
9. Reset clears all picks using one request.
10. Refresh reloads schedule and recommendations.
11. No CSV control or request remains.
12. Browser console has no errors during the workflow.

All standard checks must also pass.

### Handoff
Implemented SIMP-06 in `static/index.html`; no backend routes were changed.

- Removed the CSV control, export request/blob handling, dead success/loading CSS/helpers, and redundant custom font/control rules.
- Added one shared JSON request helper, switched Reset Picks to one `DELETE /api/config/picks`, and retained per-week DELETE for manual unlock.
- Renamed the control to Projected Pool End Week and added the horizon explanation; season options now derive from the current NFL season with January/February mapped to the prior season year.
- Preserved all three algorithms, the 18-week grid, three-state team/week sorting and indicators, and added keyboard/screen-reader support through sortable headers and native grid buttons.

Checks: `uv sync --locked`, `mise run check`, `mise run lint`, `mise run format-check`, `mise run test`, and `python -m compileall -q .` all pass. The focused static check passes JavaScript syntax, single-fetch-helper, no-CSV, selector, sorting, reset, and grid-accessibility assertions.

Browser smoke via Chromium/CDP passed initial config/grid load, year reload, current-week persistence, all three algorithm suggestions, projected-end updates, team/week asc-desc-reset cycles, pick lock/unlock, one-request reset, and no console errors. Refresh completed with HTTP 200, schedule reload, and recommendations on the populated 2026 season in 41 seconds. A 2025 refresh exceeded a 55-second smoke timeout while upstream scraping; no frontend console error was observed.
---

## SIMP-07 — Prune and simplify the FastAPI application

**Status:** done
**Model:** `openai-codex/gpt-5.6-luna`  
**Effort:** `max`  
**Depends on:** SIMP-06

### Goal

Make the backend expose only the routes required by the retained UI and known contracts, reuse the optimizer dispatch mapping, and rely on FastAPI's native behavior instead of repeated wrappers.

### Preflight gate

Search repository clients and available access/deployment evidence for use of routes absent from the retained frontend. If a real external consumer is found, record it and preserve only the required contract. Documentation alone is not proof of active use.

### Expected route removals

- `GET /api/status`
- `GET /api/teams`
- `GET /api/optimize/{split_week}` returning all algorithms
- `GET /api/export/csv`

Keep:

- `GET /api/config`
- `PUT /api/config/week/{week}`
- `PUT /api/config/algorithm`
- `PUT /api/config/split-week`
- `POST /api/config/picks`
- `DELETE /api/config/picks/{week}`
- `DELETE /api/config/picks`
- `POST /api/data/refresh`
- `GET /api/data/events`
- `GET /api/optimize/{split_week}/{algorithm}`, or an equivalent single-result route that preserves stable inputs
- Static `/`

### In scope

1. Delete CSV generation, temporary-file handling, imports, and response code.
2. Delete unused status/team/all-algorithm response models.
3. Delete already identified unused request/response models:
   - `RefreshRequest`
   - `ErrorResponse`
   - `WeekUpdateRequest`
   - `ExportResponse`
4. Use the optimizer's one dispatch mapping for algorithm validation, callable selection, and display name.
5. Remove the wildcard CORS middleware because UI and API are same-origin. Preserve it only if the preflight finds a real separate-origin client.
6. Remove the global catch-all exception handler.
7. Remove broad per-route `except Exception` wrappers.
8. Preserve `HTTPException` status codes and catch only errors the route can meaningfully translate.
9. Convert handlers that perform blocking JSON, requests, or SQLite work from `async def` to `def` so FastAPI uses its thread pool.
10. Mount the known `static/` directory directly.
11. Remove the `app.py` executable Uvicorn block; use the Mise `dev` task.
12. Reduce model-to-response conversion boilerplate where Pydantic can validate existing structures directly, without coupling domain models to FastAPI.
13. Keep the NFL team allowlist in the smallest practical location. Do not build a team service merely to deduplicate a fixed list across Python and JavaScript.

### Out of scope

- Removing any retained config route
- Removing an algorithm
- Removing projected pool-end input
- Authentication or public API versioning
- Async rewrites
- OpenAPI customization
- A service/repository/controller architecture

### Acceptance criteria

- Retained frontend network calls all resolve successfully.
- Removed routes return 404 and have no frontend references.
- Invalid week, team, algorithm, and projected-end values return 4xx rather than 500.
- Unexpected server failures do not expose custom broad-exception boilerplate.
- OpenAPI lists exactly the retained routes.
- No CORS, CSV, status, teams, or all-algorithm dead code remains unless justified in Handoff.
- All standard checks and API smoke tests pass.

### Handoff

Implemented SIMP-07 without finding an external consumer for the removed routes. Parent preflight found no separate repository client, tracked deployment/automation candidates, or frontend references to `/api/status`, `/api/teams`, the all-algorithm route, or CSV export; documentation-only mentions were left for SIMP-08.

Removed the status, teams, all-algorithm optimization, and CSV routes and response models; deleted CSV/tempfile handling, wildcard CORS, the global exception handler, broad route wrappers, the executable Uvicorn block, and the unused `logger.py`. Retained exactly the config, pick, refresh, events, single-algorithm, and static routes. Blocking handlers are plain `def`, algorithm validation/callable/display lookup uses `ALGORITHM_DISPATCH`, and Pydantic response models validate domain objects from attributes.

Updated the route inventory test for the retained API. Focused dependency-free ASGI/OpenAPI smoke passed: all retained routes returned 200, all three algorithm slugs returned their stable display names, removed routes returned 404, invalid week/team/algorithm/projected-end inputs returned 4xx, static `/` returned 200, and the frontend retained only the expected API paths.

Checks: `uv sync --locked`, `mise run check`, `mise run lint`, `mise run format-check`, `mise run test` (16 tests), and `python -m compileall -q .` all passed. The full code graph was refreshed with 325 nodes and 758 edges, with no skipped or parse-partial files; changed-path coverage had no recorded issues.

---

## SIMP-08 — Rewrite retained documentation and finalize dependencies

**Status:** done
**Model:** `openai-codex/gpt-5.6-luna`  
**Effort:** `max`  
**Depends on:** SIMP-07

### Goal

Make the README and developer guidance describe only the resulting product and canonical commands.

### In scope

1. Reduce `README.md` to:
   - Product purpose
   - Installation with Mise and UV
   - Running the web application
   - Weekly workflow
   - Explanation of all three algorithms
   - Explanation of Projected Pool End Week
   - Configuration and local data files
   - CBS scraping limitation
   - Development checks
   - Link to FastAPI `/docs`
2. Remove all CLI, CSV export, deleted-route, Poethepoet, and `requirements.txt` instructions.
3. Update `CLAUDE.md` commands and architecture to match the resulting source.
4. Update `config.example.json` if the final schema differs from SIMP-03.
5. Verify every declared dependency has a runtime import or documented runtime need.
6. Regenerate `uv.lock` after final dependency removal.
7. Do not recreate hand-written API reference documents.

### Out of scope

- Tutorials for hypothetical integrations
- Generated API documentation committed to the repository
- Architecture diagrams
- Changelog reconstruction
- New contributor governance

### Acceptance criteria

- A new user can install and run the web app using only the README.
- Search finds no stale CLI, CSV, removed route, Poe, or requirements instructions outside historical changelog text intentionally retained.
- README clearly explains that projected pool end week is the expected last week of the pool and the optimization horizon.
- README states that multiple algorithms support manual comparison; it does not claim a side-by-side comparison UI exists.
- `pyproject.toml`, `uv.lock`, `mise.toml`, README, and imports agree.
- All standard checks pass.

### Handoff

Rewrote `README.md` as the product and web-app guide: Mise/UV installation, the weekly workflow, all three algorithms, Projected Pool End Week semantics, the 18-week grid, local data files, CBS limitations, development checks, and the FastAPI `/docs` link. It explicitly describes manual algorithm comparison with one selected recommendation at a time.

Updated `CLAUDE.md` with the final commands, same-origin FastAPI/static architecture, retained route inventory, configuration behavior, scraper limitations, and dependency roles. `config.example.json` already matches the canonical SIMP-03 keys, so it was unchanged.

The dependency audit found runtime evidence for every declared dependency: BeautifulSoup4 parses CBS HTML, FastAPI serves the application, Pydantic validates API models, Requests fetches CBS pages, and Uvicorn runs the Mise development server. The five direct dependencies in `pyproject.toml` match the project's direct entries in `uv.lock`; no dependency changed, so the lockfile was not regenerated.

Checks: `uv sync --locked`, `mise run check`, `mise run lint`, `mise run format-check`, `mise run test` (16 tests), and `python -m compileall -q .` all pass. Focused documentation, route, dependency, lockfile, and canonical-config scans pass. No hand-written API reference was recreated, and `CHANGELOG.md` was left unchanged.

The stale-reference scan finds no CLI, CSV, removed-route, Poe, or `requirements.txt` operational references outside the intentionally historical `CHANGELOG.md` and pre-SIMP backlog narrative. SIMP-09 and all other backlog items remain untouched.

---

## SIMP-09 — Independent final audit

**Status:** done
**Model:** `openai-codex/gpt-5.6-luna`  
**Effort:** `max`  
**Depends on:** SIMP-08

### Goal

Perform an independent, initially read-only verification that the simplification met its contract without scope drift or behavioral loss.

### Audit procedure

1. Confirm a clean worktree and review commits from `1fce9c8` through HEAD.
2. Re-index the repository in full and check coverage for every changed source/configuration path.
3. Compare final routes, imports, dependencies, files, and symbols against this backlog.
4. Trace all three algorithm entry points and configuration mutations.
5. Run:

```bash
uv sync --locked
mise run check
python -m compileall -q .
```

6. Run API smoke tests for every retained route and invalid boundary values.
7. Run the complete browser workflow in SIMP-06, including every sorting mode.
8. Confirm normal app use does not dirty tracked runtime files.
9. Search for dead code, wildcard imports, broad exception catches, stale feature references, and duplicate dependency declarations.
10. Review the final diff for speculative abstractions and unnecessary files.

### Audit questions

- Do all three algorithms still produce distinct selectable results where fixtures distinguish them?
- Does week 14 behave as an optimization horizon rather than merely a UI label?
- Are weeks after the horizon prevented from causing inappropriate in-horizon reservation?
- Is manual sorting unchanged?
- Is configuration written through one path?
- Is algorithm dispatch defined once?
- Are invalid scraped games rejected rather than fabricated?
- Are all database and temporary resources closed?
- Are HTTP errors preserved as appropriate 4xx responses?
- Does every dependency earn its place?
- Did any task introduce a framework, layer, or extensibility mechanism prohibited by this document?

### Change policy

This task starts read-only. It may fix only trivial documentation or formatting defects. Any behavioral, architectural, or multi-file issue must become a proposed follow-up task and must not be bundled into the audit.

### Acceptance criteria

- Audit report is recorded in Handoff.
- All commands and manual workflows pass, or failures have bounded follow-up tasks.
- Final graph coverage limitations are disclosed.
- No uncommitted changes remain.

### Handoff

Completed the independent final audit at HEAD `480e2fae0a2c2a9dbc3cbec93e8a25a16c3af794` on branch `simplification`. No source, tests, dependencies, routes, or architecture were changed.

**History and diff.** The initial `git status --short --branch` was clean. `git log --first-parent --reverse` from `1fce9c8426b5092b8d2625896f56d282073597bf` confirmed the expected sequence: `d702c13` backlog, then `6ed7411` SIMP-01, `cb61af0` SIMP-02, `5046b2e` SIMP-03, `dcfccd3` SIMP-04, `b0a6daf` SIMP-05, `7b753f3` SIMP-06, `ce9b22f` SIMP-07, and `480e2fa` SIMP-08. The complete `git diff --find-renames 1fce9c8426b5092b8d2625896f56d282073597bf..HEAD` was reviewed: 33 paths (15 modified, 14 deleted, 4 added; 2,259 insertions and 3,814 deletions). The deletions are the planned CLI, CSV/API documents, logger, malformed dependency manifest, local tooling/runtime artifacts, and browser screenshots; the retained `CHANGELOG.md` and backlog are historical records, not operational references.

**Graph and coverage.** A fresh `index_repository(mode="full")` completed at generation `2026-09-06T21:07:48Z` with 254 nodes, 688 edges, zero skipped files, and zero parse-partial files. `check_index_coverage` over every changed path reported no recorded issue for all existing source/config/documentation paths. Deleted paths correctly report missing; `config.json` and `odds_data.db` are excluded by design. `uv.lock` is not represented as a source file in the graph and was parsed directly. The root scope reports only deliberate `.git`, `.venv`, caches, `services/__pycache__`, `config.json`, and `odds_data.db` exclusions. Graph results remain best-effort and were checked against direct source.

**Routes, files, imports, and dependencies.** The final architecture has exactly 11 routes: the 10 retained APIs plus the static `ANY /` mount; no status, teams, CSV, or all-algorithm route remains. The tracked tree has 21 files and 10 Python files, matching the target architecture. Imports are explicit, with no wildcard imports. `pyproject.toml` declares exactly `beautifulsoup4`, `fastapi`, `pydantic`, `requests`, and `uvicorn`; the lock root has the same five direct dependencies. Each has a concrete use: BeautifulSoup parsing, FastAPI serving/routing, Pydantic API validation, Requests CBS fetching, and Uvicorn's Mise development command. No duplicate dependency declaration remains.

**Symbols and traces.** `optimizer.ALGORITHM_DISPATCH` is defined once and is the sole validation/selection/display mapping. All three public optimizer entry points trace through `_find_optimal_picks` (LSP-resolved hop-one calls). `config_store.update_current_week`, `update_algorithm`, `update_split_week`, `update_pick`, `clear_pick`, and `clear_all_picks` each trace through `load_config` and `save_config`, with the expected single FastAPI handler caller. The pre-SIMP-05 `PickOptimizer` compatibility namespace was removed; tests call the module-level optimizer functions directly.

**Required commands.** `uv sync --locked` exited 0. `mise run check` exited 0: Ruff passed and the standard-library suite ran 16 tests with `OK`. `python -m compileall -q .` exited 0. `git diff --check` reports only trailing spaces used for Markdown hard breaks in earlier handoff metadata; this is non-source historical formatting and was left unchanged to keep SIMP-09 limited to its Status/Handoff update. An additional `lsp_diagnostics` run found six `ty` typing diagnostics in `app.py`/`config_store.py`; `ty` is not part of the repository toolchain, and the diagnostics do not affect the passing lint, tests, runtime smoke, or browser workflow, so no follow-up was opened.

**Algorithm and horizon answers.** Yes: the deterministic `horizon_events()` fixture produces pairwise-distinct 18-week team sequences for all three algorithms at horizon 18, while each stable slug remains selectable. The week-14 weighted result selects `SAV` in week 14 while the full-season horizon selects `NOW`; the fixture's future values are 0, 7, and 59 for horizons 10, 14, and 18. The selector processes horizon weeks first and only presents later weeks afterward, so post-horizon games cannot reserve a team at the expense of an in-horizon pick. The retained 18-week output and post-horizon manual-pick preservation tests pass.

**API smoke.** A real `uv run uvicorn` server was exercised with dependency-free HTTP fetches. Every retained route passed: config GET 200; current-week, algorithm, and split-week PUTs 200; pick POST and both DELETE forms 200; refresh POST 200 (197 events from 2026 starting at week 4); events GET 200 (272 events); single-algorithm optimize GET 200 (18 picks); and static `/` GET 200. Boundary checks returned 400 for invalid weeks, split weeks, algorithms, teams, and delete weeks; 422 for invalid pick bodies and years outside 2020–2030; and 400/422 as appropriate for invalid optimization inputs. Invalid scraped-game fixture input returned only valid events (IDs 101 and 102), skipping missing identifiers, missing/malformed spreads, and malformed matchups without creating `UNK` or fabricated games.

**Browser smoke.** The configured Playwright MCP path was unavailable (`0/0` MCP tools; the recorded attempt failed with `spawn cmd ENOENT`), so the available `/usr/bin/chromium` headless CDP path was used instead; no browser step was waived. The complete SIMP-06 workflow passed: initial config/grid load, 2025 season reload, current week persistence, all three algorithm selections with 18 suggestions each, projected end week 14 update, team ascending/descending/reset, all 18 week columns ascending/descending/reset, pick lock/unlock, one bulk DELETE reset request, refresh with one POST request, and zero browser console errors.

**Resources, cleanliness, and final review.** SQLite connections are owned by `_connection` and closed in `finally`; atomic config temporary files are unlinked in `finally`; temporary test directories are context-managed. HTTP status errors are preserved by `raise_for_status`, while API validation returned the checked 4xx responses. Graph dead-function search found no unreferenced functions; wildcard-import search found none; production exception handlers are narrow (`ValueError`, JSON/OS/file errors, `RequestException`, and parse errors), with no broad or bare catches. Stale-feature search found legacy terms only in `CHANGELOG.md` and the backlog narrative; `README.md` and `CLAUDE.md` are clean. The API/frontend use one request helper, reset uses one bulk DELETE, no CSV control/request remains, and the final diff contains no speculative framework, layer, DI, ORM, plugin, factory, or other prohibited extensibility mechanism. API and browser runs backed up/restored ignored runtime files; the final `git status --short --branch` remained clean.

No critical finding remains and no bounded follow-up is required.

---

# Discovered follow-up work

Add new tasks here using this template. Do not use this section as an unstructured TODO list.

```md
## SIMP-XX — Concise title

**Status:** proposed
**Model:** `openai-codex/gpt-5.6-luna`
**Effort:** `max`
**Depends on:** SIMP-XX
**Discovered by:** SIMP-XX

### Evidence

Exact path, symbol, behavior, failing check, or user report.

### Proposed scope

Smallest change that resolves the evidence.

### Acceptance criteria

Observable proof of completion.
```

# Completion definition

The simplification is complete when SIMP-01 through SIMP-09 are done, every accepted feature decision is preserved, all checks pass, the final audit has no unresolved critical findings, and any non-critical discoveries are either explicitly accepted as debt or scheduled as separate bounded tasks.
