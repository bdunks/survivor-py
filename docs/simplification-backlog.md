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

Added `test_simp01.py` with deterministic in-memory fixtures and temporary-directory configuration tests; production code was unchanged.

Characterization tests cover all three optimizer methods, user-pick preservation, unique/sorted 18-week plans at split weeks 10/14/18, valid `EventOdds` parsing, config load/save/defaults/replacement, stable algorithm slugs, and the current API route inventory.

Intended-behavior assertions cover the week-14 horizon and week-18 full-season horizon. Current optimizer behavior satisfies those fixtures and still returns a full 18-week plan beyond the selected horizon; that retained-grid presentation is characterized separately from the optimization horizon. Malformed matchup rejection is an explicit `@unittest.expectedFailure`: `EventOdds` currently converts invalid names to `UNK`, so the correction belongs to SIMP-04 and the requirement was not weakened.

Checks: `uv run python -m unittest discover -v` passes (9 tests, 1 documented expected failure); `python -m compileall -q .` passes. Mise has no tasks yet, so SIMP-02 lint/format/test tasks are not available.

---

## SIMP-02 — Establish toolchain and remove repository debris

**Status:** blocked  
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

_Blocked by SIMP-01._

---

## SIMP-03 — Consolidate configuration and retire the CLI

**Status:** blocked  
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

_Blocked by SIMP-02._

---

## SIMP-04 — Simplify scraper, models, and SQLite lifecycle

**Status:** blocked  
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

_Blocked by SIMP-03._

---

## SIMP-05 — Simplify optimizer internals without removing algorithms

**Status:** blocked  
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

_Blocked by SIMP-04._

---

## SIMP-06 — Simplify the frontend while preserving manual analysis

**Status:** blocked  
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

_Blocked by SIMP-05._

---

## SIMP-07 — Prune and simplify the FastAPI application

**Status:** blocked  
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

_Blocked by SIMP-06._

---

## SIMP-08 — Rewrite retained documentation and finalize dependencies

**Status:** blocked  
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

_Blocked by SIMP-07._

---

## SIMP-09 — Independent final audit

**Status:** blocked  
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

_Blocked by SIMP-08._

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
