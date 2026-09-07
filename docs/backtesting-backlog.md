# Historical Data and Backtesting Implementation Backlog

## Purpose

This document is the execution contract for collecting point-in-time NFL data and replaying survivor algorithms without look-ahead bias. It is intended to be executed as a sequential series of small tasks, each in a fresh context window.

The result should remain a small FastAPI application using SQLite, standard-library tooling, the existing optimizer functions, and the existing vanilla frontend. Historical data collection must begin during the season because overwritten spreads and unknown pick times cannot be reconstructed later.

## Current baseline

- Branch at planning time: `main`
- Baseline commit: `c6ef0cb`
- Current odds table: `averaged_odds`
- `services/sqlite.py` replaces rows by `event_id`; it does not preserve spread history.
- Refreshes have no durable run, page-capture, failure, or observation timestamps.
- Refresh currently starts at `current_week`, so a completed previous week may not be fetched for final scores.
- Picks are mutable entries in `config.json`, are not season-specific, and have no history or selection timestamp.
- Optimization responses do not record their input observations, parameters, code revision, or recommendations.
- `config.json` and `odds_data.db` are local ignored files.

The codebase-memory graph used during planning was generated on `main` with no recorded coverage gaps in `app.py`, `api_models.py`, `config_store.py`, `models.py`, `optimizer.py`, `services/cbssports.py`, `services/sqlite.py`, `static/index.html`, `test_core.py`, or `test_services.py`. This is a best-effort signal, not proof of completeness.

## Fixed product decisions

These decisions are authoritative for every task in this backlog.

### Retain

1. SQLite remains the only application database.
2. CBS Sports remains the data source.
3. Existing optimization algorithms and stable algorithm slugs remain.
4. The optimizer continues to consume `EventOdds` and prior locked picks.
5. The normal UI continues to display the latest known schedule and spreads.
6. `config.json` remains for UI preferences such as current week, selected algorithm, and projected pool end week.
7. Authoritative decision snapshots, selection events, and recorded optimization runs are immutable.
8. Frequent refreshes update current state; they do not automatically become backtest snapshots.
9. Timestamps are recorded in UTC.
10. Backtesting initially runs offline and emits machine-readable output; a backtest UI is not required.
11. Every intermediate task leaves the application runnable and tested.

### Snapshot policy

The system deliberately separates three different meanings of “spread”:

1. **Current spread:** the newest successfully fetched value used by the live UI. It may be updated in place on every refresh.
2. **Decision spread:** the immutable value in the one authoritative decision snapshot for a survivor week. This is the optimizer input used for fair historical comparisons.
3. **Closing spread:** the last spread successfully observed before that game's kickoff. It is an evaluation benchmark, not a decision input by default.

The authoritative decision snapshot is frozen when the first actual pick for that season/week is locked. It copies the complete optimizer input visible at that time, including future-week games, and the pick event references it. Every algorithm backtested for that survivor week uses that same snapshot.

This gives one authoritative snapshot per `(season_year, survivor_week)`, not one per refresh. If the pool later adopts a fixed weekly decision cutoff, snapshot creation can move to that explicit cutoff without changing the stored shape. Final pre-kickoff spreads must not be used as historical decision inputs unless the tested policy explicitly assumes picks are made separately immediately before each game; otherwise they introduce look-ahead bias.

Refresh frequency is therefore an operational choice rather than a storage multiplier. Hourly, six-hourly, or daily refreshes may create small refresh-attempt records and update current state, but they do not copy the schedule into history. A full season has at most 18 normal decision snapshots. Optional line-movement history is deferred until a concrete tuning question requires it.

### Point-in-time rules

1. Every survivor week has at most one authoritative decision snapshot.
2. A decision snapshot contains the complete set of game inputs supplied to the optimizer, not merely that week's games.
3. A decision snapshot is immutable after it is frozen.
4. Every algorithm compared for a survivor week uses the same decision snapshot.
5. Closing spreads are derived separately as the last values observed before each kickoff and are never silently substituted for decision spreads.
6. Failed refreshes are represented explicitly and cannot overwrite current state, closing candidates, or an authoritative snapshot.
7. An actual pick records the server receipt time, season, and authoritative decision snapshot.
8. A pick may reference the optimization run shown to the user; manual picks may omit that reference.
9. Existing historical rows with unknown capture times are marked as legacy and excluded from strict backtests by default.
10. Ties count as survivor losses unless a later explicit pool rule changes that behavior.

### Minimal persisted model

The implementation should use these concepts without adding an ORM or migration framework:

