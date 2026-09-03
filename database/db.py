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
