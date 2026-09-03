from __future__ import annotations

import sqlite3
from typing import Any

import pandas as pd


class Repository:
    """Persistence boundary; UI and services do not depend on SQL details."""

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def add_device(self, name: str) -> int:
        self.connection.execute("INSERT OR IGNORE INTO dispositivos(nombre) VALUES (?)", (name,))
        row = self.connection.execute("SELECT id FROM dispositivos WHERE nombre = ?", (name,)).fetchone()
        return int(row["id"])

    def add_campaign(self, device_id: int, number: str) -> int:
        self.connection.execute(
            "INSERT OR IGNORE INTO campanas(dispositivo_id, numero) VALUES (?, ?)",
            (device_id, str(number)),
        )
        row = self.connection.execute(
            "SELECT id FROM campanas WHERE dispositivo_id = ? AND numero = ?", (device_id, str(number))
        ).fetchone()
        return int(row["id"])

    def add_measurement(self, values: dict[str, Any]) -> tuple[int, bool]:
        existing = self.connection.execute(
            "SELECT id FROM mediciones WHERE campana_id = ? AND archivo = ?",
            (values["campana_id"], values["archivo"]),
        ).fetchone()
        if existing:
            return int(existing["id"]), False
        cursor = self.connection.execute(
            """INSERT INTO mediciones(dispositivo_id, campana_id, archivo, fecha, descripcion, clase, estado)
               VALUES (:dispositivo_id, :campana_id, :archivo, :fecha, :descripcion, :clase, :estado)""",
            values,
        )
        return int(cursor.lastrowid), True

    def add_points(self, measurement_id: int, points: pd.DataFrame) -> int:
        rows = [(measurement_id, float(row.v), float(row.i)) for row in points.itertuples()]
        self.connection.executemany("INSERT INTO puntos(medicion_id, v, i) VALUES (?, ?, ?)", rows)
        return len(rows)

    def save_ztc(self, campaign_id: int, vt: float, current: float) -> None:
        self.connection.execute(
            """INSERT INTO analisis_ztc(campana_id, vt_ztc, i_ztc) VALUES (?, ?, ?)
               ON CONFLICT(campana_id) DO UPDATE SET vt_ztc=excluded.vt_ztc, i_ztc=excluded.i_ztc""",
            (campaign_id, vt, current),
        )

    def _query(self, sql: str, params: tuple = ()) -> pd.DataFrame:
        return pd.read_sql_query(sql, self.connection, params=params)

    def devices(self) -> pd.DataFrame:
        return self._query("SELECT id, nombre FROM dispositivos ORDER BY nombre")

    def campaigns(self, device_id: int | None = None) -> pd.DataFrame:
        sql = "SELECT c.id, c.dispositivo_id, d.nombre AS dispositivo, c.numero FROM campanas c JOIN dispositivos d ON d.id=c.dispositivo_id"
        params: tuple = ()
        if device_id is not None:
            sql += " WHERE c.dispositivo_id = ?"
            params = (device_id,)
        return self._query(sql + " ORDER BY d.nombre, c.numero", params)

    def measurements(self, campaign_id: int | None = None) -> pd.DataFrame:
        sql = """SELECT m.*, d.nombre AS dispositivo, c.numero AS campana
                  FROM mediciones m JOIN dispositivos d ON d.id=m.dispositivo_id
                  JOIN campanas c ON c.id=m.campana_id"""
        params: tuple = ()
        if campaign_id is not None:
            sql += " WHERE m.campana_id = ?"
            params = (campaign_id,)
        return self._query(sql + " ORDER BY m.id", params)

    def points(self, measurement_id: int) -> pd.DataFrame:
        return self._query("SELECT v, i FROM puntos WHERE medicion_id = ? ORDER BY v", (measurement_id,))

    def all_points(self) -> pd.DataFrame:
        return self._query("""SELECT p.*, m.archivo, m.campana_id, d.nombre AS dispositivo, c.numero AS campana
            FROM puntos p JOIN mediciones m ON m.id=p.medicion_id JOIN dispositivos d ON d.id=m.dispositivo_id
            JOIN campanas c ON c.id=m.campana_id ORDER BY p.id""")

    def counts(self) -> dict[str, int]:
        tables = {"dispositivos": "devices", "campanas": "campaigns", "mediciones": "measurements", "puntos": "points", "analisis_ztc": "ztc"}
        return {label: int(self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) for table, label in tables.items()}

    def ztc_results(self) -> pd.DataFrame:
        return self._query("""SELECT d.nombre AS dispositivo, c.id AS campana_id, c.numero AS campana,
            a.vt_ztc, a.i_ztc FROM analisis_ztc a JOIN campanas c ON c.id=a.campana_id
            JOIN dispositivos d ON d.id=c.dispositivo_id ORDER BY d.nombre, c.numero""")
