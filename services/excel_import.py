from __future__ import annotations

import re
from datetime import date
from typing import BinaryIO

import pandas as pd

from database.repository import Repository

ALIASES = {
    "dispositivo": ["dispositivo", "device", "nombre dispositivo", "dut"],
    "campana": ["campana", "campaña", "campaign", "numero campaña"],
    "medicion": ["medicion", "medición", "measurement", "archivo", "file"],
    "v": ["v", "voltaje", "voltage", "voltaje [v]"],
    "i": ["i", "corriente", "current", "corriente [a]"],
    "fecha": ["fecha", "date"], "descripcion": ["descripcion", "descripción", "description"],
    "clase": ["clase", "class"], "estado": ["estado", "state"],
}


def _normalized(value: object) -> str:
    text = str(value).strip().lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _find_columns(frame: pd.DataFrame) -> dict[str, str]:
    normalized = {_normalized(column): column for column in frame.columns}
    found = {}
    for target, aliases in ALIASES.items():
        for alias in aliases:
            if _normalized(alias) in normalized:
                found[target] = normalized[_normalized(alias)]
                break
    return found


def import_excel(uploaded_file: BinaryIO, repository: Repository) -> dict:
    imported = ignored = points_count = 0
    errors: list[dict] = []
    sheets = pd.read_excel(uploaded_file, sheet_name=None)
    for sheet_name, frame in sheets.items():
        columns = _find_columns(frame)
        missing = [name for name in ("dispositivo", "campana", "medicion", "v", "i") if name not in columns]
        if missing:
            errors.append({"Archivo": sheet_name, "Fila": "-", "Problema": "faltan columnas: " + ", ".join(missing)})
            ignored += 1
            continue
        frame = frame.copy()
        frame["__fila"] = frame.index + 2
        group_columns = [columns[name] for name in ("dispositivo", "campana", "medicion")]
        for _, group in frame.groupby(group_columns, dropna=False, sort=False):
            try:
                row = group.iloc[0]
                device = str(row[columns["dispositivo"]]).strip()
                campaign = str(row[columns["campana"]]).strip()
                measurement = str(row[columns["medicion"]]).strip()
                if not device or not campaign or not measurement:
                    raise ValueError("identificador vacio")
                points = group[[columns["v"], columns["i"]]].rename(columns={columns["v"]: "v", columns["i"]: "i"})
                points["v"] = pd.to_numeric(points["v"], errors="raise")
                points["i"] = pd.to_numeric(points["i"], errors="raise")
                device_id = repository.add_device(device)
                campaign_id = repository.add_campaign(device_id, campaign)
                measurement_id, created = repository.add_measurement({
                    "dispositivo_id": device_id, "campana_id": campaign_id, "archivo": measurement,
                    "fecha": str(row[columns["fecha"]]) if "fecha" in columns else str(date.today()),
                    "descripcion": str(row[columns["descripcion"]]) if "descripcion" in columns else "",
                    "clase": str(row[columns["clase"]]) if "clase" in columns else "normal",
                    "estado": str(row[columns["estado"]]) if "estado" in columns else "nada",
                })
                if created:
                    repository.add_points(measurement_id, points)
                    points_count += len(points)
                    imported += 1
                else:
                    ignored += 1
            except (TypeError, ValueError) as error:
                errors.append({"Archivo": sheet_name, "Fila": int(group.iloc[0]["__fila"]), "Problema": str(error)})
                ignored += 1
    repository.connection.commit()
    return {"dispositivos": len(repository.devices()), "campanas": len(repository.campaigns()), "mediciones": imported, "puntos": points_count, "ignorados": ignored, "errores": errors}
