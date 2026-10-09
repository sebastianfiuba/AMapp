from __future__ import annotations

import numpy as np
import pandas as pd

from services.measurements import extract_temperature


def available_temperatures(measurements: pd.DataFrame) -> list[float]:
    if measurements.empty:
        return []
    temperatures = {
        temperature
        for row in measurements.itertuples()
        if (temperature := extract_temperature(row)) is not None
    }
    return sorted(temperatures)


def preferred_temperature(temperatures: list[float]) -> float | None:
    for preferred in (26.0, 28.0):
        if preferred in temperatures:
            return preferred
    return None


def parse_target_currents(value: str) -> list[float]:
    currents = []
    for item in value.replace(",", ".").replace("\n", ";").split(";"):
        item = item.strip()
        if not item:
            continue
        try:
            current = float(item)
        except ValueError as error:
            raise ValueError(f"corriente no válida: {item}") from error
        if not np.isfinite(current):
            raise ValueError(f"corriente no finita: {item}")
        if current not in currents:
            currents.append(current)
    if not currents:
        raise ValueError("ingresá al menos una corriente objetivo")
    return currents


def delta_vt_at_currents(repository, measurements: pd.DataFrame, currents: list[float],
                         reference_id: int) -> tuple[pd.DataFrame, list[str]]:
    if measurements.empty:
        raise ValueError("seleccioná al menos una medición")
    if not currents or any(not np.isfinite(current) for current in currents):
        raise ValueError("ingresá al menos una corriente objetivo finita")
    if "dispositivo_id" in measurements and measurements.dispositivo_id.nunique() != 1:
        raise ValueError("las mediciones deben pertenecer al mismo dispositivo")
    measurement_ids = measurements.id.astype(int).tolist()
    if reference_id not in measurement_ids:
        raise ValueError("la medición de referencia debe estar seleccionada")

    reference = measurements[measurements.id.astype(int) == reference_id].iloc[0]
    reference_label = f"{reference.campana} | {reference.archivo}"
    rows = []
    warnings = []
    for current in currents:
        voltages = {}
        for measurement in measurements.itertuples():
            measurement_id = int(measurement.id)
            points = repository.points(measurement_id)
            if points.empty:
                warnings.append(f"{measurement.archivo}: no tiene puntos I-V.")
                continue
            clean = points[["v", "i"]].apply(pd.to_numeric, errors="coerce").dropna()
            clean = clean.groupby("i", as_index=False)["v"].mean().sort_values("i")
            if len(clean) < 2:
                warnings.append(f"{measurement.archivo}: necesita dos corrientes distintas.")
                continue
            if current < clean.i.min() or current > clean.i.max():
                warnings.append(f"{measurement.archivo}: {current:.8g} A queda fuera del rango medido.")
                continue
            voltages[measurement_id] = float(np.interp(current, clean.i.to_numpy(), clean.v.to_numpy()))

        if reference_id not in voltages:
            warnings.append(f"No se pudo calcular la corriente {current:.8g} A en la medición de referencia.")
            continue
        reference_voltage = voltages[reference_id]
        for measurement in measurements.itertuples():
            measurement_id = int(measurement.id)
            if measurement_id not in voltages:
                continue
            rows.append({
                "id": measurement_id,
                "Medición": f"{measurement.campana} | {measurement.archivo}",
                "Corriente [A]": current,
                "VT [V]": voltages[measurement_id],
                "ΔVT [V]": voltages[measurement_id] - reference_voltage,
                "Referencia": reference_label,
            })
    return pd.DataFrame(rows), warnings
