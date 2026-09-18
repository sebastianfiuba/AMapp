from __future__ import annotations

import re

import pandas as pd

from database.repository import Repository
from services.ztc import analyze_curves


def extract_temperature(row) -> float | None:
    searchable = "|".join(str(getattr(row, field, "") or "") for field in ("archivo", "descripcion", "clase", "estado", "campana"))
    match = re.search(r"(?:t|temp(?:eratura)?|temperature)\s*[-_=]?\s*(-?\d+(?:[.,]\d+)?)", searchable.casefold())
    if not match:
        match = re.search(r"(-?\d+(?:[.,]\d+)?)\s*(?:°\s*c|grados)", searchable.casefold())
    return float(match.group(1).replace(",", ".")) if match else None


def is_temperature_sweep(row) -> bool:
    return extract_temperature(row) is not None


def temperature_measurements(measurements: pd.DataFrame) -> pd.DataFrame:
    if measurements.empty:
        return measurements.copy()
    return measurements[measurements.apply(is_temperature_sweep, axis=1)].copy()


def campaign_analysis(repository: Repository, campaign_id: int, measurements: pd.DataFrame | None = None, method: str = "dI/dT") -> tuple[dict, pd.DataFrame]:
    measurements = repository.iv_measurements(campaign_id) if measurements is None else measurements
    if measurements.empty:
        raise ValueError("la campana no tiene mediciones")
    rows = list(measurements.itertuples())
    temperatures = [extract_temperature(row) for row in rows]
    if any(value is None for value in temperatures):
        raise ValueError("cada barrido de temperatura necesita una temperatura identificable en sus metadatos")
    if len(set(temperatures)) < 2:
        raise ValueError("se necesitan al menos dos temperaturas distintas para calcular ZTC")
    curves = [repository.points(int(row.id)) for row in rows]
    result, dispersion = analyze_curves(curves, temperatures, method)
    repository.save_ztc(campaign_id, result.vt_ztc, result.i_ztc)
    return {"vt_ztc": result.vt_ztc, "i_ztc": result.i_ztc, "cantidad_mediciones": result.cantidad_mediciones,
            "metodo": result.metodo, "error_relativo": result.error_relativo}, dispersion


def campaign_analysis_methods(repository: Repository, campaign_id: int, measurements: pd.DataFrame | None = None) -> tuple[dict, pd.DataFrame]:
    measurements = repository.iv_measurements(campaign_id) if measurements is None else measurements
    if measurements.empty:
        raise ValueError("la campana no tiene mediciones")
    rows = list(measurements.itertuples())
    temperatures = [extract_temperature(row) for row in rows]
    if any(value is None for value in temperatures):
        raise ValueError("cada barrido de temperatura necesita una temperatura identificable en sus metadatos")
    if len(set(temperatures)) < 2:
        raise ValueError("se necesitan al menos dos temperaturas distintas para calcular ZTC")
    curves = [repository.points(int(row.id)) for row in rows]
    combined, combined_dispersion = analyze_curves(curves, temperatures, "combinado")
    physical, physical_dispersion = analyze_curves(curves, temperatures, "dI/dT")
    relative, relative_dispersion = analyze_curves(curves, temperatures, "error relativo")
    repository.save_ztc(campaign_id, combined.vt_ztc, combined.i_ztc)
    result = {
        "vt_ztc": combined.vt_ztc,
        "i_ztc": combined.i_ztc,
        "cantidad_mediciones": physical.cantidad_mediciones,
        "metodo": "combinado",
        "error_relativo": combined.error_relativo,
        "combined_score": combined_dispersion["combined_score_at_vt"].iloc[0],
        "combined": {"vt_ztc": combined.vt_ztc, "i_ztc": combined.i_ztc, "error_relativo": combined.error_relativo},
        "didt": {"vt_ztc": physical.vt_ztc, "i_ztc": physical.i_ztc, "error_relativo": physical.error_relativo},
        "relative": {"vt_ztc": relative.vt_ztc, "i_ztc": relative.i_ztc, "error_relativo": relative.error_relativo},
    }
    dispersion = combined_dispersion.copy()
    dispersion["relative_method_vt"] = relative.vt_ztc
    dispersion["relative_method_i"] = relative.i_ztc
    dispersion["campaign_id"] = campaign_id
    dispersion["temperatures"] = ", ".join(str(value) for value in sorted(temperatures))
    dispersion.attrs["methods"] = {"combinado": result["combined"], "dI/dT": result["didt"], "error relativo": result["relative"]}
    return result, dispersion


def individual_result(repository: Repository, measurement_id: int, vt_ztc: float, i_ztc: float) -> dict:
    points = repository.points(measurement_id)
    result, _ = analyze_curves([points])
    vt_error = result.vt_ztc - vt_ztc
    i_error = result.i_ztc - i_ztc
    return {
        "vt_individual": result.vt_ztc, "i_individual": result.i_ztc,
        "error_vt": vt_error, "error_vt_pct": 100 * vt_error / vt_ztc if vt_ztc else None,
        "error_i_ztc": i_error, "error_i_ztc_pct": 100 * i_error / i_ztc if i_ztc else None,
    }
