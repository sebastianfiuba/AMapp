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
    crossing_candidates = []
    if temperatures is not None:
        slope_scale = max(float(np.nanpercentile(np.abs(slope), 75)), 1e-15)
        relative_scale = max(float(np.nanpercentile(relative_error, 75)), 1e-15)
        spread_scale = max(float(np.nanpercentile(spread, 75)), 1e-15)
        slope_component = np.abs(slope) / slope_scale
        relative_component = relative_error / relative_scale
        spread_component = spread / spread_scale
        combined_score = 0.5 * spread_component + 0.25 * relative_component + 0.25 * slope_component
        crossings = np.flatnonzero(slope[:-1] * slope[1:] <= 0)
        if method == "combinado":
            crossing_points = []
            for crossing in crossings:
                refined_v = float(np.interp(0.0, [slope[crossing], slope[crossing + 1]], [samples[crossing], samples[crossing + 1]]))
                crossing_points.append({"vt": refined_v, "sources": ["dI/dT"]})
            temperature_values = np.asarray(temperatures, dtype=float)
            sample_step = float(samples[1] - samples[0])
            for first in range(len(prepared)):
                for second in range(first + 1, len(prepared)):
                    if temperature_values[first] == temperature_values[second]:
                        continue
                    difference = currents[first] - currents[second]
                    pair_crossings = np.flatnonzero(difference[:-1] * difference[1:] <= 0)
                    source = f"par {temperature_values[first]:g}-{temperature_values[second]:g} °C"
                    for crossing in pair_crossings:
                        refined_v = float(np.interp(0.0, [difference[crossing], difference[crossing + 1]],
                                                    [samples[crossing], samples[crossing + 1]]))
                        nearby = next((candidate for candidate in crossing_points
                                       if abs(candidate["vt"] - refined_v) <= sample_step), None)
                        if nearby is None:
                            crossing_points.append({"vt": refined_v, "sources": [source]})
                        else:
                            nearby["sources"].append(source)
                            old_spread = float(np.interp(nearby["vt"], samples, spread))
                            new_spread = float(np.interp(refined_v, samples, spread))
                            if new_spread < old_spread:
                                nearby["vt"] = refined_v
            crossing_points.sort(key=lambda candidate: candidate["vt"])
            crossing_voltages = [candidate["vt"] for candidate in crossing_points]
            for order, candidate in enumerate(crossing_points, start=1):
                refined_v = candidate["vt"]
                segment_left = lower if order == 1 else (crossing_voltages[order - 2] + refined_v) / 2
                segment_right = upper if order == len(crossing_points) else (refined_v + crossing_voltages[order]) / 2
                left_gap = refined_v - crossing_voltages[order - 2] if order > 1 else segment_right - refined_v
                right_gap = crossing_voltages[order] - refined_v if order < len(crossing_points) else refined_v - segment_left
                local_radius = max(3 * sample_step, 0.2 * min(left_gap, right_gap))
                local_mask = (samples >= max(segment_left, refined_v - local_radius)) & (samples <= min(segment_right, refined_v + local_radius))
                segment_mask = (samples >= segment_left) & (samples <= segment_right)
                if not local_mask.any():
                    local_mask[int(np.argmin(np.abs(samples - refined_v)))] = True
                if not segment_mask.any():
                    segment_mask[int(np.argmin(np.abs(samples - refined_v)))] = True
                local_slope = slope[local_mask]
                segment_slope = slope[segment_mask]
                local_relative_error = relative_error[local_mask]
                segment_relative_error = relative_error[segment_mask]
                local_spread = spread[local_mask]
                segment_spread = spread[segment_mask]
                slope_stability = float(np.median(np.abs(local_slope)) / slope_scale)
                relative_stability = float(np.median(local_relative_error) / relative_scale)
                spread_stability = float(np.percentile(local_spread, 75) / spread_scale)
                local_score = 0.5 * spread_stability + 0.25 * relative_stability + 0.25 * slope_stability
                segment_slope_stability = float(np.percentile(np.abs(segment_slope), 75) / slope_scale)
                segment_relative_stability = float(np.percentile(segment_relative_error, 75) / relative_scale)
                segment_spread_stability = float(np.percentile(segment_spread, 75) / spread_scale)
                segment_score = 0.5 * segment_spread_stability + 0.25 * segment_relative_stability + 0.25 * segment_slope_stability
                stable_score = 0.6 * local_score + 0.4 * segment_score
                crossing = int(np.clip(np.searchsorted(samples, refined_v) - 1, 0, len(samples) - 2))
                transition = abs(float(slope[crossing + 1] - slope[crossing])) / slope_scale
                candidate_current = float(np.mean([np.interp(refined_v, values, current) for values, current in prepared]))
                has_slope_crossing = "dI/dT" in candidate["sources"]
                crossing_candidates.append({"orden": order, "vt": refined_v, "i": candidate_current,
                                            "tipo": "dI/dT + cruces entre barridos" if has_slope_crossing and len(candidate["sources"]) > 1 else
                                            "dI/dT" if has_slope_crossing else "cruce entre barridos",
                                            "cruces": ", ".join(dict.fromkeys(candidate["sources"])), "score": local_score,
                                            "stable_score": stable_score, "transition": transition,
                                            "slope": float(np.interp(refined_v, samples, slope)),
                                            "relative_error": float(np.interp(refined_v, samples, relative_error)),
                                            "slope_stability": slope_stability, "relative_stability": relative_stability,
                                            "spread_stability": spread_stability, "segment_score": segment_score,
                                            "segment_slope_stability": segment_slope_stability,
                                            "segment_relative_stability": segment_relative_stability,
                                            "segment_spread_stability": segment_spread_stability,
                                            "segment_start": float(segment_left), "segment_end": float(segment_right),
                                            "local_radius": float(local_radius)})
            if crossing_candidates:
                selected = min(crossing_candidates, key=lambda candidate: (candidate["stable_score"], candidate["orden"]))
                vt = float(selected["vt"])
    else:
        slope_component = np.zeros(len(samples))
        relative_component = np.zeros(len(samples))
        combined_score = np.zeros(len(samples))
    iztc = float(np.mean([np.interp(vt, values, current) for values, current in prepared]))
    error_at_vt = float(np.interp(vt, samples, relative_error))
    combined_at_vt = float(np.interp(vt, samples, combined_score))
    dispersion = pd.DataFrame({"v": samples, "dispersion": spread, "d_i_d_t": slope, "relative_error": relative_error, "slope_component": slope_component, "relative_component": relative_component, "combined_score": combined_score, "combined_score_at_vt": combined_at_vt})
    dispersion.attrs["crossing_candidates"] = crossing_candidates
    return ResultadoZTC(vt, iztc, len(curves), method, error_at_vt), dispersion
