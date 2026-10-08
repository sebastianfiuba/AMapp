import streamlit as st
import pandas as pd

from ui.charts import chart_downloads, iv_chart
from ui.measurement_editor import recalculate_campaigns, render_measurement_editor
from ui.track_vt import render_panel as render_track_panel
from ui.theme import banner
from services.measurements import iv_measurement_noise_flags


def render_iv_panel(repository):
    devices = repository.devices()
    if devices.empty:
        st.info("Todavia no hay dispositivos cargados.")
        return
    device_options = {row.nombre: int(row.id) for row in devices.itertuples()}
    selected_devices = st.multiselect("Dispositivos", list(device_options), default=list(device_options)[:1], key="measurements_devices")
    device_ids = [device_options[name] for name in selected_devices]
    campaigns = repository.campaigns()
    campaigns = campaigns[campaigns.dispositivo_id.isin(device_ids)]
    campaign_options = {f"{row.dispositivo} | {row.numero}": int(row.id) for row in campaigns.itertuples()}
    selected_campaigns = st.multiselect("Campañas", list(campaign_options), default=list(campaign_options)[:1], key="measurements_campaigns")
    campaign_ids = [campaign_options[label] for label in selected_campaigns]
    measurements = repository.iv_measurements(include_deleted=True, include_unaccepted=True)
    measurements = measurements[measurements.dispositivo_id.isin(device_ids) & measurements.campana_id.isin(campaign_ids)]
    search_text = st.text_input("Buscar mediciones", placeholder="Archivo, dispositivo, campaña o metadata", key="measurements_search")
    state_filter = st.selectbox("Estado", ["Todas", "Activas", "Eliminadas"], key="measurements_state_filter")
    acceptance_filter = st.selectbox("Aceptación", ["Todas", "Aceptadas", "No aceptadas"], key="measurements_acceptance_filter")
    if search_text:
        searchable = measurements.fillna("").astype(str).agg(" ".join, axis=1)
        measurements = measurements[searchable.str.contains(search_text, case=False, regex=False)]
    if state_filter == "Activas":
        measurements = measurements[measurements.activa.astype(bool)]
    elif state_filter == "Eliminadas":
        measurements = measurements[~measurements.activa.astype(bool)]
    if acceptance_filter == "Aceptadas":
        measurements = measurements[measurements.aceptada.astype(bool)]
    elif acceptance_filter == "No aceptadas":
        measurements = measurements[~measurements.aceptada.astype(bool)]
    if measurements.empty:
        st.info("No hay mediciones que coincidan con los filtros.")
        return
    active_measurements = measurements[measurements.activa.astype(bool) & measurements.aceptada.astype(bool)]
    active_points = {int(row.id): repository.points(int(row.id)) for row in active_measurements.itertuples()}
    noise_flags = iv_measurement_noise_flags(active_measurements, active_points)
    measurements = measurements.merge(noise_flags, on="id", how="left")
    measurements["control_iv"] = measurements["control_iv"].fillna("Inactiva")
    only_flagged = st.checkbox("Mostrar solo mediciones con ruido exagerado", key="measurements_noise_filter")
    if only_flagged:
        measurements = measurements[measurements.control_iv == "REVISAR ruido"]
    flagged_count = int((noise_flags.control_iv == "REVISAR ruido").sum())
    st.caption(f"{len(measurements)} medición(es) visibles; {flagged_count} con posible ruido aleatorio. Alerta automática, requiere revisión.")
    if measurements.empty:
        st.info("No hay mediciones marcadas con ruido exagerado.")
        return
    render_measurement_editor(repository, measurements, "measurements_iv")
    measurement_options = {f"{row.dispositivo} | {row.campana} | {row.archivo}": int(row.id) for row in measurements.itertuples()}
    active_labels = [label for label, measurement_id in measurement_options.items()
                     if bool(measurements.loc[measurements.id == measurement_id, "activa"].iloc[0])
                     and bool(measurements.loc[measurements.id == measurement_id, "aceptada"].iloc[0])]
    selected_measurements = st.multiselect("Mediciones activas para la vista previa", list(measurement_options), default=active_labels[:3], key="measurements_preview")
    selected_ids = {measurement_options[label] for label in selected_measurements}
    preview = measurements[measurements.id.isin(selected_ids) & measurements.activa.astype(bool) & measurements.aceptada.astype(bool)]
    if preview.empty:
        st.info("Selecciona al menos una medición para previsualizar.")
        return
    points = {int(row.id): repository.points(int(row.id)) for row in preview.itertuples()}
    figure = iv_chart(preview, points)
    st.subheader("Vista previa")
    st.plotly_chart(figure, width="stretch")
    chart_downloads(figure, "mediciones_seleccionadas", "measurements_preview")
    st.dataframe(preview[["dispositivo", "campana", "archivo", "fecha", "descripcion", "clase", "estado", "observaciones", "aceptada", "caso_no_aceptacion"]], width="stretch", hide_index=True)
    selected = st.selectbox("Detalle de medición", list(measurement_options), key="measurement_detail")
    row = measurements[measurements.id == measurement_options[selected]].iloc[0]
    st.dataframe(row[["dispositivo", "campana", "archivo", "fecha", "descripcion", "clase", "estado", "observaciones", "aceptada", "caso_no_aceptacion"]].to_frame("Valor"), width="stretch")
    active = bool(row.activa)
    action = "Desactivar medición" if active else "Restaurar medición"
    if st.button(action, key="measurements_toggle_deleted"):
        campaign_id = repository.set_measurement_deleted(int(row.id), not active)
        if campaign_id is not None:
            recalculate_campaigns(repository, {campaign_id})
            repository.connection.commit()
            st.success("Medición desactivada; se conservan puntos y metadata." if active else "Medición restaurada.")
            st.rerun()
    observation_value = "" if pd.isna(row.observaciones) else str(row.observaciones)
    observations = st.text_area("Observaciones", value=observation_value, key=f"measurement_observations_{row.id}")
    if st.button("Guardar observaciones", key=f"save_measurement_observations_{row.id}"):
        repository.update_measurement_metadata(int(row.id), {"observaciones": observations})
        repository.connection.commit()
        st.success("Observaciones guardadas.")
        st.rerun()
    detail_points = repository.points(int(row.id))
    detail_figure = iv_chart(measurements[measurements.id == row.id], {int(row.id): detail_points})
    detail_figure.update_layout(height=720, margin={"l": 70, "r": 40, "t": 45, "b": 80}, legend={"orientation": "h", "y": -0.2})
    st.plotly_chart(detail_figure, width="stretch", key="measurement_detail_chart")
    st.subheader("Editor de raw data V/I")
    edited_points = st.data_editor(detail_points, num_rows="dynamic", width="stretch", hide_index=True, key="measurement_raw_editor")
    if st.button("Guardar raw data", type="primary", key="save_measurement_raw"):
        try:
            repository.replace_points(int(row.id), edited_points)
            recalculate_campaigns(repository, {int(row.campana_id)})
            repository.connection.commit()
            st.success("Raw data guardado sin eliminar la medición.")
            st.rerun()
        except ValueError as error:
            st.error(str(error))


