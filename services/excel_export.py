from io import BytesIO

import pandas as pd
from openpyxl import Workbook

from database.repository import Repository


def export_excel(repository: Repository) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        repository.devices().to_excel(writer, index=False, sheet_name="Dispositivos")
        repository.campaigns().to_excel(writer, index=False, sheet_name="Campanas")
        repository.measurements().to_excel(writer, index=False, sheet_name="Mediciones")
        repository.ztc_results().to_excel(writer, index=False, sheet_name="Resultados ZTC")
        repository.all_points().to_excel(writer, index=False, sheet_name="Puntos V I")
    return output.getvalue()
