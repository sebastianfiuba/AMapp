from __future__ import annotations

import json
import os
import re
import urllib.request

import numpy as np

from database.repository import Repository
from services.measurements import extract_temperature, temperature_measurements
from services.ztc import analyze_curves


def _local_ai_answer(question: str, analysis: str) -> str:
    host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")
    payload = json.dumps({
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": "Sos un asistente de laboratorio eléctrico. Responde en español, explica brevemente el análisis indicado usando solo los datos dados. No inventes mediciones ni alteres los valores numéricos."},
            {"role": "user", "content": f"Consulta: {question}\nAnálisis de la base: {analysis}"},
        ],
        "options": {"temperature": 0.2, "num_predict": 180},
    }).encode("utf-8")
    request = urllib.request.Request(f"{host}/api/chat", data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            message = json.loads(response.read().decode("utf-8"))["message"]["content"].strip()
        return message or analysis
    except (OSError, TimeoutError, KeyError, json.JSONDecodeError, UnicodeDecodeError):
        return analysis


def _requested_target(repository: Repository, text: str):
    device_match = re.search(r"(?:dispositivo|device|dut)\s*(?:n(?:ro|umero)?\.?\s*)?([a-z]*\d+[a-z0-9_-]*)", text)
    campaign_match = re.search(r"(?:camp(?:aña|ana)|campaign)\s*(?:n(?:ro|umero)?\.?\s*)?([a-z0-9_-]+)", text)
    if not device_match or not campaign_match:
        return None
    token = device_match.group(1).casefold()
    number = re.search(r"\d+", token)
    devices = repository.devices()
    if re.search(r"[a-z]", token):
        matches = devices[devices.nombre.str.casefold().str.contains(token, regex=False)]
    elif number is not None:
        matches = devices[devices.numero.astype(str) == number.group(0)]
    else:
        matches = devices.iloc[0:0]
    if len(matches) != 1:
        return None
    device = matches.iloc[0]
    campaigns = repository.campaigns(int(device.id))
    campaign_number = campaign_match.group(1).casefold()
    campaign = campaigns[campaigns.numero.astype(str).str.casefold() == campaign_number]
    if campaign.empty:
        available = ", ".join(campaigns.numero.astype(str).tolist()) or "ninguna"
        return f"No encontré la campaña {campaign_number} de {device.nombre}. Campañas disponibles: {available}."
    return int(campaign.iloc[0].id), device.nombre, campaign_number


def _analyze_campaign(repository: Repository, campaign_id: int, device_name: str, campaign_number: str) -> str:
    all_measurements = repository.iv_measurements(campaign_id, include_deleted=True)
    inactive_count = int((~all_measurements.activa.astype(bool)).sum()) if not all_measurements.empty else 0
    measurements = temperature_measurements(all_measurements[all_measurements.activa.astype(bool)])
    if measurements.empty:
        return (f"{device_name}, campaña {campaign_number}: no hay barridos térmicos activos para analizar. "
                f"Mediciones inactivas conservadas: {inactive_count}.")
    temperatures = [extract_temperature(row) for row in measurements.itertuples()]
    if len(set(temperatures)) < 2:
        return (f"{device_name}, campaña {campaign_number}: encontré {len(measurements)} barrido(s), "
                "pero hacen falta al menos dos temperaturas distintas para estimar ZTC.")
    curves = [repository.points(int(row.id)) for row in measurements.itertuples()]
    try:
        result, dispersion = analyze_curves(curves, temperatures, "combinado")
    except ValueError as error:
        return f"{device_name}, campaña {campaign_number}: no pude calcular ZTC. {error}."
    candidates = dispersion.attrs.get("crossing_candidates", [])
    selected = min(candidates, key=lambda candidate: candidate["stable_score"]) if candidates else None
    minimum = dispersion.loc[dispersion.relative_error.idxmin()]
    curves_at_minimum = [
        np.interp(float(minimum.v), curve.sort_values("v").v, curve.sort_values("v").i)
        for curve in curves
    ]
    minimum_current = float(np.mean(curves_at_minimum))
    temperatures_label = ", ".join(f"{value:g} °C" for value in sorted(temperatures))
    crossing_note = (f"Se detectaron {len(candidates)} cruces; se eligió el {selected['orden']}° "
                     "por estabilidad local y del tramo." if selected else "No se detectaron cruces de pendiente.")
    return (f"{device_name}, campaña {campaign_number}: {len(measurements)} barridos activos "
            f"({temperatures_label}). ZTC combinado: VT={result.vt_ztc:.6g} V, "
            f"I={result.i_ztc * 1_000_000:.4g} µA; error relativo en ZTC={result.error_relativo:.2%}. "
            f"{crossing_note} La mínima dispersión aparece en VT={float(minimum.v):.6g} V "
            f"(I media={minimum_current * 1_000_000:.4g} µA, error={float(minimum.relative_error):.2%}). "
            f"Mediciones inactivas conservadas: {inactive_count}.")


def answer_question(repository: Repository, question: str) -> str:
    text = question.casefold().strip()
    target = _requested_target(repository, text)
    if isinstance(target, str):
        return _local_ai_answer(question, target)
    if target is not None:
        return _local_ai_answer(question, _analyze_campaign(repository, *target))
    counts = repository.counts()
    measurements = repository.measurements(include_deleted=True)
    active = int(measurements.activa.sum()) if not measurements.empty else 0
    inactive = len(measurements) - active
    integrity = repository.connection.execute(
        "SELECT COUNT(*) FROM tracks_vt"
    ).fetchone()[0]

    if not text:
        answer = "Pedime un análisis por dispositivo y campaña, por ejemplo: analiza dispositivo 17, campaña 15. También consulto mediciones, ZTC e integridad."
        return _local_ai_answer(question, answer)
    if re.search(r"(medici[oó]n(?:es)?|curva|curvas)", text):
        answer = f"Hay {len(measurements)} mediciones I-V guardadas: {active} activas y {inactive} inactivas. Las inactivas se conservan, pero no participan en gráficos ni cálculos."
        return _local_ai_answer(question, answer)
    if re.search(r"(ztc|automatic|resultado)", text):
        answer = f"La base tiene {counts['ztc']} resultados ZTC guardados. El análisis usa solo mediciones activas con temperatura identificable y al menos dos temperaturas distintas."
        return _local_ai_answer(question, answer)
    if re.search(r"(campana|campaña|campanas|campañas)", text):
        answer = f"Hay {counts['campaigns']} campañas y {counts['devices']} dispositivos registrados."
        return _local_ai_answer(question, answer)
    if re.search(r"(duplic|integridad|track)", text):
        duplicates = repository.connection.execute(
            "SELECT COUNT(*) - COUNT(DISTINCT dispositivo_id || ':' || track_key) FROM tracks_vt"
        ).fetchone()[0]
        answer = f"Hay {integrity} tracks guardados y el chequeo de claves Track Vt informa {max(0, int(duplicates))} duplicados."
        return _local_ai_answer(question, answer)
    if re.search(r"(inactiv|elimin|desactiv)", text):
        answer = f"Hay {inactive} mediciones inactivas. Podés reactivarlas desde el modo edición de metadata en cualquier visor de mediciones."
        return _local_ai_answer(question, answer)
    answer = "Puedo analizar un dispositivo y campaña concretos, o consultar mediciones, ZTC, campañas, tracks e integridad."
    return _local_ai_answer(question, answer)
