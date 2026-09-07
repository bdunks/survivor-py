import json
import sqlite3
import uuid
from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from models import EventOdds, Pick

DEFAULT_DB_NAME = "odds_data.db"

LEGACY_SNAPSHOT_TRIGGER = "legacy-migration"


Timestamp = str | datetime


def _utc_timestamp(value: Timestamp | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        timestamp = value
    else:
        text = value[:-1] + "+00:00" if value.endswith("Z") else value
        try:
            timestamp = datetime.fromisoformat(text)
        except ValueError as error:
            raise ValueError(f"Invalid UTC timestamp: {value!r}") from error

    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC).isoformat()


def _timestamp_key(value: str) -> datetime:
    timestamp = _utc_timestamp(value)
    if timestamp is None:
        raise ValueError("timestamp is required")
    return datetime.fromisoformat(timestamp)


def _ensure_columns(
    connection: sqlite3.Connection,
    table: str,
    columns: Mapping[str, str],
) -> None:
    existing = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
    for name, definition in columns.items():
        if name not in existing:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


@contextmanager
def _connection(db_name: str | Path = DEFAULT_DB_NAME) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(db_name)
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def _setup_database(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS averaged_odds (
            event_id INTEGER PRIMARY KEY,
            season_year INTEGER,
            week INTEGER,
            home_team TEXT,
            away_team TEXT,
            short_name TEXT,
            spread REAL
        )
        """
    )
    connection.execute("DROP TRIGGER IF EXISTS update_averaged_odds")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS refresh_runs (
            refresh_id TEXT PRIMARY KEY,
            season_year INTEGER NOT NULL,
            requested_weeks TEXT NOT NULL,
            source_urls TEXT NOT NULL DEFAULT '[]',
            started_at TEXT NOT NULL,
            finished_at TEXT,
            status TEXT NOT NULL,
            error TEXT
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS refresh_payloads (
            refresh_id TEXT NOT NULL,
            week INTEGER NOT NULL,
            source_url TEXT NOT NULL,
            payload BLOB NOT NULL,
            error TEXT NOT NULL,
            PRIMARY KEY (refresh_id, week),
            FOREIGN KEY (refresh_id) REFERENCES refresh_runs(refresh_id)
                ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS current_game_state (
            event_id INTEGER PRIMARY KEY,
            season_year INTEGER,
            week INTEGER,
            home_team TEXT,
            away_team TEXT,
            short_name TEXT,
            spread REAL,
            kickoff_at TEXT,
            game_status TEXT,
            home_score INTEGER,
            away_score INTEGER,
            home_moneyline INTEGER,
            away_moneyline INTEGER,
            total REAL,
            observed_at TEXT,
            refresh_id TEXT,
            is_legacy INTEGER NOT NULL DEFAULT 0 CHECK (is_legacy IN (0, 1))
        )
        """
    )
    _ensure_columns(
        connection,
        "refresh_runs",
        {"source_urls": "TEXT NOT NULL DEFAULT '[]'"},
    )
    _ensure_columns(
        connection,
        "current_game_state",
        {
            "home_moneyline": "INTEGER",
            "away_moneyline": "INTEGER",
            "total": "REAL",
        },
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS decision_snapshots (
            snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
            season_year INTEGER NOT NULL,
            survivor_week INTEGER NOT NULL,
            decision_at TEXT NOT NULL,
            trigger TEXT NOT NULL,
            UNIQUE (season_year, survivor_week)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS decision_snapshot_games (
            snapshot_id INTEGER NOT NULL,
            event_id INTEGER NOT NULL,
            season_year INTEGER NOT NULL,
            week INTEGER NOT NULL,
            home_team TEXT NOT NULL,
            away_team TEXT NOT NULL,
            short_name TEXT NOT NULL,
            spread REAL NOT NULL,
            observed_at TEXT,
            refresh_id TEXT,
            PRIMARY KEY (snapshot_id, event_id),
            FOREIGN KEY (snapshot_id) REFERENCES decision_snapshots(snapshot_id)
                ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS closing_lines (
            event_id INTEGER PRIMARY KEY,
            season_year INTEGER,
            week INTEGER,
            spread REAL NOT NULL,
            observed_at TEXT NOT NULL,
            kickoff_at TEXT NOT NULL,
            refresh_id TEXT
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS game_results (
            event_id INTEGER PRIMARY KEY,
            season_year INTEGER,
            week INTEGER,
            status TEXT NOT NULL,
            home_score INTEGER,
            away_score INTEGER,
            observed_at TEXT NOT NULL,
            corrected_at TEXT
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS optimization_runs (
            run_id INTEGER PRIMARY KEY AUTOINCREMENT,
            season_year INTEGER NOT NULL,
            algorithm TEXT NOT NULL,
            split_week INTEGER NOT NULL,
            current_week INTEGER NOT NULL,
            parameters TEXT NOT NULL,
            code_revision TEXT NOT NULL,
            source_hash TEXT,
            generated_at TEXT NOT NULL,
            decision_snapshot_id INTEGER,
            recommendations TEXT NOT NULL,
            FOREIGN KEY (decision_snapshot_id) REFERENCES decision_snapshots(snapshot_id)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS pick_events (
            pick_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            season_year INTEGER NOT NULL,
            week INTEGER NOT NULL,
            action TEXT NOT NULL CHECK (action IN ('set', 'clear')),
            team TEXT,
            spread REAL,
            recorded_at TEXT NOT NULL,
            decision_snapshot_id INTEGER,
            optimization_run_id INTEGER,
            FOREIGN KEY (decision_snapshot_id) REFERENCES decision_snapshots(snapshot_id),
            FOREIGN KEY (optimization_run_id) REFERENCES optimization_runs(run_id)
        )
        """
    )
    for statement in (
        (
            "CREATE INDEX IF NOT EXISTS idx_current_state_season_week "
            "ON current_game_state (season_year, week)"
        ),
        (
            "CREATE INDEX IF NOT EXISTS idx_current_state_season_observed "
            "ON current_game_state (season_year, observed_at)"
        ),
        (
            "CREATE INDEX IF NOT EXISTS idx_snapshot_games_snapshot_week "
            "ON decision_snapshot_games (snapshot_id, week)"
        ),
        (
            "CREATE INDEX IF NOT EXISTS idx_closing_lines_observed "
            "ON closing_lines (observed_at)"
        ),
        (
            "CREATE INDEX IF NOT EXISTS idx_game_results_season_week "
            "ON game_results (season_year, week)"
        ),
        (
            "CREATE INDEX IF NOT EXISTS idx_pick_events_season_week_recorded "
            "ON pick_events (season_year, week, recorded_at)"
        ),
        (
            "CREATE INDEX IF NOT EXISTS idx_optimization_runs_season_generated "
            "ON optimization_runs (season_year, generated_at)"
        ),
    ):
        connection.execute(statement)

    _import_legacy_odds(connection)


def _import_legacy_odds(connection: sqlite3.Connection) -> None:
    rows = connection.execute(
        """
        SELECT event_id, season_year, week, home_team, away_team, short_name, spread
        FROM averaged_odds
        """
    ).fetchall()
    connection.executemany(
        """
        INSERT INTO current_game_state (
            event_id, season_year, week, home_team, away_team, short_name, spread,
            observed_at, refresh_id, is_legacy
        ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, 1)
        ON CONFLICT(event_id) DO UPDATE SET
            season_year = excluded.season_year,
            week = excluded.week,
            home_team = excluded.home_team,
            away_team = excluded.away_team,
            short_name = excluded.short_name,
            spread = excluded.spread
        WHERE current_game_state.is_legacy = 1
        """,
        rows,
    )


def setup_database(db_name: str | Path = DEFAULT_DB_NAME) -> None:
    with _connection(db_name) as connection:
        _setup_database(connection)


def save_odds_data(
    data: Iterable[EventOdds], db_name: str | Path = DEFAULT_DB_NAME
) -> None:
    with _connection(db_name) as connection:
        _setup_database(connection)
        connection.executemany(
            """
            INSERT OR REPLACE INTO averaged_odds
                (event_id, season_year, week, home_team, away_team, short_name, spread)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    item.event_id,
                    item.season_year,
                    item.week,
                    item.home_team,
                    item.away_team,
                    item.short_name,
                    item.spread,
                )
                for item in data
            ),
        )
        _import_legacy_odds(connection)


def fetch_odds_data(
    year: int, db_name: str | Path = DEFAULT_DB_NAME
) -> list[EventOdds]:
    return fetch_current_state(year, db_name)


def _events_from_rows(rows: Iterable[tuple[Any, ...]]) -> list[EventOdds]:
    events = []
    for event_id, season_year, week, short_name, spread, *_ in rows:
        try:
            events.append(
                EventOdds(
                    event_id=event_id,
                    season_year=season_year,
                    week=week,
                    short_name=short_name,
                    spread=spread,
                )
            )
        except (TypeError, ValueError):
            continue
    return events


def create_refresh_run(
    season_year: int,
    requested_weeks: Iterable[int],
    started_at: Timestamp,
    refresh_id: str | None = None,
    db_name: str | Path = DEFAULT_DB_NAME,
    source_urls: Iterable[str] | None = None,
) -> str:
    run_id = refresh_id or uuid.uuid4().hex
    requested_values = list(requested_weeks)
    source_values = list(source_urls or ())
    requested = json.dumps(requested_values, separators=(",", ":"))
    sources = json.dumps(source_values, separators=(",", ":"))
    with _connection(db_name) as connection:
        _setup_database(connection)
        connection.execute(
            """
            INSERT INTO refresh_runs
                (refresh_id, season_year, requested_weeks, source_urls, started_at, status)
            VALUES (?, ?, ?, ?, ?, 'running')
            """,
            (run_id, season_year, requested, sources, _utc_timestamp(started_at)),
        )
    return run_id


def finalize_refresh_run(
    refresh_id: str,
    finished_at: Timestamp,
    status: str,
    error: str | None = None,
    db_name: str | Path = DEFAULT_DB_NAME,
) -> None:
    with _connection(db_name) as connection:
        _setup_database(connection)
        cursor = connection.execute(
            """
            UPDATE refresh_runs
            SET finished_at = ?, status = ?, error = ?
            WHERE refresh_id = ?
            """,
            (
                _utc_timestamp(finished_at),
                status,
                None if error is None else str(error)[:1000],
                refresh_id,
            ),
        )
        if cursor.rowcount != 1:
            raise ValueError(f"Unknown refresh run: {refresh_id}")


start_refresh_run = create_refresh_run
finish_refresh_run = finalize_refresh_run


def _event_value(event: EventOdds, name: str) -> object | None:
    value = getattr(event, name, None)
    return None if value == "" else value


def _event_timestamp(event: EventOdds, name: str) -> str | None:
    value = _event_value(event, name)
    if value is None:
        return None
    try:
        return _utc_timestamp(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _upsert_current_event(
    connection: sqlite3.Connection,
    event: EventOdds,
    observed_at: Timestamp | None,
    refresh_id: str | None,
) -> bool:
    observed = _utc_timestamp(observed_at)
    is_legacy = int(observed is None)
    previous = connection.execute(
        "SELECT observed_at, is_legacy FROM current_game_state WHERE event_id = ?",
        (event.event_id,),
    ).fetchone()
    if previous is not None:
        previous_observed, previous_legacy = previous
        if not previous_legacy and observed is None:
            return False
        if previous_observed and observed:
            try:
                if _timestamp_key(observed) < _timestamp_key(previous_observed):
                    return False
            except ValueError:
                pass

    connection.execute(
        """
        INSERT INTO current_game_state (
            event_id, season_year, week, home_team, away_team, short_name, spread,
            kickoff_at, game_status, home_score, away_score, home_moneyline,
            away_moneyline, total, observed_at, refresh_id, is_legacy
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(event_id) DO UPDATE SET
            season_year = excluded.season_year,
            week = excluded.week,
            home_team = excluded.home_team,
            away_team = excluded.away_team,
            short_name = excluded.short_name,
            spread = COALESCE(excluded.spread, current_game_state.spread),
            kickoff_at = COALESCE(
                excluded.kickoff_at, current_game_state.kickoff_at
            ),
            game_status = COALESCE(
                excluded.game_status, current_game_state.game_status
            ),
            home_score = COALESCE(
                excluded.home_score, current_game_state.home_score
            ),
            away_score = COALESCE(
                excluded.away_score, current_game_state.away_score
            ),
            home_moneyline = COALESCE(
                excluded.home_moneyline, current_game_state.home_moneyline
            ),
            away_moneyline = COALESCE(
                excluded.away_moneyline, current_game_state.away_moneyline
            ),
            total = COALESCE(excluded.total, current_game_state.total),
            observed_at = excluded.observed_at,
            refresh_id = excluded.refresh_id,
            is_legacy = excluded.is_legacy
        """,
        (
            event.event_id,
            event.season_year,
            event.week,
            event.home_team,
            event.away_team,
            event.short_name,
            event.spread,
            _event_timestamp(event, "kickoff_at"),
            _event_value(event, "game_status"),
            _event_value(event, "home_score"),
            _event_value(event, "away_score"),
            _event_value(event, "home_moneyline"),
            _event_value(event, "away_moneyline"),
            _event_value(event, "total"),
            observed,
            refresh_id,
            is_legacy,
        ),
    )
    return True


def save_current_state(
    data: Iterable[EventOdds],
    observed_at: Timestamp | None = None,
    refresh_id: str | None = None,
    db_name: str | Path = DEFAULT_DB_NAME,
) -> None:
    events = list(data)
    with _connection(db_name) as connection:
        _setup_database(connection)
        for event in events:
            _upsert_current_event(connection, event, observed_at, refresh_id)
        if observed_at is not None:
            seasons: dict[int, set[int]] = {}
            for event in events:
                seasons.setdefault(event.season_year, set()).add(event.event_id)
            for season_year, event_ids in seasons.items():
                event_ids = sorted(event_ids)
                placeholders = ", ".join("?" for _ in event_ids)
                connection.execute(
                    f"DELETE FROM current_game_state "
                    f"WHERE season_year = ? AND event_id NOT IN ({placeholders})",
                    (season_year, *event_ids),
                )


def upsert_current_game(
    event: EventOdds,
    observed_at: Timestamp | None = None,
    refresh_id: str | None = None,
    db_name: str | Path = DEFAULT_DB_NAME,
) -> bool:
    with _connection(db_name) as connection:
        _setup_database(connection)
        return _upsert_current_event(connection, event, observed_at, refresh_id)


def fetch_current_state(
    year: int, db_name: str | Path = DEFAULT_DB_NAME
) -> list[EventOdds]:
    with _connection(db_name) as connection:
        _setup_database(connection)
        rows = connection.execute(
            """
            SELECT event_id, season_year, week, short_name, spread
            FROM current_game_state
            WHERE season_year = ?
            ORDER BY event_id
            """,
            (year,),
        ).fetchall()
    return _events_from_rows(rows)


def _finished_status(status: str) -> bool:
    normalized = status.strip().lower()
    return normalized.startswith("final") or normalized in {
        "complete",
        "completed",
        "postponed",
        "cancelled",
        "canceled",
    }


def apply_refresh(
    season_year: int,
    events: Iterable[EventOdds],
    observed_at: Timestamp,
    status: str = "complete",
    error: str | None = None,
    db_name: str | Path = DEFAULT_DB_NAME,
    *,
    requested_weeks: Iterable[int] | None = None,
    successful_weeks: Iterable[int] | None = None,
    failed_weeks: Iterable[int] = (),
    source_urls: Iterable[str] = (),
    raw_failures: Iterable[Mapping[str, object]] = (),
    started_at: Timestamp | None = None,
    finished_at: Timestamp | None = None,
) -> dict[str, object]:
    all_events = list(events)
    sources = list(source_urls)
    requested = list(
        requested_weeks
        if requested_weeks is not None
        else sorted({event.week for event in all_events})
    )
    failed = sorted(set(failed_weeks))
    successful = sorted(
        set(
            successful_weeks
            if successful_weeks is not None
            else (event.week for event in all_events)
        )
        - set(failed)
    )
    refresh_status = status.lower()
    if failed and refresh_status == "complete":
        refresh_status = "partial" if successful else "failed"
    if refresh_status == "failed":
        successful = []
        process_events: list[EventOdds] = []
    else:
        process_events = [event for event in all_events if event.week not in failed]
    if refresh_status not in {"complete", "partial", "failed"}:
        raise ValueError(f"Invalid refresh status: {status}")
    if error is None and failed:
        error = "failed weeks: " + ", ".join(str(week) for week in failed)
    run_id = create_refresh_run(
        season_year,
        requested,
        started_at or observed_at,
        db_name=db_name,
        source_urls=sources,
    )
    current_updates = 0
    closing_updates = 0
    result_updates = 0
    try:
        with _connection(db_name) as connection:
            _setup_database(connection)
            for event in process_events:
                if _upsert_current_event(connection, event, observed_at, run_id):
                    current_updates += 1

        for event in process_events:
            kickoff = _event_timestamp(event, "kickoff_at")
            if (
                event.spread is not None
                and kickoff is not None
                and update_closing_line(
                    event.event_id,
                    event.spread,
                    observed_at,
                    kickoff,
                    db_name=db_name,
                    season_year=event.season_year,
                    week=event.week,
                    refresh_id=run_id,
                )
            ):
                closing_updates += 1

            game_status = _event_value(event, "game_status")
            if not isinstance(game_status, str) or not game_status.strip():
                continue
            home_score = _event_value(event, "home_score")
            away_score = _event_value(event, "away_score")
            if (
                _finished_status(game_status)
                or home_score is not None
                or away_score is not None
            ) and upsert_game_result(
                event.event_id,
                game_status,
                home_score if isinstance(home_score, int) else None,
                away_score if isinstance(away_score, int) else None,
                observed_at,
                db_name=db_name,
                season_year=event.season_year,
                week=event.week,
            ):
                result_updates += 1

        with _connection(db_name) as connection:
            _setup_database(connection)
            for failure in raw_failures:
                week = failure.get("week")
                source_url = failure.get("source_url")
                payload = failure.get("payload")
                failure_error = failure.get("error")
                if (
                    isinstance(week, int)
                    and isinstance(source_url, str)
                    and isinstance(payload, bytes)
                ):
                    connection.execute(
                        """
                        INSERT OR REPLACE INTO refresh_payloads
                            (refresh_id, week, source_url, payload, error)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            run_id,
                            week,
                            source_url,
                            payload,
                            str(failure_error or "parser failure")[:1000],
                        ),
                    )

        finished = finished_at or observed_at
        finalize_refresh_run(
            run_id,
            finished,
            refresh_status,
            error,
            db_name,
        )
    except Exception as exception:
        finalize_refresh_run(
            run_id,
            finished_at or observed_at,
            "failed",
            str(exception),
            db_name,
        )
        raise

    return {
        "refresh_id": run_id,
        "status": refresh_status,
        "requested_weeks": requested,
        "successful_weeks": successful,
        "failed_weeks": failed,
        "successful_count": len(successful),
        "failed_count": len(failed),
        "parsed_count": len(process_events),
        "current_state_updates": current_updates,
        "closing_line_updates": closing_updates,
        "final_result_updates": result_updates,
        "source_urls": sources,
    }


def freeze_decision_snapshot(
    season_year: int,
    survivor_week: int,
    decision_at: Timestamp,
    trigger: str = "pick",
    db_name: str | Path = DEFAULT_DB_NAME,
) -> int:
    with _connection(db_name) as connection:
        _setup_database(connection)
        existing = connection.execute(
            """
            SELECT snapshot_id
            FROM decision_snapshots
            WHERE season_year = ? AND survivor_week = ?
            """,
            (season_year, survivor_week),
        ).fetchone()
        if existing is not None:
            return existing[0]

        connection.execute(
            """
            INSERT INTO decision_snapshots
                (season_year, survivor_week, decision_at, trigger)
            VALUES (?, ?, ?, ?)
            """,
            (season_year, survivor_week, _utc_timestamp(decision_at), trigger),
        )
        snapshot_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
        rows = connection.execute(
            """
            SELECT event_id, season_year, week, home_team, away_team, short_name,
                   spread, observed_at, refresh_id
            FROM current_game_state
            WHERE season_year = ? AND is_legacy = 0
            ORDER BY event_id
            """,
            (season_year,),
        ).fetchall()
        connection.executemany(
            """
            INSERT INTO decision_snapshot_games (
                snapshot_id, event_id, season_year, week, home_team, away_team,
                short_name, spread, observed_at, refresh_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ((snapshot_id, *row) for row in rows),
        )
        return snapshot_id


def find_decision_snapshot(
    season_year: int,
    survivor_week: int,
    db_name: str | Path = DEFAULT_DB_NAME,
) -> int | None:
    with _connection(db_name) as connection:
        _setup_database(connection)
        row = connection.execute(
            """
            SELECT snapshot_id
            FROM decision_snapshots
            WHERE season_year = ? AND survivor_week = ?
            """,
            (season_year, survivor_week),
        ).fetchone()
    return None if row is None else row[0]


def fetch_snapshot_events(
    snapshot_id: int, db_name: str | Path = DEFAULT_DB_NAME
) -> list[EventOdds]:
    with _connection(db_name) as connection:
        _setup_database(connection)
        rows = connection.execute(
            """
            SELECT event_id, season_year, week, short_name, spread
            FROM decision_snapshot_games
            WHERE snapshot_id = ?
            ORDER BY event_id
            """,
            (snapshot_id,),
        ).fetchall()
    return _events_from_rows(rows)


def fetch_decision_snapshot(
    season_year: int,
    survivor_week: int,
    db_name: str | Path = DEFAULT_DB_NAME,
) -> list[EventOdds]:
    snapshot_id = find_decision_snapshot(season_year, survivor_week, db_name)
    if snapshot_id is None:
        return []
    return fetch_snapshot_events(snapshot_id, db_name)


def update_closing_line(
    event_id: int,
    spread: float,
    observed_at: Timestamp,
    kickoff_at: Timestamp,
    db_name: str | Path = DEFAULT_DB_NAME,
    season_year: int | None = None,
    week: int | None = None,
    refresh_id: str | None = None,
) -> bool:
    observed = _utc_timestamp(observed_at)
    kickoff = _utc_timestamp(kickoff_at)
    if observed is None or kickoff is None:
        return False

    with _connection(db_name) as connection:
        _setup_database(connection)
        current = connection.execute(
            "SELECT kickoff_at FROM current_game_state WHERE event_id = ?",
            (event_id,),
        ).fetchone()
        if current is None or current[0] is None:
            return False
        try:
            actual_kickoff = _utc_timestamp(current[0])
        except (TypeError, ValueError):
            return False
        if actual_kickoff is None or kickoff != actual_kickoff:
            return False
        if _timestamp_key(observed) >= _timestamp_key(actual_kickoff):
            return False

        previous = connection.execute(
            "SELECT observed_at FROM closing_lines WHERE event_id = ?",
            (event_id,),
        ).fetchone()
        if previous is not None and _timestamp_key(observed) <= _timestamp_key(
            previous[0]
        ):
            return False
        connection.execute(
            """
            INSERT INTO closing_lines (
                event_id, season_year, week, spread, observed_at, kickoff_at, refresh_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(event_id) DO UPDATE SET
                season_year = excluded.season_year,
                week = excluded.week,
                spread = excluded.spread,
                observed_at = excluded.observed_at,
                kickoff_at = excluded.kickoff_at,
                refresh_id = excluded.refresh_id
            """,
            (event_id, season_year, week, spread, observed, actual_kickoff, refresh_id),
        )
    return True


def fetch_closing_line(
    event_id: int, db_name: str | Path = DEFAULT_DB_NAME
) -> dict[str, object] | None:
    with _connection(db_name) as connection:
        _setup_database(connection)
        row = connection.execute(
            """
            SELECT event_id, season_year, week, spread, observed_at,
                   kickoff_at, refresh_id
            FROM closing_lines
            WHERE event_id = ?
            """,
            (event_id,),
        ).fetchone()
    if row is None:
        return None
    keys = (
        "event_id",
        "season_year",
        "week",
        "spread",
        "observed_at",
        "kickoff_at",
        "refresh_id",
    )
    return dict(zip(keys, row, strict=True))


def upsert_game_result(
    event_id: int,
    status: str,
    home_score: int | None,
    away_score: int | None,
    observed_at: Timestamp,
    corrected_at: Timestamp | None = None,
    db_name: str | Path = DEFAULT_DB_NAME,
    season_year: int | None = None,
    week: int | None = None,
) -> bool:
    observed = _utc_timestamp(observed_at)
    corrected = _utc_timestamp(corrected_at)
    if observed is None:
        raise ValueError("observed_at is required")

    with _connection(db_name) as connection:
        _setup_database(connection)
        previous = connection.execute(
            """
            SELECT season_year, week, status, home_score, away_score,
                   observed_at, corrected_at
            FROM game_results
            WHERE event_id = ?
            """,
            (event_id,),
        ).fetchone()
        if previous is not None and _timestamp_key(observed) < _timestamp_key(
            previous[5]
        ):
            return False
        if previous is not None and corrected is None:
            changed = (
                status != previous[2]
                or home_score != previous[3]
                or away_score != previous[4]
            )
            corrected = observed if changed else previous[6]
        connection.execute(
            """
            INSERT INTO game_results (
                event_id, season_year, week, status, home_score, away_score,
                observed_at, corrected_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(event_id) DO UPDATE SET
                season_year = excluded.season_year,
                week = excluded.week,
                status = excluded.status,
                home_score = excluded.home_score,
                away_score = excluded.away_score,
                observed_at = excluded.observed_at,
                corrected_at = excluded.corrected_at
            """,
            (
                event_id,
                season_year,
                week,
                status,
                home_score,
                away_score,
                observed,
                corrected,
            ),
        )
    return True


def fetch_game_result(
    event_id: int, db_name: str | Path = DEFAULT_DB_NAME
) -> dict[str, object] | None:
    with _connection(db_name) as connection:
        _setup_database(connection)
        row = connection.execute(
            """
            SELECT event_id, season_year, week, status, home_score, away_score,
                   observed_at, corrected_at
            FROM game_results
            WHERE event_id = ?
            """,
            (event_id,),
        ).fetchone()
    if row is None:
        return None
    keys = (
        "event_id",
        "season_year",
        "week",
        "status",
        "home_score",
        "away_score",
        "observed_at",
        "corrected_at",
    )
    return dict(zip(keys, row, strict=True))


def _create_decision_snapshot(
    connection: sqlite3.Connection,
    season_year: int,
    survivor_week: int,
    decision_at: Timestamp,
    trigger: str,
) -> int:
    connection.execute(
        """
        INSERT INTO decision_snapshots
            (season_year, survivor_week, decision_at, trigger)
        VALUES (?, ?, ?, ?)
        """,
        (season_year, survivor_week, _utc_timestamp(decision_at), trigger),
    )
    snapshot_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
    rows = connection.execute(
        """
        SELECT event_id, season_year, week, home_team, away_team,
               short_name, spread, observed_at, refresh_id
        FROM current_game_state
        WHERE season_year = ?
        ORDER BY event_id
        """,
        (season_year,),
    ).fetchall()
    connection.executemany(
        """
        INSERT INTO decision_snapshot_games (
            snapshot_id, event_id, season_year, week, home_team, away_team,
            short_name, spread, observed_at, refresh_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ((snapshot_id, *row) for row in rows),
    )
    return snapshot_id


def append_pick_event(
    season_year: int,
    week: int,
    action: str,
    pick: Pick | None,
    recorded_at: Timestamp,
    decision_snapshot_id: int | None = None,
    optimization_run_id: int | None = None,
    db_name: str | Path = DEFAULT_DB_NAME,
    snapshot_id: int | None = None,
) -> int:
    if action not in {"set", "clear"}:
        raise ValueError(f"Invalid pick action: {action}")
    if action == "set" and pick is None:
        raise ValueError("set pick events require a pick")
    if snapshot_id is not None:
        if decision_snapshot_id is not None and decision_snapshot_id != snapshot_id:
            raise ValueError("Conflicting decision snapshot IDs")
        decision_snapshot_id = snapshot_id

    team = None if pick is None else pick.team
    spread = None if pick is None else pick.spread
    with _connection(db_name) as connection:
        _setup_database(connection)
        if decision_snapshot_id is None:
            existing = connection.execute(
                """
                SELECT snapshot_id
                FROM decision_snapshots
                WHERE season_year = ? AND survivor_week = ?
                """,
                (season_year, week),
            ).fetchone()
            decision_snapshot_id = (
                _create_decision_snapshot(
                    connection, season_year, week, recorded_at, "pick"
                )
                if existing is None
                else existing[0]
            )
        connection.execute(
            """
            INSERT INTO pick_events (
                season_year, week, action, team, spread, recorded_at,
                decision_snapshot_id, optimization_run_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                season_year,
                week,
                action,
                team,
                spread,
                _utc_timestamp(recorded_at),
                decision_snapshot_id,
                optimization_run_id,
            ),
        )
        return connection.execute("SELECT last_insert_rowid()").fetchone()[0]


def migrate_legacy_pick_events(
    season_year: int,
    picks: Iterable[Pick],
    recorded_at: Timestamp,
    db_name: str | Path = DEFAULT_DB_NAME,
) -> int:
    if type(season_year) is not int or not 2020 <= season_year <= 2030:
        raise ValueError("Season year must be between 2020 and 2030")
    legacy_picks = list(picks)
    if not legacy_picks:
        return 0
    if any(not isinstance(pick, Pick) for pick in legacy_picks):
        raise TypeError("legacy picks must be Pick values")

    weeks = [pick.week for pick in legacy_picks]
    if any(type(week) is not int or not 1 <= week <= 18 for week in weeks):
        raise ValueError("Legacy pick weeks must be between 1 and 18")
    if len(weeks) != len(set(weeks)):
        raise ValueError("Each week can only have one legacy pick")
    teams = [pick.team for pick in legacy_picks]
    if any(not isinstance(team, str) or not team for team in teams):
        raise ValueError("Legacy pick teams must be non-empty strings")
    if len(teams) != len(set(teams)):
        raise ValueError("Each team can only have one legacy pick")

    recorded = _utc_timestamp(recorded_at)
    if recorded is None:
        raise ValueError("recorded_at is required")

    imported = 0
    with _connection(db_name) as connection:
        _setup_database(connection)
        for pick in legacy_picks:
            existing = connection.execute(
                """
                SELECT snapshot_id, trigger
                FROM decision_snapshots
                WHERE season_year = ? AND survivor_week = ?
                """,
                (season_year, pick.week),
            ).fetchone()
            if existing is not None:
                snapshot_id, trigger = existing
                if trigger != LEGACY_SNAPSHOT_TRIGGER:
                    raise ValueError(
                        f"Cannot migrate week {pick.week}: "
                        "decision snapshot already exists"
                    )
                previous = connection.execute(
                    """
                    SELECT action, team, spread
                    FROM pick_events
                    WHERE season_year = ? AND week = ?
                      AND decision_snapshot_id = ?
                    ORDER BY pick_event_id DESC
                    LIMIT 1
                    """,
                    (season_year, pick.week, snapshot_id),
                ).fetchone()
                if previous != ("set", pick.team, pick.spread):
                    raise ValueError(
                        f"Legacy migration already contains a different pick "
                        f"for week {pick.week}"
                    )
                continue

            snapshot_id = _create_decision_snapshot(
                connection,
                season_year,
                pick.week,
                recorded,
                LEGACY_SNAPSHOT_TRIGGER,
            )
            connection.execute(
                """
                INSERT INTO pick_events (
                    season_year, week, action, team, spread, recorded_at,
                    decision_snapshot_id, optimization_run_id
                ) VALUES (?, ?, 'set', ?, ?, ?, ?, NULL)
                """,
                (
                    season_year,
                    pick.week,
                    pick.team,
                    pick.spread,
                    recorded,
                    snapshot_id,
                ),
            )
            imported += 1
    return imported


def fetch_current_picks(
    season_year: int, db_name: str | Path = DEFAULT_DB_NAME
) -> list[Pick]:
    with _connection(db_name) as connection:
        _setup_database(connection)
        rows = connection.execute(
            """
            WITH latest AS (
                SELECT week, MAX(pick_event_id) AS max_id
                FROM pick_events
                WHERE season_year = ?
                GROUP BY week
            )
            SELECT p.team, p.week, p.spread
            FROM pick_events p
            INNER JOIN latest l ON p.week = l.week AND p.pick_event_id = l.max_id
            WHERE p.season_year = ? AND p.action = 'set'
            ORDER BY p.week
            """,
            (season_year, season_year),
        ).fetchall()
    return [Pick(team=row[0], week=row[1], spread=row[2]) for row in rows]


def clear_all_pick_events(
    season_year: int,
    recorded_at: Timestamp,
    db_name: str | Path = DEFAULT_DB_NAME,
) -> None:
    current_picks = fetch_current_picks(season_year, db_name)
    with _connection(db_name) as connection:
        _setup_database(connection)
        for pick in current_picks:
            connection.execute(
                """
                INSERT INTO pick_events (
                    season_year, week, action, team, spread, recorded_at,
                    decision_snapshot_id, optimization_run_id
                ) VALUES (?, ?, 'clear', NULL, NULL, ?, NULL, NULL)
                """,
                (season_year, pick.week, _utc_timestamp(recorded_at)),
            )


def _pick_to_json(pick: Pick) -> dict[str, object]:
    return {"team": pick.team, "week": pick.week, "spread": pick.spread}


def save_optimization_run(
    season_year: int,
    algorithm: str,
    split_week: int,
    current_week: int,
    parameters: Mapping[str, object],
    code_revision: str,
    generated_at: Timestamp,
    decision_snapshot_id: int | None,
    recommendations: Iterable[Pick],
    db_name: str | Path = DEFAULT_DB_NAME,
    source_hash: str | None = None,
) -> int:
    encoded_parameters = json.dumps(parameters, sort_keys=True, separators=(",", ":"))
    encoded_recommendations = json.dumps(
        [_pick_to_json(pick) for pick in recommendations],
        sort_keys=True,
        separators=(",", ":"),
    )
    with _connection(db_name) as connection:
        _setup_database(connection)
        connection.execute(
            """
            INSERT INTO optimization_runs (
                season_year, algorithm, split_week, current_week, parameters,
                code_revision, source_hash, generated_at, decision_snapshot_id,
                recommendations
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                season_year,
                algorithm,
                split_week,
                current_week,
                encoded_parameters,
                code_revision,
                source_hash,
                _utc_timestamp(generated_at),
                decision_snapshot_id,
                encoded_recommendations,
            ),
        )
        return connection.execute("SELECT last_insert_rowid()").fetchone()[0]


def fetch_optimization_run(
    run_id: int, db_name: str | Path = DEFAULT_DB_NAME
) -> dict[str, object] | None:
    with _connection(db_name) as connection:
        _setup_database(connection)
        row = connection.execute(
            """
            SELECT run_id, season_year, algorithm, split_week, current_week,
                   parameters, code_revision, source_hash, generated_at,
                   decision_snapshot_id, recommendations
            FROM optimization_runs
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
    if row is None:
        return None
    (
        stored_run_id,
        season_year,
        algorithm,
        split_week,
        current_week,
        parameters,
        code_revision,
        source_hash,
        generated_at,
        decision_snapshot_id,
        recommendations,
    ) = row
    return {
        "run_id": stored_run_id,
        "season_year": season_year,
        "algorithm": algorithm,
        "split_week": split_week,
        "current_week": current_week,
        "parameters": json.loads(parameters),
        "code_revision": code_revision,
        "source_hash": source_hash,
        "generated_at": generated_at,
        "decision_snapshot_id": decision_snapshot_id,
        "recommendations": [
            Pick(item["team"], item["week"], item.get("spread"))
            for item in json.loads(recommendations)
        ],
    }


def find_latest_optimization_run(
    season_year: int,
    week: int,
    algorithm: str,
    db_name: str | Path = DEFAULT_DB_NAME,
) -> dict[str, object] | None:
    """Find the most recent optimization run for a season/week/algorithm."""
    with _connection(db_name) as connection:
        _setup_database(connection)
        row = connection.execute(
            """
            SELECT run_id, season_year, algorithm, split_week, current_week,
                   parameters, code_revision, source_hash, generated_at,
                   decision_snapshot_id, recommendations
            FROM optimization_runs
            WHERE season_year = ? AND current_week = ? AND algorithm = ?
            ORDER BY generated_at DESC
            LIMIT 1
            """,
            (season_year, week, algorithm),
        ).fetchone()
    if row is None:
        return None
    (
        stored_run_id,
        stored_season_year,
        stored_algorithm,
        split_week,
        current_week,
        parameters,
        code_revision,
        source_hash,
        generated_at,
        decision_snapshot_id,
        recommendations,
    ) = row
    return {
        "run_id": stored_run_id,
        "season_year": stored_season_year,
        "algorithm": stored_algorithm,
        "split_week": split_week,
        "current_week": current_week,
        "parameters": json.loads(parameters),
        "code_revision": code_revision,
        "source_hash": source_hash,
        "generated_at": generated_at,
        "decision_snapshot_id": decision_snapshot_id,
        "recommendations": [
            Pick(item["team"], item["week"], item.get("spread"))
            for item in json.loads(recommendations)
        ],
    }


def backup_database(
    source: str | Path = DEFAULT_DB_NAME,
    destination: str | Path = "odds_data_backup.db",
) -> None:
    """Backup SQLite database using Connection.backup()."""
    with _connection(source) as src, _connection(destination) as dst:
        src.backup(dst)