def _render_acceptance_panel(repository):
    measurements = repository.measurements()
    st.subheader("Revisión de aceptación")
    if measurements.empty:
        st.info("Todavía no hay mediciones para revisar.")
        return

    options = {
        f"ID {row.id} | {row.dispositivo} | {row.campana} | {row.archivo}": int(row.id)
        for row in measurements.itertuples()
    }
    selected = st.multiselect("Mediciones a rechazar", list(options), key="acceptance_reject_selection")
    case_name = st.text_input("Caso de no aceptación", placeholder="Ej.: ruido alto, contacto inestable")
    if st.button("Marcar como no aceptadas", disabled=not selected or not case_name.strip(), type="primary"):
        measurement_ids = [options[label] for label in selected]
        campaign_ids = set(measurements.loc[measurements.id.isin(measurement_ids), "campana_id"].astype(int))
        repository.set_measurements_acceptance(measurement_ids, False, case_name)
        recalculate_campaigns(repository, campaign_ids)
        repository.connection.commit()
        st.rerun()

    rejected = measurements[~measurements.aceptada.fillna(1).astype(bool)].copy()
    st.subheader("Mediciones no aceptadas por caso")
    if rejected.empty:
        st.info("No hay mediciones no aceptadas.")
        return
    rejected["caso"] = rejected.caso_no_aceptacion.fillna("").str.strip().replace("", "Sin caso")
    for case, case_measurements in rejected.groupby("caso", sort=True):
        with st.expander(f"{case} ({len(case_measurements)})"):
            st.dataframe(case_measurements[["id", "dispositivo", "campana", "archivo", "fecha", "observaciones"]],
                         width="stretch", hide_index=True)

    rejected_options = {
        f"ID {row.id} | {row.dispositivo} | {row.campana} | {row.archivo}": int(row.id)
        for row in rejected.itertuples()
    }
    restore = st.multiselect("Mediciones a reaceptar", list(rejected_options), key="acceptance_restore_selection")
    if st.button("Marcar como aceptadas", disabled=not restore):
        measurement_ids = [rejected_options[label] for label in restore]
        campaign_ids = set(measurements.loc[measurements.id.isin(measurement_ids), "campana_id"].astype(int))
        repository.set_measurements_acceptance(measurement_ids, True)
        recalculate_campaigns(repository, campaign_ids)
        repository.connection.commit()
        st.rerun()


def render(repository):
    banner("Explorador", "Mediciones", "Consultá curvas I-V y mediciones Track Vt desde una sola sección.")
    iv_tab, track_tab, acceptance_tab = st.tabs(["I-V", "Track Vt", "Aceptación"])
    with iv_tab:
        render_iv_panel(repository)
    with track_tab:
        render_track_panel(repository)
    with acceptance_tab:
        _render_acceptance_panel(repository)
