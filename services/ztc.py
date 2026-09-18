from __future__ import annotations

import numpy as np
import pandas as pd

from models.ztc import ResultadoZTC


def _curve(points: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    clean = points[["v", "i"]].dropna().astype(float).groupby("v", as_index=False)["i"].mean().sort_values("v")
    if len(clean) < 2:
        raise ValueError("cada medicion necesita al menos 2 tensiones distintas")
    return clean.v.to_numpy(), clean.i.to_numpy()


def analyze_curves(curves: list[pd.DataFrame], temperatures: list[float] | None = None, method: str = "dI/dT") -> tuple[ResultadoZTC, pd.DataFrame]:
    if not curves:
        raise ValueError("la campana no tiene mediciones")
    prepared = [_curve(curve) for curve in curves]
    if temperatures is not None and len(temperatures) != len(prepared):
        raise ValueError("la cantidad de temperaturas debe coincidir con la cantidad de curvas")
    if temperatures is not None and len(set(temperatures)) < 2:
        raise ValueError("se necesitan al menos dos temperaturas distintas")
    if len(prepared) == 1:
        values, spline = prepared[0]
        if temperatures is not None:
            raise ValueError("ZTC necesita al menos dos barridos a distintas temperaturas")
        index = int(np.argmin(np.abs(spline)))
        return ResultadoZTC(float(values[index]), float(spline[index]), 1, method), pd.DataFrame({"v": values, "dispersion": np.zeros(len(values)), "relative_error": np.zeros(len(values))})

    lower = max(values.min() for values, _ in prepared)
    upper = min(values.max() for values, _ in prepared)
    if lower >= upper:
        raise ValueError("las mediciones no tienen un intervalo de tension comun")
    samples = np.linspace(lower, upper, max(200, len(curves) * 50))
    currents = np.vstack([np.interp(samples, values, current) for values, current in prepared])
    spread = currents.max(axis=0) - currents.min(axis=0)
    mean_current = currents.mean(axis=0)
    relative_error = spread / np.maximum(np.abs(mean_current), 1e-15)
    slope = np.zeros(len(samples))
    if temperatures is None:
        vt = float(samples[int(np.argmin(spread))])
        method = "dispersion"
    else:
        temperature_values = np.asarray(temperatures, dtype=float)
        centered_temperature = temperature_values - temperature_values.mean()
        denominator = float(np.dot(centered_temperature, centered_temperature))
        slope = centered_temperature @ currents / denominator
        if method == "error relativo":
            vt = float(samples[int(np.argmin(relative_error))])
        else:
            crossings = np.flatnonzero(slope[:-1] * slope[1:] <= 0)
            if len(crossings):
                crossing = crossings[int(np.argmin(np.abs(slope[crossings])))]
                vt = float(np.interp(0.0, [slope[crossing], slope[crossing + 1]], [samples[crossing], samples[crossing + 1]]))
            else:
                vt = float(samples[int(np.argmin(np.abs(slope)))])
    if temperatures is not None:
        slope_scale = max(float(np.nanpercentile(np.abs(slope), 75)), 1e-15)
        relative_scale = max(float(np.nanpercentile(relative_error, 75)), 1e-15)
        slope_component = np.abs(slope) / slope_scale
        relative_component = relative_error / relative_scale
        combined_score = 0.8 * slope_component + 0.2 * relative_component
        crossings = np.flatnonzero(slope[:-1] * slope[1:] <= 0)
        if method == "combinado" and len(crossings):
            candidate_indices = np.unique(np.clip(np.concatenate([crossings, crossings + 1]), 0, len(samples) - 1))
            vt = float(samples[candidate_indices[np.argmin(combined_score[candidate_indices])]])
    else:
        slope_component = np.zeros(len(samples))
        relative_component = np.zeros(len(samples))
        combined_score = np.zeros(len(samples))
    iztc = float(np.mean([np.interp(vt, values, current) for values, current in prepared]))
    error_at_vt = float(np.interp(vt, samples, relative_error))
    combined_at_vt = float(np.interp(vt, samples, combined_score))
    return ResultadoZTC(vt, iztc, len(curves), method, error_at_vt), pd.DataFrame({"v": samples, "dispersion": spread, "d_i_d_t": slope, "relative_error": relative_error, "slope_component": slope_component, "relative_component": relative_component, "combined_score": combined_score, "combined_score_at_vt": combined_at_vt})
