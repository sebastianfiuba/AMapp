from io import BytesIO

import pandas as pd
from openpyxl import Workbook

from database.repository import Repository


def export_excel(repository: Repository) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        repository.devices().to_excel(writer, index=False, sheet_name="Dispositivos")
        repository.campaigns().to_excel(writer, index=False, sheet_name="Campanas")
        repository.measurements().to_excel(writer, index=False, sheet_name="Mediciones")
        repository.ztc_results().to_excel(writer, index=False, sheet_name="Resultados ZTC")
        repository.all_points().to_excel(writer, index=False, sheet_name="Puntos V I")
        repository.tracks().to_excel(writer, index=False, sheet_name="Tracks Vt")
        repository.all_track_points().to_excel(writer, index=False, sheet_name="Puntos Track Vt")
        repository.campaign_links().to_excel(writer, index=False, sheet_name="Secuencia Campanas")
        repository.unclassified().to_excel(writer, index=False, sheet_name="Sin clasificar")
    return output.getvalue()


def export_integrity(repository: Repository) -> dict[str, int]:
    checks = {
        "mediciones_duplicadas": "SELECT COUNT(*) - COUNT(DISTINCT campana_id || ':' || archivo) FROM mediciones",
        "puntos_iv_duplicados": "SELECT COUNT(*) - COUNT(DISTINCT medicion_id || ':' || v || ':' || i) FROM puntos",
        "tracks_duplicados": "SELECT COUNT(*) - COUNT(DISTINCT dispositivo_id || ':' || archivo || ':' || canal) FROM tracks_vt",
        "puntos_track_duplicados": "SELECT COUNT(*) - COUNT(DISTINCT track_id || ':' || t || ':' || vt) FROM puntos_track_vt",
    }
    return {name: max(0, int(repository.connection.execute(sql).fetchone()[0] or 0)) for name, sql in checks.items()}
