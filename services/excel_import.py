from __future__ import annotations

import hashlib
import io
import re
from typing import BinaryIO

import pandas as pd

from database.repository import Repository, _device_parts

ALIASES = {
    "dispositivo": ["dispositivo", "device", "nombre dispositivo", "dut"],
    "campana": ["campana", "campaña", "campaign", "numero campaña"],
    "medicion": ["medicion", "medición", "measurement", "archivo", "file"],
    "v": ["v", "voltaje", "voltage", "voltaje [v]"],
    "i": ["i", "corriente", "current", "corriente [a]"],
    "fecha": ["fecha", "date"], "descripcion": ["descripcion", "descripción", "description"],
    "clase": ["clase", "class"], "estado": ["estado", "state"],
}
TRACK_TIME_HEADERS = {"t s", "tiempo s", "time s", "t"}
TRACK_VOLTAGE_HEADERS = {"vt v", "v t v", "v t", "vt"}
KEY_ALIASES = {_normalized_alias: key for key, aliases in ALIASES.items() for _normalized_alias in [re.sub(r"[^a-z0-9]+", " ", _alias.strip().lower()).strip() for _alias in aliases]}


def _normalized(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).strip().lower()).strip()


def _clean(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    if isinstance(value, pd.Timestamp):
        return value.isoformat(sep=" ")
    return str(value).strip()


def _measurement_key(value: object) -> str:
    return _normalized(re.sub(r"\.ri$", "", _clean(value)))


def _find_columns(frame: pd.DataFrame) -> dict[str, int]:
    fallback = {}
    for header_row in range(min(len(frame), 30)):
        found = {KEY_ALIASES[_normalized(value)]: index for index, value in enumerate(frame.iloc[header_row]) if _normalized(value) in KEY_ALIASES}
        if found:
            found["__header_row"] = header_row
            if {"v", "i"} <= found.keys() or {"dispositivo", "medicion"} <= found.keys():
                return found
            fallback = found
    return fallback


def detect_vi_columns(frame: pd.DataFrame) -> dict[str, int]:
    columns = _find_columns(frame)
    return {key: columns[key] for key in ("v", "i", "__header_row") if key in columns} if {"v", "i"} <= columns.keys() else {}


def extract_device(*values: object) -> str:
    for value in values:
        text = _clean(value)
        if text:
            _, _, canonical = _device_parts(text)
            return canonical
    return ""


def extract_metadata(frame: pd.DataFrame, sheet_name: str, filename: str = "") -> dict[str, str]:
    metadata: dict[str, str] = {}
    for row in frame.itertuples(index=False, name=None):
        if len(row) >= 2:
            key = KEY_ALIASES.get(_normalized(row[0]))
            if key and key not in metadata:
                metadata[key] = _clean(row[1])
    columns = _find_columns(frame)
    if "__header_row" in columns:
        for key, index in columns.items():
            if key not in {"__header_row", "v", "i"} and key not in metadata and index < frame.shape[1] and columns["__header_row"] + 1 < len(frame):
                metadata[key] = _clean(frame.iloc[columns["__header_row"] + 1, index])
    metadata["dispositivo"] = extract_device(metadata.get("dispositivo"), sheet_name, filename)
    metadata["medicion"] = metadata.get("medicion") or filename or sheet_name
    metadata["campana"] = metadata.get("campana") or "sin asignar"
    return metadata


def _metadata_catalog(frames: list[tuple[str, pd.DataFrame]]) -> dict[str, dict[str, str]]:
    catalog: dict[str, dict[str, str]] = {}
    for _, frame in frames:
        columns = _find_columns(frame)
        if not {"dispositivo", "medicion"} <= columns.keys():
            continue
        row_start = columns["__header_row"] + 1
        for row in frame.iloc[row_start:].itertuples(index=False, name=None):
            row_data = {
                key: _clean(row[index])
                for key, index in columns.items()
                if key != "__header_row" and key not in {"v", "i"} and index < len(row)
            }
            measurement = row_data.get("medicion")
            if measurement:
                catalog[_measurement_key(measurement)] = row_data
    return catalog


def _points_from_frame(frame: pd.DataFrame) -> pd.DataFrame:
    columns = detect_vi_columns(frame)
    if not columns:
        return pd.DataFrame(columns=["v", "i"])
    points = frame.iloc[columns["__header_row"] + 1:, [columns["v"], columns["i"]]].copy()
    points.columns = ["v", "i"]
    points["v"] = pd.to_numeric(points["v"], errors="coerce")
    points["i"] = pd.to_numeric(points["i"], errors="coerce")
    return points.dropna().drop_duplicates().reset_index(drop=True)


def _track_blocks(frame: pd.DataFrame) -> list[dict[str, object]]:
    blocks = []
    for header_row in range(min(len(frame), 15)):
        for time_index in range(max(0, frame.shape[1] - 1)):
            time_header = _normalized(frame.iloc[header_row, time_index])
            voltage_header = _normalized(frame.iloc[header_row, time_index + 1])
            if time_header not in TRACK_TIME_HEADERS or voltage_header not in TRACK_VOLTAGE_HEADERS:
                continue
            values = frame.iloc[header_row + 1:, [time_index, time_index + 1]].copy()
            values.columns = ["t", "vt"]
            values["t"] = pd.to_numeric(values["t"], errors="coerce")
            values["vt"] = pd.to_numeric(values["vt"], errors="coerce")
            points = values.dropna().drop_duplicates().reset_index(drop=True)
            if points.empty:
                continue
            channel = _clean(frame.iloc[header_row - 1, time_index]) if header_row else ""
            device = ""
            raw_device = ""
            for row_index in range(header_row - 1, -1, -1):
                candidate = _clean(frame.iloc[row_index, time_index])
                if extract_device(candidate):
                    device = extract_device(candidate)
                    break
                if row_index == header_row - 3 and candidate and "volver" not in _normalized(candidate):
                    raw_device = candidate
            if not device:
                device = extract_device(frame.iloc[:, time_index].dropna().tolist()) or raw_device or "TRACK SIN IDENTIFICAR"
            date = _clean(frame.iloc[header_row - 2, time_index]) if header_row >= 2 else ""
            blocks.append({"device": device, "channel": channel or f"Track {time_index + 1}", "date": date, "points": points,
                           "block_index": len(blocks)})
    return blocks


def calculate_measurement_hash(device: str, measurement: str, measurement_date: str, points: pd.DataFrame) -> str:
    values = [f"{float(row.v):.15g},{float(row.i):.15g}" for row in points.itertuples()]
    payload = "|".join((_normalized(device), _normalized(measurement), _normalized(measurement_date), *values))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _import_one(metadata: dict[str, str], points: pd.DataFrame, repository: Repository, stats: dict[str, int]) -> None:
    device = extract_device(metadata.get("dispositivo"), metadata.get("medicion"))
    measurement = _clean(metadata.get("medicion"))
    if not device or not measurement:
        raise ValueError("no se pudo identificar dispositivo o medicion")
    device_id = repository.add_device(device)
    campaign_id = repository.add_campaign(device_id, metadata.get("campana", "sin asignar"))
    measurement_date = _clean(metadata.get("fecha"))
    values = {"dispositivo_id": device_id, "campana_id": campaign_id, "archivo": measurement, "fecha": measurement_date,
              "descripcion": _clean(metadata.get("descripcion")), "clase": _clean(metadata.get("clase")), "estado": _clean(metadata.get("estado")),
              "measurement_hash": calculate_measurement_hash(device, measurement, measurement_date, points)}
    measurement_id, created = repository.add_measurement(values)
    added_points = repository.add_points(measurement_id, points)
    stats["mediciones_nuevas"] += int(created)
    stats["ya_existentes"] += int(not created)
    stats["mediciones_actualizadas"] += int(repository.last_measurement_updated)
    stats["puntos_nuevos"] += added_points
    stats["duplicados_evitados"] += int(not created) + max(0, len(points) - added_points)


def _import_frames(frames: list[tuple[str, pd.DataFrame]], repository: Repository) -> dict:
    stats = {"mediciones_nuevas": 0, "mediciones_actualizadas": 0, "ya_existentes": 0, "duplicados_evitados": 0, "puntos_nuevos": 0}
    errors = []
    catalog = _metadata_catalog(frames)
    for sheet_name, frame in frames:
        metadata = extract_metadata(frame, sheet_name)
        points = _points_from_frame(frame)
        try:
            if not points.empty:
                catalog_metadata = catalog.get(_measurement_key(metadata.get("medicion", sheet_name)), {})
                metadata = {**catalog_metadata, **metadata}
                if metadata.get("campana") == "sin asignar" and catalog_metadata.get("campana"):
                    metadata["campana"] = catalog_metadata["campana"]
                _import_one(metadata, points, repository, stats)
        except (TypeError, ValueError) as error:
            errors.append({"Archivo": sheet_name, "Fila": "-", "Problema": str(error)})
    repository.connection.commit()
    stats.update({"errores": errors, "dispositivos": len(repository.devices()), "campanas": len(repository.campaigns()),
                  "mediciones": stats["mediciones_nuevas"], "puntos": stats["puntos_nuevos"], "ignorados": len(errors)})
    return stats


def _import_track_frames(frames: list[tuple[str, pd.DataFrame]], repository: Repository) -> dict[str, object]:
    tracks_new = 0
    track_points_new = 0
    errors = []
    for sheet_name, frame in frames:
        for block in _track_blocks(frame):
            try:
                device = str(block["device"])
                if not device:
                    raise ValueError("no se pudo identificar dispositivo del Track Vt")
                device_id = repository.add_device(device)
                campaign_id = repository.add_campaign(device_id, sheet_name)
                track_key = f"{sheet_name}::{block['block_index']}"
                track_id, created = repository.add_track({
                    "dispositivo_id": device_id,
                    "campana_id": campaign_id,
                    "archivo": sheet_name,
                    "track_key": track_key,
                    "canal": str(block["channel"]),
                    "fecha": str(block["date"]),
                    "descripcion": "Track Vt",
                    "source_sheet": sheet_name,
                })
                track_points_new += repository.add_track_points(track_id, block["points"])
                tracks_new += int(created)
            except (TypeError, ValueError) as error:
                errors.append({"Archivo": sheet_name, "Fila": "-", "Problema": str(error)})
    repository.connection.commit()
    return {"tracks_nuevos": tracks_new, "track_points_nuevos": track_points_new, "errores_track": errors}


def _import_unclassified_frames(frames: list[tuple[str, pd.DataFrame]], source_file: str, repository: Repository) -> int:
    imported = 0
    for sheet_name, frame in frames:
        if not _points_from_frame(frame).empty or _track_blocks(frame):
            continue
        payload = frame.to_json(orient="split", force_ascii=False, date_format="iso")
        content_hash = hashlib.sha256(f"{sheet_name}|{payload}".encode("utf-8")).hexdigest()
        imported += int(repository.add_unclassified({
            "archivo_origen": source_file,
            "hoja": sheet_name,
            "tipo": "sin clasificar",
            "filas": len(frame),
            "columnas": ", ".join(str(column) for column in frame.columns),
            "datos_json": payload,
            "contenido_hash": content_hash,
        }))
    repository.connection.commit()
    return imported


def import_excel(uploaded_file: BinaryIO, repository: Repository) -> dict:
    frames = list(pd.read_excel(uploaded_file, sheet_name=None, header=None).items())
    source_file = getattr(uploaded_file, "name", "archivo.xlsx")
    summary = _import_frames(frames, repository)
    track_summary = _import_track_frames(frames, repository)
    summary["sin_clasificar_nuevos"] = _import_unclassified_frames(frames, source_file, repository)
    summary["tracks_nuevos"] = track_summary["tracks_nuevos"]
    summary["track_points_nuevos"] = track_summary["track_points_nuevos"]
    summary["errores"].extend(track_summary["errores_track"])
    summary["ignorados"] = len(summary["errores"])
    return summary


def import_measurement(uploaded_file: BinaryIO, repository: Repository) -> dict:
    raw = uploaded_file.read()
    name = getattr(uploaded_file, "name", "medicion.ri")
    frame = pd.read_csv(io.BytesIO(raw), sep=r"[,;\t ]+", engine="python", header=None, comment="#")
    metadata = extract_metadata(frame, "", name)
    points = _points_from_frame(frame)
    if points.empty:
        raise ValueError("no se encontraron columnas V/I ni puntos numericos")
    return _import_frames([(name, frame)], repository)


def detect_input_type(uploaded_file: BinaryIO) -> str:
    name = getattr(uploaded_file, "name", "").lower()
    if name.endswith((".xlsx", ".xlsm", ".xls")):
        return "excel"
    if name.endswith(".ri"):
        return "medicion"
    return "desconocido"