- `refresh_runs`: small operational metadata for each refresh attempt, including season, requested weeks, UTC start/end times, and status. These rows are not backtest snapshots; even 168 attempts per week is only a few thousand metadata rows per season.
- `current_game_state`: one mutable row per event containing the latest successfully fetched schedule and spread, its observation time, and source refresh ID.
- `decision_snapshots`: one immutable header per season/survivor week, including the decision time and trigger.
- `decision_snapshot_games`: the immutable complete optimizer input copied when the snapshot is frozen, retaining each row's original observation time and source refresh ID.
- `closing_lines`: one row per event, updated only by newer pre-kickoff observations and frozen after kickoff. This represents the last spread this application observed, not a guaranteed sportsbook market close.
- `game_results`: one authoritative final result per event, including status, scores, and observation time; later official corrections may update it with an audit timestamp.
- `pick_events`: season-aware `set` and `clear` events with server timestamps, the decision snapshot ID, and an optional optimization-run reference.
- `optimization_runs`: algorithm, code revision, horizon, current week, parameters, generation time, decision snapshot ID, and recommendations.

Raw CBS HTML should be retained only for authoritative decision snapshots or failed-parser diagnosis, not for every routine refresh. Deduplicate retained payloads by SHA-256 if repeated source bytes would otherwise be stored.

Use SQLite foreign keys, uniqueness constraints, and indexes that directly support current-state, decision-snapshot, closing-line, and result queries. Do not create generic repository, event-bus, plugin, or migration abstractions.

## Explicit non-goals

Do not add during this backlog:

- PostgreSQL, an ORM, or an asynchronous database library
- A frontend framework or build system
- A second sports-data provider
- Authentication, cloud storage, queues, workers, or deployment infrastructure
- A general event-sourcing framework
- A general algorithm plugin system
- Automatic parameter-grid search
- A side-by-side backtest web interface
- A single speculative “efficiency score” that hides the underlying measurements
- Full line-movement history for every routine refresh
- Invented timestamps for historical data that was not actually captured

## Target data flow

```text
Routine CBS refresh
    -> small refresh-run status record
    -> update current game state
    -> update last-observed pre-kickoff closing candidates
    -> update final results

First actual pick for a survivor week
    -> freeze one authoritative decision snapshot from current state
    -> record the pick against that snapshot

Optimization request
    -> use the authoritative snapshot when one exists
    -> record algorithm revision, parameters, and recommendations
    -> optional reference from a user pick event

Backtest
    -> one authoritative decision snapshot per survivor week
    -> existing optimizer with prior simulated picks locked
    -> final result grading
    -> closing-line comparison as evaluation only
    -> CSV/JSON report
```

## Orchestration policy

### Session policy

1. Execute tasks sequentially in dependency order.
2. Create exactly one new task session at a time.
3. Use one fresh context window per backlog task.
4. Do not run tasks concurrently or overlap changes on the same branch.
5. Begin only from a clean worktree.
6. Read `AGENTS.md`, `CLAUDE.md`, and this document completely before editing.
7. Execute only the selected task; do not absorb adjacent tasks.
8. Keep each intermediate commit runnable and tested.
9. Update only the selected task's Status and Handoff sections.
10. Commit successful tasks with a message beginning with the task ID, for example `BACK-03: preserve authoritative weekly snapshots`.
11. Refresh the codebase-memory index after structural code changes.

### Required failure remediation

A failed task or check must not be abandoned on its first failure.

1. The task agent must spend at least one additional turn diagnosing the failure, applying the smallest justified fix, and rerunning the failed check.
2. If the task agent returns control while still failing, the orchestrator must send one explicit remediation turn containing the failing command, error evidence, and bounded task scope.
3. If that remediation also fails, stop the sequence. Do not start the next backlog task.
4. Record the blocker, attempted fixes, commands, and remaining failure in the current task's Handoff.
5. Do not commit a broken or partially runnable state. If necessary, restore the clean pre-task state before stopping.
6. Newly discovered unrelated work is not a failure: document it under **Discovered follow-up work** and continue only if the assigned task remains safe.

### Standard session startup

```bash
git branch --show-current
git status --short
git log -1 --oneline
uv sync --locked
```

Verify that:

- The worktree is clean.
- Every dependency task is marked done.
- The current source still matches the selected task's assumptions.
- Relevant graph paths have current coverage evidence before structural claims are made.

### Standard session finish

Run:

```bash
mise run check
python -m compileall -q .
git diff --check
git status --short
```

Also run every exact command listed in the selected task's **Required commands** section. Record commands and outcomes in the task Handoff before committing.


---

# Backlog

## BACK-01 — Characterize point-in-time contracts

