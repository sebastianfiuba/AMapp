from __future__ import annotations

import pandas as pd
import streamlit as st

from services.measurements import campaign_analysis_methods, temperature_measurements


METADATA_COLUMNS = ("fecha", "descripcion", "clase", "estado", "activa")


def measurement_view(frame: pd.DataFrame) -> pd.DataFrame:
    view = frame.copy()
    if "activa" not in view and "eliminado" in view:
        view["activa"] = view["eliminado"].eq(0)
    return view


def recalculate_campaigns(repository, campaign_ids: set[int]) -> None:
    for campaign_id in campaign_ids:
        active = temperature_measurements(repository.iv_measurements(campaign_id))
        try:
            campaign_analysis_methods(repository, campaign_id, active)
        except ValueError:
            repository.delete_ztc(campaign_id)
        st.session_state.pop(f"ztc_{campaign_id}", None)
        st.session_state.pop(f"ztc_dispersion_{campaign_id}", None)


def render_measurement_editor(repository, frame: pd.DataFrame, key: str) -> pd.DataFrame:
    view = measurement_view(frame)
    if view.empty:
        return view
    columns = [column for column in ("id", "dispositivo", "campana", "archivo", *METADATA_COLUMNS) if column in view]
    edit_mode = st.toggle("Modo edición de metadata", key=f"{key}_edit_mode")
    if not edit_mode:
        st.dataframe(view[columns], width="stretch", hide_index=True, column_config={"activa": st.column_config.CheckboxColumn("Activa")})
        return view
    editable = [column for column in METADATA_COLUMNS if column in view]
    edited = st.data_editor(
        view[columns],
        width="stretch",
        hide_index=True,
        disabled=[column for column in columns if column not in editable],
        column_config={"activa": st.column_config.CheckboxColumn("Activa", help="Si se desmarca, la medición queda eliminada lógicamente y no entra en gráficos ni cálculos.")},
        key=f"{key}_editor",
    )
    if st.button("Guardar metadata", type="primary", key=f"{key}_save"):
        original = view.set_index("id")
        changed_campaigns: set[int] = set()
        for row in edited.itertuples(index=False):
            old = original.loc[row.id]
            values = {column: getattr(row, column) for column in editable}
            if any(values[column] != old[column] for column in editable):
                repository.update_measurement_metadata(int(row.id), values)
                changed_campaigns.add(int(old.campana_id))
        recalculate_campaigns(repository, changed_campaigns)
        repository.connection.commit()
        st.success(f"Metadata guardada. ZTC recalculado en {len(changed_campaigns)} campaña(s).")
    return view