from __future__ import annotations

import sqlite3
import json
from typing import Any

import pandas as pd


def _device_parts(name: str) -> tuple[str, str, str]:
    import re

    value = str(name or "").strip()
    for match in re.finditer(r"\d+", value):
        tag_value = value[:match.start()]
        if not re.search(r"[A-Za-z]", tag_value):
            continue
        tag = tag_value.upper()
        number = str(int(match.group(0)))
        return tag, number, f"{tag}{number}"
    return value.upper(), "", value.upper()


class Repository:
    """Persistence boundary; UI and services do not depend on SQL details."""

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        self.last_measurement_updated = False

    def add_device(self, name: str, tag: str = "", number: str = "") -> int:
        parsed_tag, parsed_number, parsed_name = _device_parts(name)
        tag = tag or parsed_tag
        number = number or parsed_number
        name = parsed_name
        self.connection.execute("INSERT OR IGNORE INTO dispositivos(nombre, tag, numero) VALUES (?, ?, ?)", (name, tag, number))
        self.connection.execute(
            "UPDATE dispositivos SET tag = COALESCE(NULLIF(tag, ''), ?), numero = COALESCE(NULLIF(numero, ''), ?) WHERE nombre = ?",
            (tag, number, name),
        )
        row = self.connection.execute("SELECT id FROM dispositivos WHERE nombre = ?", (name,)).fetchone()
        return int(row["id"])

    def rename_device(self, device_id: int, name: str) -> None:
        tag, number, canonical = _device_parts(name)
        self.connection.execute("UPDATE dispositivos SET nombre = ?, tag = ?, numero = ? WHERE id = ?", (canonical, tag, number, device_id))

    def rename_campaign(self, campaign_id: int, number: str) -> None:
        self.connection.execute("UPDATE campanas SET numero = ? WHERE id = ?", (number.strip(), campaign_id))

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
        self.last_measurement_updated = False
        existing = None
        if values.get("measurement_hash"):
            existing = self.connection.execute(
                "SELECT id FROM mediciones WHERE measurement_hash = ?",
                (values["measurement_hash"],),
            ).fetchone()
        if not existing:
            existing = self.connection.execute(
                "SELECT id FROM mediciones WHERE dispositivo_id = ? AND archivo = ?",
                (values["dispositivo_id"], values["archivo"]),
            ).fetchone()
        if existing:
            measurement_id = int(existing["id"])
            current = self.connection.execute("SELECT * FROM mediciones WHERE id = ?", (measurement_id,)).fetchone()
            incoming_campaign = self.connection.execute(
                "SELECT numero FROM campanas WHERE id = ?", (values["campana_id"],)
            ).fetchone()
            current_campaign = self.connection.execute(
                "SELECT numero FROM campanas WHERE id = ?", (current["campana_id"],)
            ).fetchone()
            if incoming_campaign and current_campaign and current_campaign["numero"] == "sin asignar" and incoming_campaign["numero"] != "sin asignar":
                self.connection.execute(
                    "UPDATE mediciones SET campana_id = ? WHERE id = ?",
                    (values["campana_id"], measurement_id),
                )
                self.last_measurement_updated = True
            updates = {
                key: value for key, value in values.items()
                if key in {"fecha", "descripcion", "clase", "estado", "measurement_hash"}
                and value not in (None, "", "nan", "NaT")
                and not current[key]
            }
            if updates:
                assignments = ", ".join(f"{key} = :{key}" for key in updates)
                updates["id"] = measurement_id
                self.connection.execute(f"UPDATE mediciones SET {assignments} WHERE id = :id", updates)
                self.last_measurement_updated = True
            return measurement_id, False
        cursor = self.connection.execute(
            """INSERT INTO mediciones(dispositivo_id, campana_id, archivo, fecha, descripcion, clase, estado, measurement_hash)
               VALUES (:dispositivo_id, :campana_id, :archivo, :fecha, :descripcion, :clase, :estado, :measurement_hash)""",
            values,
        )
        return int(cursor.lastrowid), True

    def add_points(self, measurement_id: int, points: pd.DataFrame) -> int:
        rows = {(measurement_id, float(row.v), float(row.i)) for row in points.itertuples()}
        before = self.connection.total_changes
        self.connection.executemany("INSERT OR IGNORE INTO puntos(medicion_id, v, i) VALUES (?, ?, ?)", rows)
        return self.connection.total_changes - before

    def add_track(self, values: dict[str, Any]) -> tuple[int, bool]:
        existing = self.connection.execute(
            "SELECT id FROM tracks_vt WHERE dispositivo_id = ? AND track_key = ?",
            (values["dispositivo_id"], values["track_key"]),
        ).fetchone()
        if existing:
            track_id = int(existing["id"])
            self.connection.execute(
                """UPDATE tracks_vt
                   SET campana_id = COALESCE(NULLIF(:campana_id, ''), campana_id),
                       fecha = COALESCE(NULLIF(:fecha, ''), fecha),
                       descripcion = COALESCE(NULLIF(:descripcion, ''), descripcion),
                       source_sheet = COALESCE(NULLIF(:source_sheet, ''), source_sheet)
                   WHERE id = :id""",
                {**values, "id": track_id},
            )
            return track_id, False
        cursor = self.connection.execute(
                """INSERT INTO tracks_vt(dispositivo_id, campana_id, archivo, track_key, canal, fecha, descripcion, source_sheet)
                    VALUES (:dispositivo_id, :campana_id, :archivo, :track_key, :canal, :fecha, :descripcion, :source_sheet)""",
            values,
        )
        return int(cursor.lastrowid), True

    def add_track_points(self, track_id: int, points: pd.DataFrame) -> int:
        rows = {(track_id, float(row.t), float(row.vt)) for row in points.itertuples()}
        before = self.connection.total_changes
        self.connection.executemany("INSERT OR IGNORE INTO puntos_track_vt(track_id, t, vt) VALUES (?, ?, ?)", rows)
        return self.connection.total_changes - before

    def save_ztc(self, campaign_id: int, vt: float, current: float) -> None:
        self.connection.execute(
            """INSERT INTO analisis_ztc(campana_id, vt_ztc, i_ztc) VALUES (?, ?, ?)
               ON CONFLICT(campana_id) DO UPDATE SET vt_ztc=excluded.vt_ztc, i_ztc=excluded.i_ztc""",
            (campaign_id, vt, current),
        )

    def link_campaigns(self, previous_id: int, next_id: int, order: int | None = 1, reason: str = "") -> None:
        self.connection.execute(
            """INSERT INTO relaciones_campana(anterior_id, siguiente_id, orden, motivo)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(anterior_id, siguiente_id) DO UPDATE SET orden=excluded.orden, motivo=excluded.motivo""",
            (previous_id, next_id, 0 if order is None else order, reason.strip()),
        )

    def campaign_links(self) -> pd.DataFrame:
        return self._query("""SELECT r.*, a.numero AS anterior, b.numero AS siguiente,
            da.nombre AS dispositivo
            FROM relaciones_campana r JOIN campanas a ON a.id=r.anterior_id
            JOIN campanas b ON b.id=r.siguiente_id JOIN dispositivos da ON da.id=a.dispositivo_id
            ORDER BY da.nombre, r.orden, r.id""")

    def delete_campaign_link(self, link_id: int) -> None:
        self.connection.execute("DELETE FROM relaciones_campana WHERE id = ?", (link_id,))

    def _query(self, sql: str, params: tuple = ()) -> pd.DataFrame:
        return pd.read_sql_query(sql, self.connection, params=params)

    def devices(self) -> pd.DataFrame:
        return self._query("SELECT id, nombre, tag, numero FROM dispositivos ORDER BY nombre")

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

    def iv_measurements(self, campaign_id: int | None = None) -> pd.DataFrame:
        sql = """SELECT m.*, d.nombre AS dispositivo, c.numero AS campana
                  FROM mediciones m JOIN dispositivos d ON d.id=m.dispositivo_id
                  JOIN campanas c ON c.id=m.campana_id
                  WHERE EXISTS (SELECT 1 FROM puntos p WHERE p.medicion_id=m.id)"""
        params: tuple = ()
        if campaign_id is not None:
            sql += " AND m.campana_id = ?"
            params = (campaign_id,)
        return self._query(sql + " ORDER BY d.nombre, c.numero, m.archivo", params)

    def measurements_for_devices(self, device_ids: list[int]) -> pd.DataFrame:
        if not device_ids:
            return pd.DataFrame()
        placeholders = ",".join("?" for _ in device_ids)
        return self._query(
            f"""SELECT m.*, d.nombre AS dispositivo, c.numero AS campana
                FROM mediciones m JOIN dispositivos d ON d.id=m.dispositivo_id
                JOIN campanas c ON c.id=m.campana_id
                WHERE m.dispositivo_id IN ({placeholders}) ORDER BY d.nombre, c.numero, m.archivo""",
            tuple(device_ids),
        )

    def measurements_for_campaigns(self, campaign_ids: list[int]) -> pd.DataFrame:
        if not campaign_ids:
            return pd.DataFrame()
        placeholders = ",".join("?" for _ in campaign_ids)
        return self._query(
            f"""SELECT m.*, d.nombre AS dispositivo, c.numero AS campana
                FROM mediciones m JOIN dispositivos d ON d.id=m.dispositivo_id
                JOIN campanas c ON c.id=m.campana_id
                WHERE m.campana_id IN ({placeholders}) ORDER BY d.nombre, c.numero, m.archivo""",
            tuple(campaign_ids),
        )

    def points(self, measurement_id: int) -> pd.DataFrame:
        return self._query("SELECT v, i FROM puntos WHERE medicion_id = ? ORDER BY v", (measurement_id,))

    def all_points(self) -> pd.DataFrame:
        return self._query("""SELECT p.*, m.archivo, m.campana_id, d.nombre AS dispositivo, c.numero AS campana
            FROM puntos p JOIN mediciones m ON m.id=p.medicion_id JOIN dispositivos d ON d.id=m.dispositivo_id
            JOIN campanas c ON c.id=m.campana_id ORDER BY p.id""")

    def tracks(self, device_id: int | None = None, campaign_ids: list[int] | None = None) -> pd.DataFrame:
        sql = """SELECT t.*, t.archivo AS medicion, d.nombre AS dispositivo, c.numero AS campana
                  FROM tracks_vt t JOIN dispositivos d ON d.id=t.dispositivo_id
                  JOIN campanas c ON c.id=t.campana_id"""
        clauses = []
        params: list[Any] = []
        if device_id is not None:
            clauses.append("t.dispositivo_id = ?")
            params.append(device_id)
        if campaign_ids:
            placeholders = ",".join("?" for _ in campaign_ids)
            clauses.append(f"t.campana_id IN ({placeholders})")
            params.extend(campaign_ids)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        return self._query(sql + " ORDER BY d.nombre, c.numero, t.archivo, t.canal", tuple(params))

    def track_points(self, track_id: int) -> pd.DataFrame:
        return self._query("SELECT t, vt FROM puntos_track_vt WHERE track_id = ? ORDER BY t", (track_id,))

    def all_track_points(self) -> pd.DataFrame:
        return self._query("""SELECT p.*, t.archivo, t.canal, t.campana_id, t.source_sheet,
            d.nombre AS dispositivo, c.numero AS campana
            FROM puntos_track_vt p JOIN tracks_vt t ON t.id=p.track_id
            JOIN dispositivos d ON d.id=t.dispositivo_id JOIN campanas c ON c.id=t.campana_id
            ORDER BY p.id""")

    def update_measurement_metadata(self, measurement_id: int, values: dict[str, Any]) -> None:
        allowed = {"dispositivo_id", "campana_id", "archivo", "fecha", "descripcion", "clase", "estado"}
        updates = {key: value for key, value in values.items() if key in allowed}
        if not updates:
            return
        assignments = ", ".join(f"{key} = :{key}" for key in updates)
        updates["id"] = measurement_id
        self.connection.execute(f"UPDATE mediciones SET {assignments} WHERE id = :id", updates)

    def save_workbench_view(self, name: str, configuration: dict[str, Any]) -> None:
        self.connection.execute(
            "INSERT INTO vistas_workbench(nombre, configuracion) VALUES (?, ?) "
            "ON CONFLICT(nombre) DO UPDATE SET configuracion=excluded.configuracion, creada_en=CURRENT_TIMESTAMP",
            (name.strip(), json.dumps(configuration, ensure_ascii=False)),
        )

    def workbench_views(self) -> pd.DataFrame:
        return self._query("SELECT id, nombre, configuracion, creada_en FROM vistas_workbench ORDER BY nombre")

    def delete_workbench_view(self, view_id: int) -> None:
        self.connection.execute("DELETE FROM vistas_workbench WHERE id = ?", (view_id,))

    def add_unclassified(self, values: dict[str, Any]) -> bool:
        cursor = self.connection.execute(
            """INSERT OR IGNORE INTO datos_sin_clasificar
               (archivo_origen, hoja, tipo, filas, columnas, datos_json, contenido_hash)
               VALUES (:archivo_origen, :hoja, :tipo, :filas, :columnas, :datos_json, :contenido_hash)""",
            values,
        )
        return cursor.rowcount > 0

    def unclassified(self) -> pd.DataFrame:
        return self._query("SELECT id, archivo_origen, hoja, tipo, filas, columnas, datos_json, contenido_hash FROM datos_sin_clasificar ORDER BY hoja")

    def save_measurement_group(self, name: str, measurement_ids: list[int], track_ids: list[int]) -> int:
        if not name.strip() or (not measurement_ids and not track_ids):
            raise ValueError("el grupo necesita nombre y al menos una medición o Track Vt")
        device_ids = set()
        for table, ids in (("mediciones", measurement_ids), ("tracks_vt", track_ids)):
            if ids:
                placeholders = ",".join("?" for _ in ids)
                rows = self.connection.execute(f"SELECT DISTINCT dispositivo_id FROM {table} WHERE id IN ({placeholders})", ids).fetchall()
                device_ids.update(int(row[0]) for row in rows)
        if len(device_ids) > 1:
            raise ValueError("un grupo solo puede asociar elementos del mismo dispositivo")
        self.connection.execute("INSERT INTO grupos_medicion(nombre) VALUES (?) ON CONFLICT(nombre) DO UPDATE SET nombre=excluded.nombre", (name.strip(),))
        group_id = int(self.connection.execute("SELECT id FROM grupos_medicion WHERE nombre = ?", (name.strip(),)).fetchone()[0])
        self.connection.execute("DELETE FROM grupo_mediciones WHERE grupo_id = ?", (group_id,))
        self.connection.execute("DELETE FROM grupo_tracks WHERE grupo_id = ?", (group_id,))
        self.connection.executemany("INSERT INTO grupo_mediciones(grupo_id, medicion_id) VALUES (?, ?)", [(group_id, value) for value in measurement_ids])
        self.connection.executemany("INSERT INTO grupo_tracks(grupo_id, track_id) VALUES (?, ?)", [(group_id, value) for value in track_ids])
        return group_id

    def measurement_groups(self) -> pd.DataFrame:
        return self._query("SELECT id, nombre, creado_en FROM grupos_medicion ORDER BY nombre")

    def group_measurements(self, group_id: int) -> pd.DataFrame:
        return self._query("""SELECT m.id, m.archivo, d.nombre AS dispositivo, c.numero AS campana
            FROM grupo_mediciones gm JOIN mediciones m ON m.id=gm.medicion_id
            JOIN dispositivos d ON d.id=m.dispositivo_id JOIN campanas c ON c.id=m.campana_id
            WHERE gm.grupo_id=? ORDER BY d.nombre, c.numero, m.archivo""", (group_id,))

    def group_tracks(self, group_id: int) -> pd.DataFrame:
        return self._query("""SELECT t.id, t.archivo, t.canal, d.nombre AS dispositivo, c.numero AS campana
            FROM grupo_tracks gt JOIN tracks_vt t ON t.id=gt.track_id
            JOIN dispositivos d ON d.id=t.dispositivo_id JOIN campanas c ON c.id=t.campana_id
            WHERE gt.grupo_id=? ORDER BY d.nombre, c.numero, t.archivo, t.canal""", (group_id,))

    def counts(self) -> dict[str, int]:
        tables = {"dispositivos": "devices", "campanas": "campaigns", "mediciones": "measurements", "puntos": "points", "tracks_vt": "tracks", "puntos_track_vt": "track_points", "datos_sin_clasificar": "unclassified", "analisis_ztc": "ztc", "grupos_medicion": "groups"}
        return {label: int(self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) for table, label in tables.items()}

    def ztc_results(self) -> pd.DataFrame:
        return self._query("""SELECT d.nombre AS dispositivo, c.id AS campana_id, c.numero AS campana,
            a.vt_ztc, a.i_ztc FROM analisis_ztc a JOIN campanas c ON c.id=a.campana_id
            JOIN dispositivos d ON d.id=c.dispositivo_id ORDER BY d.nombre, c.numero""")