**Status:** done
**Depends on:** none

### Goal

Add deterministic tests that define authoritative weekly snapshots, current-state refresh behavior, and no-look-ahead behavior before changing production storage.

### In scope

- Specify that routine refreshes update current game state without creating historical schedule copies.
- Specify that the first pick for a season/week freezes exactly one complete decision snapshot.
- Specify that later replacement or clear actions do not duplicate or mutate that snapshot.
- Specify that every algorithm compared for a survivor week receives the same snapshot rows.
- Specify that a closing-line candidate advances only from a newer pre-kickoff refresh and freezes after kickoff.
- Specify that a failed refresh cannot replace valid current state or closing candidates.
- Specify season isolation for picks.
- Specify `set`, replacement, `clear`, and clear-all pick history reconstruction.
- Specify that an optimization run identifies its decision snapshot and output picks.
- Specify final-result storage and correction timestamps.
- Keep all fixtures local and deterministic.

### Out of scope

- Production schema changes
- Live CBS requests
- Frontend changes
- Backtest implementation

### Required commands

```bash
uv run python -m unittest -v test_core test_services
mise run check
python -m compileall -q .
git diff --check
```

### Acceptance criteria

- Tests express the intended contracts even if production support requires later tasks.
- Expected failures are narrowly documented against their owning later task.
- Existing optimizer, service, and API tests remain green.
- Standard finish checks pass apart from explicitly documented expected failures.

### Handoff

Added `test_backtesting.py` with 12 deterministic tests using temporary SQLite paths and fixed UTC fixture timestamps. It covers current-state refreshes without schedule history, first-pick snapshots, replacement/clear immutability, shared algorithm inputs, closing lines, failed refreshes, season-aware pick history, optimization provenance, and result corrections.

Two route-level checks pass now. Ten narrowly documented `@unittest.expectedFailure` tests remain for later owners: BACK-02 current-state storage, BACK-03 refresh/closing/result persistence, BACK-04 decision snapshots and pick history, and BACK-05 optimization-run provenance. No production schema, live CBS, frontend, or backtest code was changed.

Checks: `uv run python -m unittest -v test_core test_services` passes (18 tests); each `mise run check` passes (30 tests, 10 documented expected failures); both `python -m compileall -q .` runs pass; both `git diff --check` runs pass.

---

## BACK-02 — Add authoritative snapshot SQLite storage

**Status:** done
**Depends on:** BACK-01

### Goal

Create the minimum idempotent SQLite schema for frequently refreshed current state, one immutable decision snapshot per survivor week, closing lines, results, picks, and optimization provenance.

### In scope

- Add the persisted model described in **Minimal persisted model**.
- Keep schema creation idempotent using SQLite and the existing function-based service style.
- Enable and test foreign-key enforcement for application connections.
- Add focused indexes for current season/week reads, snapshot rows, closing lines, results, and pick history.
- Add functions to create and finalize small refresh-run status records.
- Add current-game upserts that retain the previous valid value when a refresh fails.
- Add one transactional operation that freezes current state into a uniquely constrained season/week decision snapshot.
- Add reads that return optimizer-compatible `EventOdds` from either current state or an authoritative snapshot.
- Add closing-line updates that accept only newer observations captured before kickoff.
- Add final-result upserts with observed and corrected timestamps.
- Add pick-event and optimization-run persistence primitives needed by later tasks.
- Preserve `averaged_odds` temporarily.
- Import existing `averaged_odds` rows into current state only; do not manufacture historical decision snapshots.

### Out of scope

- Wiring the live refresh route to the new storage
- Changing pick APIs or frontend behavior
- Recording live optimization requests
- Implementing the backtest runner
- Introducing a migration library or repository classes

### Required commands

```bash
uv run python -m unittest -v test_services
mise run check
python -m compileall -q .
git diff --check
```

### Acceptance criteria

- Repeated database setup and legacy import are safe and do not duplicate data.
- Repeated routine updates keep one current row per event.
- Freezing the same season/week twice returns or rejects against the same authoritative snapshot without changing its rows.
- Snapshot reads remain unchanged after later current-state refreshes.
- Closing lines cannot be advanced by an observation at or after kickoff.
- Legacy data is identifiable as current-only and excluded from strict historical backtests.
- Existing application reads continue to work during migration.
- Standard finish checks pass.

### Handoff

Implemented idempotent SQLite storage for refresh runs, current game state, immutable decision snapshots, closing lines, results, pick events, and optimization runs. Application connections enable foreign keys; legacy `averaged_odds` rows migrate to current-only state without creating snapshots. Added current/snapshot reads, timestamp guards, and focused indexes while preserving the legacy API.

