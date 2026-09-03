from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.interpolate import CubicSpline
from scipy.optimize import minimize_scalar

from models.ztc import ResultadoZTC


def _curve(points: pd.DataFrame) -> tuple[np.ndarray, CubicSpline]:
    clean = points[["v", "i"]].dropna().astype(float).groupby("v", as_index=False)["i"].mean().sort_values("v")
    if len(clean) < 2:
        raise ValueError("cada medicion necesita al menos 2 tensiones distintas")
    return clean.v.to_numpy(), CubicSpline(clean.v.to_numpy(), clean.i.to_numpy())


def analyze_curves(curves: list[pd.DataFrame]) -> tuple[ResultadoZTC, pd.DataFrame]:
    if not curves:
        raise ValueError("la campana no tiene mediciones")
    prepared = [_curve(curve) for curve in curves]
    if len(prepared) == 1:
        values, spline = prepared[0]
        target_magnitude = 170e-6
        sign = 1 if float(np.mean(spline(values))) >= 0 else -1
        target = sign * target_magnitude

        def target_error(voltage: float) -> float:
            return float((spline(voltage) - target) ** 2)

        result = minimize_scalar(target_error, bounds=(float(values.min()), float(values.max())), method="bounded")
        vt = float(result.x)
        return ResultadoZTC(vt, float(spline(vt)), 1), pd.DataFrame({"v": values, "dispersion": np.zeros(len(values))})

    lower = max(values.min() for values, _ in prepared)
    upper = min(values.max() for values, _ in prepared)
    if lower >= upper:
        raise ValueError("las mediciones no tienen un intervalo de tension comun")
    samples = np.linspace(lower, upper, max(200, len(curves) * 50))
    currents = np.vstack([spline(samples) for _, spline in prepared])
    spread = currents.max(axis=0) - currents.min(axis=0)
    coarse_v = float(samples[int(np.argmin(spread))])
    step = (upper - lower) / max(len(samples) - 1, 1)
    left, right = max(lower, coarse_v - step), min(upper, coarse_v + step)

    def objective(voltage: float) -> float:
        values = np.array([spline(voltage) for _, spline in prepared])
        return float(values.max() - values.min())

    result = minimize_scalar(objective, bounds=(left, right), method="bounded")
    vt = float(result.x)
    iztc = float(np.mean([spline(vt) for _, spline in prepared]))
    return ResultadoZTC(vt, iztc, len(curves)), pd.DataFrame({"v": samples, "dispersion": spread})
