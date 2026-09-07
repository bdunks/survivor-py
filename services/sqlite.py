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
            started_at TEXT NOT NULL,
            finished_at TEXT,
            status TEXT NOT NULL,
            error TEXT
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
            observed_at TEXT,
            refresh_id TEXT,
            is_legacy INTEGER NOT NULL DEFAULT 0 CHECK (is_legacy IN (0, 1))
        )
        """
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
    with _connection(db_name) as connection:
        _setup_database(connection)
        rows = connection.execute(
            """
            SELECT event_id, season_year, week, short_name, spread
            FROM averaged_odds
            WHERE season_year = ?
            ORDER BY event_id
            """,
            (year,),
        ).fetchall()

    return _events_from_rows(rows)


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
) -> str:
    run_id = refresh_id or uuid.uuid4().hex
    requested = json.dumps(list(requested_weeks), separators=(",", ":"))
    with _connection(db_name) as connection:
        _setup_database(connection)
        connection.execute(
            """
            INSERT INTO refresh_runs
                (refresh_id, season_year, requested_weeks, started_at, status)
            VALUES (?, ?, ?, ?, 'running')
            """,
            (run_id, season_year, requested, _utc_timestamp(started_at)),
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
            (_utc_timestamp(finished_at), status, error, refresh_id),
        )
        if cursor.rowcount != 1:
            raise ValueError(f"Unknown refresh run: {refresh_id}")


start_refresh_run = create_refresh_run
finish_refresh_run = finalize_refresh_run


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
            observed_at, refresh_id, is_legacy
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(event_id) DO UPDATE SET
            season_year = excluded.season_year,
            week = excluded.week,
            home_team = excluded.home_team,
            away_team = excluded.away_team,
            short_name = excluded.short_name,
            spread = excluded.spread,
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
        seasons: dict[int, set[int]] = {}
        for event in events:
            seasons.setdefault(event.season_year, set()).add(event.event_id)
            _upsert_current_event(connection, event, observed_at, refresh_id)
        if observed_at is not None:
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
    if (
        observed is None
        or kickoff is None
        or _timestamp_key(observed) >= _timestamp_key(kickoff)
    ):
        return False

    with _connection(db_name) as connection:
        _setup_database(connection)
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
            (event_id, season_year, week, spread, observed, kickoff, refresh_id),
        )
    return True


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
            corrected = previous[6]
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