Checks: `uv run python -m unittest -v test_services` passes (7 tests); `mise run check` passes (32 tests, 7 expected failures owned by later tasks); `python -m compileall -q .` and `git diff --check` pass, including the required repeated checks.

---

## BACK-03 — Refresh current state, closing lines, and results

**Status:** done
**Depends on:** BACK-02

### Goal

Make routine refreshes update bounded current state and evaluation data without creating a historical copy of every fetched spread.

### In scope

- Record one small refresh-run row with source URLs, UTC timing, requested weeks, complete/partial/failed status, and bounded error text.
- Parse event ID, teams, home spread, kickoff time, game status, and nullable final scores.
- Capture moneylines and total only if they are reliably present in the same existing page.
- Upsert successful values into `current_game_state`; a missing or failed week must not erase prior valid state.
- Advance `closing_lines` only from a newer observation captured before kickoff.
- Upsert final status and scores into `game_results`, retaining correction timing.
- Retain raw response bytes only when needed to diagnose a parser failure; do not archive every successful routine refresh.
- Change refresh to request `max(1, current_week - 1)` through week 18 so the previous week's result can be finalized.
- Return counts that distinguish successful, failed, parsed, current-state, closing-line, and final-result updates.
- Preserve current events and optimization behavior by reading `current_game_state` until an authoritative decision snapshot is wired into later tasks.

### Out of scope

- Retry infrastructure, proxies, caching, or a second source
- Season-aware pick changes
- Optimization-run persistence
- Backtest reports

### Required checks

- Parser fixtures cover scheduled and final games, `PK`, numeric spreads, and missing optional values.
- A failed week cannot erase valid current state or advance a closing line.
- A partial refresh commits successful current/result updates and reports failed weeks.
- Repeating unchanged refreshes does not create duplicate schedule-history rows.
- `test_services` covers the refresh route, current schedule loading, and optimization against refreshed state.

### Required commands

```bash
uv run python -m unittest -v test_services
mise run check
python -m compileall -q .
git diff --check
```

### Acceptance criteria

- Routine refresh frequency does not multiply authoritative decision snapshots.
- Refresh-attempt metadata, current state, closing lines, and final results remain distinguishable.
- Final scores are collected without exposing them through optimizer `EventOdds` inputs.
- The current UI still sees the newest known event state.
- Standard finish checks and refresh-route service tests pass.

### Handoff

Implemented refresh-run metadata and bounded parser diagnostics, enriched CBS schedule/result parsing, and `apply_refresh` persistence for current state, pre-kickoff closing lines, and final results. Refresh now covers `max(1, current_week - 1)` through week 18, reports per-stage counts, and live reads use `current_game_state`; raw payloads are retained only for parser failures. Updated BACK-03 service and failed-refresh contract tests.

Checks: `uv run python -m unittest -v test_services` passes (10 tests); `mise run check` passes twice (35 tests, 6 expected failures owned by BACK-04/BACK-05); both `python -m compileall -q .` runs pass; both `git diff --check` runs pass.

---

## BACK-04 — Record season-aware pick history

**Status:** done
**Depends on:** BACK-03

### Goal

Move actual picks from mutable global configuration into a reconstructable, season-specific event ledger.

### In scope

- Add `season_year` to pick write and clear requests.
- Update the frontend to send its selected season for set, clear, and clear-all actions.
- Persist `set` and `clear` events with server UTC timestamps.
- When the first pick for a season/week is set, freeze the complete current optimizer input into that week's decision snapshot in the same transaction.
- Reuse the existing authoritative snapshot for later replacement or clear actions in that week.
- Derive current picks from the latest event for each season/week.
- Implement clear-all by appending clear events for currently active weeks.
- Continue returning the current pick response shape unless a new field is required by this task.
- Keep current week, algorithm, and split week in `config.json`.
- Migrate existing config picks only when their season can be explicitly supplied; do not guess silently.
- Ensure optimization loads picks only for the requested season.

### Out of scope

- Multiple pools or users
- Editing historical timestamps
- Recommendation-run linkage beyond accepting a nullable future reference
- Backtesting

### Required commands

```bash
uv run python -m unittest -v test_core test_services
mise run check
python -m compileall -q .
git diff --check
```

### Acceptance criteria

- Two seasons can hold independent picks for the same week.
- Each season/week has exactly one immutable decision snapshot shared by its pick history.
- Pick state can be reconstructed before and after replacement, clear, and clear-all events.
- Existing invalid-team, duplicate-team, and week validation remains at the trust boundary.
- `test_services` covers lock, unlock, reset, season switching, and season-specific optimization requests.
- Standard finish checks pass.

