import sqlite3
from pathlib import Path

from config import DATABASE_PATH


def get_connection(path: Path | str = DATABASE_PATH) -> sqlite3.Connection:
    connection = sqlite3.connect(path, check_same_thread=False, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(path: Path | str = DATABASE_PATH) -> None:
    with get_connection(path) as connection:
        schema_path = Path(__file__).with_name("schema.sql")
        connection.executescript(schema_path.read_text(encoding="utf-8"))
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(mediciones)")}
        if "measurement_hash" not in columns:
            connection.execute("ALTER TABLE mediciones ADD COLUMN measurement_hash TEXT")
            connection.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_mediciones_hash ON mediciones(measurement_hash) "
                "WHERE measurement_hash IS NOT NULL"
            )
        device_columns = {row["name"] for row in connection.execute("PRAGMA table_info(dispositivos)")}
        if "tag" not in device_columns:
            connection.execute("ALTER TABLE dispositivos ADD COLUMN tag TEXT")
        if "numero" not in device_columns:
            connection.execute("ALTER TABLE dispositivos ADD COLUMN numero TEXT")
        track_columns = {row["name"] for row in connection.execute("PRAGMA table_info(tracks_vt)")}
        if "track_key" not in track_columns:
            connection.execute("ALTER TABLE tracks_vt ADD COLUMN track_key TEXT")
            connection.execute("UPDATE tracks_vt SET track_key = 'legacy-' || id WHERE track_key IS NULL")
        connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_tracks_device_key ON tracks_vt(dispositivo_id, track_key)")
