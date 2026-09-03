from __future__ import annotations

import pandas as pd

from database.repository import Repository
from services.ztc import analyze_curves


def campaign_analysis(repository: Repository, campaign_id: int) -> tuple[dict, pd.DataFrame]:
    measurements = repository.measurements(campaign_id)
    if measurements.empty:
        raise ValueError("la campana no tiene mediciones")
    curves = [repository.points(int(row.id)) for row in measurements.itertuples()]
    result, dispersion = analyze_curves(curves)
    repository.save_ztc(campaign_id, result.vt_ztc, result.i_ztc)
    return {"vt_ztc": result.vt_ztc, "i_ztc": result.i_ztc, "cantidad_mediciones": result.cantidad_mediciones}, dispersion


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