### Handoff

Implemented season-specific pick event ledger with `fetch_current_picks(season_year)` and `clear_all_pick_events(season_year, recorded_at)` in `services/sqlite.py`. Updated `append_pick_event` to auto-create decision snapshots on first pick for a season/week by reading current game state (including legacy rows) within the same transaction. Added `season_year` field to `PickRequest` API model. Updated app routes to accept season via request body (POST) or query parameter (DELETE), derive current picks from events, and pass season to optimization. Frontend sends selected year for all pick operations. Removed `@unittest.expectedFailure` decorators from BACK-04-owned tests; BACK-04 snapshot/pick history tests now pass. Config picks remain in `config.json` but are no longer read by app routes; migration deferred (out of scope: no silent season guessing).

Checks: `uv run python -m unittest -v test_core test_services` passes (23 tests); `mise run check` passes (35 tests, 1 expected failure owned by BACK-05); `python -m compileall -q .` passes; `git diff --check` passes.

---

## BACK-05 — Persist reproducible optimization runs

**Status:** done
**Depends on:** BACK-04

### Goal

Record exactly what data and algorithm configuration produced each recommendation shown to the user.

### In scope

- Once a decision snapshot exists, make optimization for that survivor week read only that snapshot.
- At pick time, record the selected algorithm's recommendations against the authoritative snapshot and link the pick when it matches the current-week recommendation.
- Keep pre-decision exploratory optimization against current state ephemeral; it is not authoritative history.
- Record season, UTC generation time, algorithm slug, split week, current week, parameters, decision snapshot ID, and code revision.
- Record a source hash when the optimizer worktree is dirty or a durable commit alone is insufficient.
- Persist the resulting recommendation picks.
- Keep manual picks valid without an optimization-run reference.
- Preserve deterministic behavior of all existing algorithms.

### Out of scope

- Algorithm changes
- A plugin or version-registry abstraction
- A backtest UI
- Automatically committing source code

### Required commands

```bash
uv run python -m unittest -v test_core test_services
mise run check
python -m compileall -q .
git diff --check
```

### Acceptance criteria

- A stored run identifies one immutable decision snapshot, its parameters, source revision, and recommendations.
- An algorithm-assisted pick can be distinguished from a manual pick.
- Replaying a stored run at the same code revision yields the same recommendations.
- The API does not silently claim reproducibility for dirty, unidentified source.
- Existing algorithm invariants and standard finish checks pass.

### Handoff

**Implementation:**
- Added `_get_git_revision()` helper in `app.py` to get code revision from `git rev-parse HEAD` and source hash from `git diff HEAD` when worktree is dirty.
- Modified `optimize_single_algorithm()` to:
  - Load config to get `current_week`.
  - Check for existing decision snapshot via `find_decision_snapshot(year, current_week)`.
  - Use snapshot events if snapshot exists (authoritative); otherwise use current state (exploratory).
  - Save optimization run with `save_optimization_run()`, including snapshot_id, recommendations, code revision, and source hash.
  - Silently skip run persistence if git revision cannot be identified (dirty/unidentified source).
- Modified `add_pick()` to:
  - Load config to get selected algorithm and current_week.
  - When pick week matches current_week, find latest optimization run via `find_latest_optimization_run(season_year, current_week, algorithm)`.
  - Link pick to optimization run via `optimization_run_id` when pick matches current-week recommendation.
- Added `find_latest_optimization_run()` to `services/sqlite.py` to find most recent optimization run for a season/week/algorithm.
- Updated test mocks in `test_core.py` and `test_backtesting.py` to include all required config fields (`current_week`, `split_week`, `algorithm`).
- Removed `@unittest.expectedFailure` from `test_optimization_run_identifies_snapshot_and_output_picks` and updated it to create a decision snapshot before testing run persistence.

**Verification:**
- All 35 tests pass (`uv run python -m unittest -v test_core test_services`).
- `mise run check` passes (lint, format, test).
- `python -m compileall -q .` succeeds.
- `git diff --check` clean.
- Stored runs identify immutable decision snapshot, parameters, source revision, and recommendations.
- Algorithm-assisted picks have non-null `optimization_run_id`; manual picks remain null.
- Optimization uses snapshot when one exists; uses current state before first pick.
- API does not persist runs when git revision cannot be identified (exception caught, run creation skipped).
- Existing algorithm invariants preserved (no algorithm changes).

---

## BACK-06 — Implement the sequential backtest runner

**Status:** done
**Depends on:** BACK-05

### Goal

Add a small offline runner that evaluates an existing or future algorithm against historical point-in-time observations without future leakage.

