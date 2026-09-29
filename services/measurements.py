from __future__ import annotations

import re

import numpy as np
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


def _iv_noise_ratio(points: pd.DataFrame) -> tuple[float, int]:
    clean = points[["v", "i"]].dropna().astype(float).groupby("v", as_index=False)["i"].mean().sort_values("v")
    voltage = clean.v.to_numpy()
    current = clean.i.to_numpy()
    if len(voltage) < 9:
        return float("nan"), max(0, len(voltage) - 4)

    indices = np.arange(2, len(voltage) - 2)
    offsets = np.array([-2, -1, 1, 2])
    neighbor_indices = indices[:, None] + offsets
    local_voltage = voltage[neighbor_indices] - voltage[indices, None]
    voltage_scale = np.maximum(np.max(np.abs(local_voltage), axis=1, keepdims=True), 1e-15)
    normalized_voltage = local_voltage / voltage_scale
    neighbor_current = current[neighbor_indices]
    sum_1 = normalized_voltage.sum(axis=1)
    sum_2 = (normalized_voltage**2).sum(axis=1)
    sum_3 = (normalized_voltage**3).sum(axis=1)
    sum_4 = (normalized_voltage**4).sum(axis=1)
    cofactor_00 = sum_2 * sum_4 - sum_3**2
    cofactor_01 = sum_2 * sum_3 - sum_1 * sum_4
    cofactor_02 = sum_1 * sum_3 - sum_2**2
    determinant = 4 * cofactor_00 + sum_1 * cofactor_01 + sum_2 * cofactor_02
    sum_y = neighbor_current.sum(axis=1)
    sum_xy = (normalized_voltage * neighbor_current).sum(axis=1)
    sum_xxy = (normalized_voltage**2 * neighbor_current).sum(axis=1)
    predicted = (cofactor_00 * sum_y + cofactor_01 * sum_xy + cofactor_02 * sum_xxy) / determinant
    residuals = current[indices] - predicted
    residual_median = float(np.median(residuals))
    robust_noise = 1.4826 * float(np.median(np.abs(residuals - residual_median)))
    isolated_noise = float(np.percentile(np.abs(residuals), 99))
    signal_range = float(np.percentile(current, 90) - np.percentile(current, 10))
    signal_scale = max(signal_range, float(np.median(np.abs(current))) * 0.01, 1e-15)
    return max(robust_noise, isolated_noise) / signal_scale, len(residuals)


def iv_measurement_noise_flags(measurements: pd.DataFrame, points_by_id: dict[int, pd.DataFrame]) -> pd.DataFrame:
    """Flag I-V curves with unusually noisy local residuals within their campaign."""
    columns = ["id", "noise_ratio", "noise_threshold", "control_iv"]
    if measurements.empty:
        return pd.DataFrame(columns=columns)

    results = []
    for row in measurements.itertuples():
        ratio, point_count = _iv_noise_ratio(points_by_id.get(int(row.id), pd.DataFrame(columns=["v", "i"])))
        results.append({"id": int(row.id), "noise_ratio": ratio, "points_evaluated": point_count})
    scores = pd.DataFrame(results)
    metadata = measurements[[column for column in ("id", "dispositivo_id", "campana_id") if column in measurements]].drop_duplicates("id")
    scores = scores.merge(metadata, on="id", how="left")
    group_columns = [column for column in ("dispositivo_id", "campana_id") if column in scores]
    groups = scores.groupby(group_columns, dropna=False, sort=False) if group_columns else [(None, scores)]

    thresholds = {}
    for _, group in groups:
        finite = group.noise_ratio.replace([np.inf, -np.inf], np.nan).dropna().to_numpy()
        if not len(finite):
            threshold = float("nan")
        else:
            median = float(np.median(finite))
            deviation = float(np.median(np.abs(finite - median)))
            threshold = max(0.02, median + 6 * 1.4826 * deviation)
        for measurement_id in group.id:
            thresholds[int(measurement_id)] = threshold

    scores["noise_threshold"] = scores.id.map(thresholds)
    scores["control_iv"] = np.where(
        scores.noise_ratio.isna(), "Sin puntaje (<9 puntos)",
        np.where(scores.noise_ratio >= scores.noise_threshold, "REVISAR ruido", "OK"),
    )
    return scores[columns]


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
    repository.save_ztc(campaign_id, combined.vt_ztc, combined.i_ztc)
    result = {
        "vt_ztc": combined.vt_ztc,
        "i_ztc": combined.i_ztc,
        "cantidad_mediciones": combined.cantidad_mediciones,
        "metodo": "combinado",
        "error_relativo": combined.error_relativo,
        "combined_score": combined_dispersion["combined_score_at_vt"].iloc[0],
        "combined": {"vt_ztc": combined.vt_ztc, "i_ztc": combined.i_ztc, "error_relativo": combined.error_relativo},
    }
    dispersion = combined_dispersion.copy()
    dispersion["campaign_id"] = campaign_id
    dispersion["temperatures"] = ", ".join(str(value) for value in sorted(temperatures))
    dispersion.attrs["methods"] = {"combinado": result["combined"]}
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


def compare_measurements_to_reference(repository: Repository, measurements: pd.DataFrame, reference_id: int) -> pd.DataFrame:
    if measurements.empty or reference_id not in measurements.id.to_numpy():
        raise ValueError("la medicion de referencia no esta en la seleccion activa")
    reference = individual_result(repository, reference_id, 0.0, 0.0)
    rows = []
    for measurement in measurements.itertuples():
        point = individual_result(repository, int(measurement.id), reference["vt_individual"], reference["i_individual"])
        rows.append({
            "id": int(measurement.id),
            "medicion": measurement.archivo,
            "vt_individual": point["vt_individual"],
            "error_vt": point["error_vt"],
            "error_vt_pct": point["error_vt_pct"],
            "i_individual": point["i_individual"],
            "error_i": point["error_i_ztc"],
            "error_i_pct": point["error_i_ztc_pct"],
        })
    return pd.DataFrame(rows)
