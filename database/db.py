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
        if "eliminado" not in columns:
            connection.execute("ALTER TABLE mediciones ADD COLUMN eliminado INTEGER NOT NULL DEFAULT 0 CHECK(eliminado IN (0, 1))")
        device_columns = {row["name"] for row in connection.execute("PRAGMA table_info(dispositivos)")}
        if "tag" not in device_columns:
            connection.execute("ALTER TABLE dispositivos ADD COLUMN tag TEXT")
        if "numero" not in device_columns:
            connection.execute("ALTER TABLE dispositivos ADD COLUMN numero TEXT")
        track_columns = {row["name"] for row in connection.execute("PRAGMA table_info(tracks_vt)")}
        if "track_key" not in track_columns:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute("""CREATE TABLE tracks_vt_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dispositivo_id INTEGER NOT NULL REFERENCES dispositivos(id) ON DELETE CASCADE,
                campana_id INTEGER NOT NULL REFERENCES campanas(id) ON DELETE CASCADE,
                archivo TEXT NOT NULL,
                track_key TEXT NOT NULL,
                canal TEXT NOT NULL,
                fecha TEXT,
                descripcion TEXT,
                source_sheet TEXT,
                UNIQUE(dispositivo_id, track_key)
            )""")
            connection.execute("""INSERT INTO tracks_vt_new
                (id, dispositivo_id, campana_id, archivo, track_key, canal, fecha, descripcion, source_sheet)
                SELECT id, dispositivo_id, campana_id, archivo, 'legacy-' || id, canal, fecha, descripcion, source_sheet
                FROM tracks_vt""")
            connection.execute("DROP TABLE tracks_vt")
            connection.execute("ALTER TABLE tracks_vt_new RENAME TO tracks_vt")
            connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_tracks_device_key ON tracks_vt(dispositivo_id, track_key)")