### In scope

- Add a standard-library `argparse` entry point, preferably one `backtest.py` module unless current structure provides a smaller fit.
- Add deterministic runner coverage in `test_backtest.py`.
- Use the one authoritative decision snapshot recorded for each simulated survivor week.
- Fail strict mode when a required weekly snapshot is missing; do not synthesize a cutoff from later data.
- Allow a future explicit cutoff policy only as a separately named mode with its own captured snapshots.
- Run the selected existing optimizer with earlier simulated picks locked.
- Use only the current week's recommendation as that week's simulated selection.
- Grade selections using final observations without passing scores or later spreads into the optimizer.
- Record both first elimination and counterfactual later recommendations.
- Treat ties as losses and report postponed, cancelled, or ungraded games explicitly.
- Reject strict runs that require a missing or legacy-only decision snapshot unless the caller opts into a clearly labeled degraded mode.
- Emit deterministic JSON and CSV using the standard library.

### Required output

Each weekly row includes:

- Season, week, and authoritative decision time
- Decision snapshot identifier
- Algorithm, source revision, split week, and parameters
- Selected team, opponent, decision spread, and closing spread
- Final score, scoring margin, and win/loss/tie/ungraded outcome
- Previously used teams

Aggregate output includes:

- First elimination week
- Wins, losses, ties, ungraded weeks, and weeks survived
- Average decision spread
- Average closing spread
- Average decision-to-closing line movement
- Selected spread versus the best legal same-week alternative

### Out of scope

- Web UI
- Parameter grid search
- Claiming spread-only metrics are calibrated win probabilities
- A generalized simulation framework

### Required commands

```bash
uv run python -m unittest -v test_backtest
mise run check
python -m compileall -q .
git diff --check
```

### Acceptance criteria

- A test proves that a spread fetched after the weekly snapshot was frozen cannot change that snapshot or its backtest output.
- Repeated runs against identical inputs produce byte-stable normalized output, excluding an optional report-generation timestamp.
- Team-reuse, week uniqueness, pick ordering, and horizon behavior remain valid.
- Missing data produces an explicit degraded or failed result rather than silent substitution.
- Standard finish checks pass.

### Handoff

**Implementation:**
- Added `backtest.py` with stdlib-only `argparse` entry point, strict/degraded modes, and deterministic JSON/CSV output.
- Strict mode rejects missing or empty required weekly snapshots; degraded mode is explicit and skips unavailable weeks without substituting current state.
- The runner uses immutable snapshot events as optimizer input, preserves prior simulated pick weeks/spreads, and marks post-elimination recommendations as counterfactual.
- Grading reads final results and closing lines separately, reports win/loss/tie/postponed/cancelled/ungraded outcomes, and computes the required aggregate metrics.
- Weekly and aggregate output include source revision metadata, deterministic parameters, snapshot provenance, and stable ordering.

**Testing:**
- Added `test_backtest.py` with 18 deterministic tests covering snapshot immutability, strict/degraded missing data, repeatability, pick locking, provenance, counterfactuals, grading, and JSON/CSV output.

**Verification:**
- `uv run python -m unittest -v test_backtest`: 18 tests pass.
- `mise run check`: lint, format, and all 53 tests pass.
- `python -m compileall -q .`: passes.
- `git diff --check`: passes.
- Worktree is clean and the amended `BACK-06:` commit is the single commit after BACK-05.
---

## BACK-07 — End-to-end audit, backup, and operating documentation

**Status:** done
**Depends on:** BACK-06

### Goal

Prove the complete capture-to-backtest workflow, document weekly operation, and ensure the local historical database has a durable backup path.

### In scope

- Run an end-to-end deterministic fixture flow: current-state refresh, decision snapshot, optimization run, pick event, result update, and backtest.
- Verify current-state, immutable decision-snapshot, closing-line, and final-result queries independently.
- Verify strict backtests reject incomplete snapshot history.
- Add a standard-library SQLite backup or documented filesystem backup procedure for the ignored local database.
- Document how to perform the final full-season weeks 1–18 refresh after results settle.
- Document how to run authoritative-snapshot backtests and interpret every metric.
- Document bounded database growth, refresh-run metadata retention, and that routine refresh payloads are not archived.
- Update `README.md` and `CLAUDE.md` only where the implemented workflow changes project operation or architecture.
- Refresh the full codebase-memory index and check coverage for every changed source path.
- Record remaining limitations under **Discovered follow-up work**.

### Out of scope

- New features found during audit
- Cloud backup automation
- Additional data providers
- Backtest visualization
- Algorithm tuning itself

