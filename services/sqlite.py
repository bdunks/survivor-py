import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path

from models import EventOdds

DEFAULT_DB_NAME = "odds_data.db"


@contextmanager
def _connection(db_name: str | Path = DEFAULT_DB_NAME) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(db_name)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def _setup_database(connection: sqlite3.Connection) -> None:
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
            """,
            (year,),
        ).fetchall()

    events = []
    for event_id, season_year, week, short_name, spread in rows:
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
