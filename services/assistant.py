from __future__ import annotations

import re

from database.repository import Repository


def answer_question(repository: Repository, question: str) -> str:
    text = question.casefold().strip()
    counts = repository.counts()
    measurements = repository.measurements(include_deleted=True)
    active = int(measurements.activa.sum()) if not measurements.empty else 0
    inactive = len(measurements) - active
    integrity = repository.connection.execute(
        "SELECT COUNT(*) FROM tracks_vt"
    ).fetchone()[0]

    if not text:
        return "Preguntame por mediciones activas, campañas, ZTC, duplicados o integridad de la base."
    if re.search(r"(medicion|mediciones|curva|curvas)", text):
        return f"Hay {len(measurements)} mediciones I-V guardadas: {active} activas y {inactive} inactivas. Las inactivas se conservan, pero no participan en gráficos ni cálculos."
    if re.search(r"(ztc|automatic|resultado)", text):
        return f"La base tiene {counts['ztc']} resultados ZTC guardados. El análisis usa solo mediciones activas con temperatura identificable y al menos dos temperaturas distintas."
    if re.search(r"(campana|campaña|campanas|campañas)", text):
        return f"Hay {counts['campaigns']} campañas y {counts['devices']} dispositivos registrados."
    if re.search(r"(duplic|integridad|track)", text):
        duplicates = repository.connection.execute(
            "SELECT COUNT(*) - COUNT(DISTINCT dispositivo_id || ':' || track_key) FROM tracks_vt"
        ).fetchone()[0]
        return f"Hay {integrity} tracks guardados y el chequeo de claves Track Vt informa {max(0, int(duplicates))} duplicados."
    if re.search(r"(inactiv|elimin|desactiv)", text):
        return f"Hay {inactive} mediciones inactivas. Podés reactivarlas desde el modo edición de metadata en cualquier visor de mediciones."
    return "Puedo consultar el estado de mediciones, campañas, resultados ZTC, tracks e integridad. Probá con una pregunta más concreta."