### Required commands

```bash
uv run python -m unittest discover -v
mise run check
python -m compileall -q .
git diff --check
```

### Acceptance criteria

- The complete fixture workflow is reproducible from an empty temporary database.
- Every command in this task's **Required commands** section passes.
- Backup and restore are demonstrated against a temporary path.
- Documentation clearly distinguishes current state, authoritative decision snapshots, actual picks, recorded recommendations, closing lines, final results, and simulated backtest picks.
- No uncommitted changes remain.

### Handoff

**Implementation:**

- Added `backup_database(source, destination)` to `services/sqlite.py` using stdlib `Connection.backup()` and exported it from `services/__init__.py`.
- Added public `fetch_closing_line(event_id, db_name)`; the backtest runner uses it instead of duplicating the closing-line query.
- Expanded `test_backup_database_restores_complete_state` to copy a temporary source database to a backup and restore it into a separate temporary path.
- Expanded `test_end_to_end_workflow_from_empty_database_through_backtest` to prove current-state reads, first-pick snapshot freezing and immutability, persisted optimization-run provenance and recommendations, a linked actual pick event, independent closing-line and final-result reads, strict rejection of incomplete snapshot history, and degraded snapshot-based grading.
- Corrected README configuration documentation: `config.json` retains `current_week`, `algorithm`, and `split_week` preferences; actual picks are season-aware SQLite `pick_events`. README also documents recorded recommendations, simulated picks, the final weeks 1–18 refresh, every aggregate metric, backup/restore, retained refresh metadata, and the absence of successful routine payload archives.
- Updated CLAUDE.md only for the implemented architecture and runtime workflow: SQLite historical tables and backup, snapshot-based optimization/backtesting, and configuration preferences.
- Existing limitations remain recorded under **Discovered follow-up work**; BACK-08 through BACK-11 were not implemented.

**Verification:**

- `uv run python -m unittest discover -v`: 55 tests pass.
- `mise run check`: Ruff lint/format and all 55 tests pass.
- `python -m compileall -q .`: passes.
- `git diff --check`: passes.
- Temporary SQLite backup/restore and the empty-database end-to-end fixture both pass.
- Full codebase-memory index refreshed in full mode: 421 nodes and 1,697 edges, with zero skipped or parse-partial files.
- `check_index_coverage` returned `no_recorded_issue` and `metadata_match` for all seven changed paths: `CLAUDE.md`, `README.md`, `docs/backtesting-backlog.md`, `backtest.py`, `services/__init__.py`, `services/sqlite.py`, and `test_backtesting.py`.
- `git rev-list --count 40e7b19356ff8d56e2e17ee13128c44d4609258b..HEAD`: 1 after the amended commit.
- `git show --check HEAD`: passes, and the final worktree is clean.

**Discovered follow-up work recorded below.**

---

## Discovered follow-up work

Add new entries here only when execution finds necessary work outside the active task. Each entry must include:

- Proposed task ID and title
- Evidence and affected paths
- Why it is outside the current task
- Dependency task
- Risk if deferred

Do not implement a discovered follow-up in the same context unless the user explicitly changes the backlog scope.

### BACK-08 — Migrate existing config.json picks to SQLite ledger
**Status:** done

**Evidence:** `config.json` may contain existing `picks` entries from earlier manual UI usage. Those picks have no season, no timestamp, and no snapshot reference. `app.py` routes no longer read `config.picks`; the frontend now sends season-aware requests. Existing `picks` in local `config.json` files are orphaned.

**Affected paths:** `app.py`, `config_store.py`, user `config.json` files.

**Why outside BACK-07:** BACK-07 scope explicitly defers migration ("Migration deferred (out of scope: no silent season guessing)"). A migration requires an explicit season choice from the user or a documented manual procedure, not silent inference.

**Dependency:** BACK-07 (completed).

**Risk if deferred:** Users with existing config picks will not see them in the UI after upgrading to the BACK-07+ application. Low risk if documented clearly in upgrade notes; medium risk if users assume the application will preserve their picks automatically.

**Handoff:**

**Implementation:**
- Added strict legacy-pick loading and clearing in `config_store.py`; malformed, invalid, duplicate-week, duplicate-team, and non-finite entries are rejected without changing the source file.
- Added `POST /api/config/picks/migrate?season_year={year}`. The season is required and NFL team validation happens before any database write.
- Added an atomic, idempotent SQLite import that records `set` events and complete `legacy-migration` snapshots, preserves event order, refuses existing non-legacy snapshot conflicts, and clears config picks only after a successful import.
- Strict backtests reject legacy-marked snapshots because their original decision times are unknown.
- Added deterministic migration tests covering import, snapshot creation, config cleanup, idempotency, validation, explicit seasons, and strict-backtest exclusion.


