import sqlite3
from typing import List, Tuple

from models import EventOdds


class DatabaseService:
    def __init__(self, db_name="odds_data.db"):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.setup_database()

    def setup_database(self):
        """Create the necessary tables if they don't exist."""
        self.cursor.execute(
            """
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
        """
        )

        # Create a trigger to update the updated_at column whenever a row is updated
        self.cursor.execute(
            """
        CREATE TRIGGER IF NOT EXISTS update_averaged_odds
        AFTER UPDATE ON averaged_odds
        FOR EACH ROW
        BEGIN
            UPDATE averaged_odds SET updated_at = CURRENT_TIMESTAMP WHERE event_id = OLD.event_id;
        END
        """
        )

        self.conn.commit()

    def insert_or_replace_data(
        self, table_name: str, columns: List[str], data: List[Tuple]
    ):
        """Insert or replace data into a given table."""
        placeholders = ", ".join(["?"] * len(columns))
        columns_str = ", ".join(columns)
        sql = f"INSERT OR REPLACE INTO {table_name} ({columns_str}) VALUES ({placeholders})"
        self.cursor.executemany(sql, data)
        self.conn.commit()

    def save_odds_data(self, data):
        """Insert the averaged odds data into the database."""
        columns = [
            "event_id",
            "season_year",
            "week",
            "home_team",
            "away_team",
            "short_name",
            "spread",
        ]
        formatted_data = [
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
        ]
        self.insert_or_replace_data("averaged_odds", columns, formatted_data)

    def fetch_odds_data(self, year: int) -> List[EventOdds]:
        """Fetch the averaged odds data from the database for a specific year."""
        self.cursor.execute(
            "SELECT * FROM averaged_odds WHERE season_year = ?", (year,)
        )
        rows = self.cursor.fetchall()
        event_odds_list = [
            EventOdds(
                event_id=row[0],
                season_year=row[1],
                week=row[2],
                short_name=row[5],
                spread=row[6],
            )
            for row in rows
        ]
        return event_odds_list

    def close(self):
        """Close the database connection."""
        self.conn.close()
