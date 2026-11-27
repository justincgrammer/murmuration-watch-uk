import os
import sqlite3
from pathlib import Path

DB_PATH = Path(os.getenv("DB_PATH", str(Path(__file__).parent / "murmurations.db")))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_database() -> None:
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS counties (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                slug TEXT NOT NULL UNIQUE,
                region TEXT NOT NULL,
                center_lat REAL NOT NULL,
                center_lng REAL NOT NULL,
                default_zoom INTEGER NOT NULL DEFAULT 9,
                is_active INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS roost_sites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                county_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                parking_lat REAL,
                parking_lng REAL,
                parking_access TEXT,
                habitat_type TEXT,
                best_months TEXT DEFAULT 'Oct-Feb',
                reliability TEXT DEFAULT 'High',
                status TEXT NOT NULL DEFAULT 'active',
                notes TEXT,
                UNIQUE(county_id, name),
                FOREIGN KEY (county_id) REFERENCES counties(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS sightings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                roost_id INTEGER,
                county_id INTEGER NOT NULL,
                custom_location_name TEXT,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                observed_date TEXT NOT NULL,
                observed_time TEXT,
                flock_size TEXT,
                display_quality INTEGER CHECK(display_quality BETWEEN 1 AND 5),
                weather_summary TEXT,
                wind_speed_mph REAL,
                behaviour_notes TEXT,
                photo_url TEXT,
                source TEXT NOT NULL DEFAULT 'user',
                source_url TEXT,
                status TEXT NOT NULL DEFAULT 'published',
                client_hash TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (roost_id) REFERENCES roost_sites(id) ON DELETE SET NULL,
                FOREIGN KEY (county_id) REFERENCES counties(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS scraper_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ran_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                county_slug TEXT,
                source_name TEXT NOT NULL,
                records_found INTEGER NOT NULL DEFAULT 0,
                records_inserted INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'success',
                error_message TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_counties_region ON counties(region, is_active);
            CREATE INDEX IF NOT EXISTS idx_roosts_county ON roost_sites(county_id, status);
            CREATE INDEX IF NOT EXISTS idx_sightings_date ON sightings(observed_date DESC);
            CREATE INDEX IF NOT EXISTS idx_sightings_county ON sightings(county_id, status);
            CREATE INDEX IF NOT EXISTS idx_sightings_hash ON sightings(client_hash, observed_date);
            """
        )
    print(f"Database initialised cleanly at: {DB_PATH}")


if __name__ == "__main__":
    init_database()