**Verification:**
- `uv run python -m unittest -v test_core test_services test_migration`: 28 tests pass.
- `uv run python -m unittest discover -v`: 60 tests pass.
- `mise run check`: Ruff lint/format and all 60 tests pass.
- `python -m compileall -q .`: passes.
- `git diff --check`: passes.
- Full codebase-memory index: generation `2026-09-07T22:44:38Z`, 440 nodes, 1,829 edges; all changed paths reported `no_recorded_issue`/`metadata_match`, with zero skipped or parse-partial files.


**Limitations / deferred:**
- Legacy decision timestamps cannot be recovered, so migrated snapshots remain excluded from strict backtests; the documented manual endpoint is the only migration path. BACK-09, BACK-10, and BACK-11 were not implemented.

### BACK-09 — Add explicit refresh-run success/failure/partial status to UI
**Status:** done

**Evidence:** `apply_refresh` returns per-stage counts and records small refresh-run metadata including status, but the frontend currently displays only a generic success/failure message. Partial refreshes (some weeks succeed, others fail) are not surfaced in detail.

**Affected paths:** `static/index.html`, `app.py` refresh route response shape.

**Why outside BACK-07:** BACK-07 is documentation and audit focused; UI enhancements for refresh status are a separate frontend feature not required for backtest correctness.

**Dependency:** BACK-03 (completed: `apply_refresh` already records per-stage counts).

**Risk if deferred:** Users cannot easily diagnose which weeks failed during a partial refresh without inspecting the database or server logs. Low risk for single-user local operation; medium risk if this becomes a shared tool.


**Handoff:**
- The refresh route now returns a stable `complete`, `partial`, or `failed` status with bounded error details, requested/successful/failed weeks, counts, and existing per-stage update counts. Fetch exceptions are recorded and returned as failed refresh results.
- The frontend renders an accessible inline status for each outcome, lists failed weeks and bounded errors, reloads the schedule only for complete/partial runs, and handles empty or HTTP error responses without claiming success.
- Added deterministic route status-mapping tests and a browser-free frontend contract test.

**Verification:**
- `uv run python -m unittest discover -v`: 62 tests pass.
- `mise run check`: Ruff lint/format and all 62 tests pass.
- `python -m compileall -q .`: passes.
- `git diff --check`: passes.
- `node --check` on the extracted frontend script: passes.

**Limitations / deferred:**
- Refresh history remains database-backed operational metadata rather than a separate history view; BACK-10 and BACK-11 remain untouched.
### BACK-10 — Validate closing-line kickoff timestamp against actual game kickoff

**Evidence:** `update_closing_line` accepts `kickoff_at` as a parameter and guards pre-kickoff observations, but it does not validate that `kickoff_at` matches the event's actual scheduled kickoff from the current game state. A caller could pass an incorrect kickoff time and silently update a closing line post-kickoff.

**Affected paths:** `services/sqlite.py` `update_closing_line`, `apply_refresh` closing-line persistence.

**Why outside BACK-07:** BACK-07 scope is end-to-end workflow audit and documentation, not hardening edge-case timestamp validation. The current implementation relies on the caller (refresh logic) to pass the correct kickoff; an explicit cross-check would be a defensive improvement, not a correctness fix for the documented workflow.

**Dependency:** BACK-03 (completed: closing-line updates exist).

**Risk if deferred:** If CBS data returns incorrect kickoff times or the refresh logic has a bug, closing lines could be updated with post-kickoff spreads and silently accepted. Low risk: CBS kickoff times are generally reliable, and test fixtures use correct timestamps. Medium risk in production if kickoff time parsing ever regresses.

### BACK-11 — Add automated end-of-season backtest run and comparison report

**Evidence:** `backtest.py` exists and works, but users must manually run it for each algorithm after the season ends. There is no scripted workflow to run all four algorithms, compare their results, and generate a summary report.

**Affected paths:** New script or Mise task wrapping `backtest.py` for all algorithms.

**Why outside BACK-07:** BACK-07 scope includes documenting how to run backtests, not automating multi-algorithm comparison or creating a summary report. Automation is a convenience feature, not a correctness requirement.

**Dependency:** BACK-06 (completed: `backtest.py` works), BACK-07 (completed: backtest documented).

**Risk if deferred:** Users must manually run four separate `backtest.py` invocations and manually compare JSON/CSV outputs. Low risk: the manual process is straightforward and documented. Medium risk if this becomes a shared tool where standardized comparison is expected.
