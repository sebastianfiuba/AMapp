import pandas as pd


def validate_points(points: pd.DataFrame) -> list[str]:
    errors = []
    if points.empty:
        errors.append("no hay puntos")
    for column in ("v", "i"):
        if column not in points.columns:
            errors.append(f"falta la columna {column}")
        elif not pd.to_numeric(points[column], errors="coerce").notna().all():
            errors.append(f"hay valores no numericos en {column}")
    if "v" in points and points["v"].duplicated().any():
        errors.append("hay tensiones duplicadas; se promediaran al analizar")
    return errors
