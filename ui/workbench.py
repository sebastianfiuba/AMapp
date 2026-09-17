import json
import re

import numpy as np
import pandas as pd
import streamlit as st

from ui.charts import chart_downloads, iv_chart, track_chart
from ui.theme import banner
from ui.ztc import render_panel as render_ztc_panel


def _label(row):
    return f"{row.dispositivo} | {row.campana} | {row.archivo}"


def _render_comparison(repository):
    st.subheader("Comparador")
    devices = repository.devices()
    campaigns = repository.campaigns()
    if devices.empty:
        st.info("Importa datos para comenzar a comparar.")
        return
    views = repository.workbench_views()
    view_names = ["(sin vista guardada)"] + views.nombre.tolist()
    selected_view = st.selectbox("Vista guardada", view_names)
    loaded = {}
    if selected_view != "(sin vista guardada)":
        loaded = json.loads(views.loc[views.nombre == selected_view, "configuracion"].iloc[0])
    device_options = {f"{row.nombre} (id {row.id})": int(row.id) for row in devices.itertuples()}
    default_devices = [label for label, value in device_options.items() if value in loaded.get("devices", [])] or list(device_options)[:2]
    selected_devices = st.multiselect("Dispositivos", list(device_options), default=default_devices, key="workbench_devices")
    selected_device_ids = [device_options[label] for label in selected_devices]
    campaign_options = {f"{row.dispositivo} | {row.numero} (id {row.id})": int(row.id) for row in campaigns[campaigns.dispositivo_id.isin(selected_device_ids)].itertuples()}
    default_campaigns = [label for label, value in campaign_options.items() if value in loaded.get("campaigns", [])]
    selected_campaigns = st.multiselect("Campañas", list(campaign_options), default=default_campaigns, key="workbench_campaigns")
    campaign_ids = [campaign_options[label] for label in selected_campaigns]
    measurements = repository.iv_measurements()
    measurements = measurements[measurements.dispositivo_id.isin(selected_device_ids)]
    if campaign_ids:
        measurements = measurements[measurements.campana_id.isin(campaign_ids)]
    filter_text = st.text_input("Buscar en todas las columnas", value=loaded.get("filter_text", ""))
    device_filter = st.multiselect("Dispositivo", sorted(measurements.dispositivo.unique()), key="workbench_device_filter") if not measurements.empty else []
    campaign_filter = st.multiselect("Campaña", sorted(measurements.campana.unique()), key="workbench_campaign_filter") if not measurements.empty else []
    state_options = sorted(measurements["estado"].dropna().astype(str).unique()) if not measurements.empty else []
    filter_states = st.multiselect("Estados", state_options, default=[state for state in loaded.get("states", []) if state in state_options])
    filter_date = st.text_input("Filtro de fecha", value=loaded.get("date", ""), placeholder="Ej.: 2025-03")
    class_options = sorted(measurements["clase"].dropna().astype(str).unique()) if not measurements.empty else []
    filter_classes = st.multiselect("Clase", class_options, key="workbench_classes")
    if filter_text:
        searchable = measurements.fillna("").astype(str).agg(" ".join, axis=1)
        measurements = measurements[searchable.str.contains(filter_text, case=False, regex=False)]
    if device_filter:
        measurements = measurements[measurements.dispositivo.isin(device_filter)]
    if campaign_filter:
        measurements = measurements[measurements.campana.isin(campaign_filter)]
    if filter_states:
        measurements = measurements[measurements.estado.astype(str).isin(filter_states)]
    if filter_classes:
        measurements = measurements[measurements.clase.astype(str).isin(filter_classes)]
    if filter_date:
        measurements = measurements[measurements.fecha.astype(str).str.contains(filter_date, case=False, regex=False)]
    if measurements.empty:
        st.info("Selecciona al menos un dispositivo o campaña con mediciones.")
        return
    measurement_labels = {f"{row.dispositivo} | {row.campana} | {row.archivo} (id {row.id})": int(row.id) for row in measurements.itertuples()}
    selected_labels = st.multiselect("Mediciones seleccionadas", list(measurement_labels), default=list(measurement_labels), key="workbench_measurements")
    selected_ids = [measurement_labels[label] for label in selected_labels]
    measurements = measurements[measurements.id.isin(selected_ids)]
    st.caption(f"{len(measurements)} curvas I-V seleccionadas")
    left, right = st.columns([1.35, 1], gap="large")
    with left:
        st.data_editor(measurements[["id", "dispositivo", "campana", "archivo", "fecha", "clase", "estado"]], width="stretch", hide_index=True, disabled=True, key="workbench_measurement_table")
    with right:
        points = {int(row.id): repository.points(int(row.id)) for row in measurements.itertuples()}
        iv_figure = iv_chart(measurements, points)
        st.plotly_chart(iv_figure, width="stretch")
        st.download_button("Exportar gráfico I-V (HTML)", iv_figure.to_html(include_plotlyjs="cdn").encode("utf-8"), "comparacion_iv.html", "text/html", key="comparison_iv_export")

    track_frames = []
    for device_id in selected_device_ids:
        track_frame = repository.tracks(device_id=device_id, campaign_ids=campaign_ids or None)
        if not track_frame.empty:
            track_frames.append(track_frame)
    tracks = pd.concat(track_frames, ignore_index=True) if track_frames else pd.DataFrame()
    if not tracks.empty:
        channel_options = sorted(tracks.canal.dropna().astype(str).unique())
        selected_channels = st.multiselect("Canal de medición", channel_options, default=channel_options, key="workbench_track_channels")
        if selected_channels:
            tracks = tracks[tracks.canal.astype(str).isin(selected_channels)]
    if not tracks.empty:
        st.subheader("Track Vt de la misma selección")
        track_points = {int(row.id): repository.track_points(int(row.id)) for row in tracks.itertuples()}
        track_figure = track_chart(tracks, track_points)
        track_left, track_right = st.columns([1.35, 1], gap="large")
        with track_left:
            st.data_editor(tracks[["id", "dispositivo", "campana", "archivo", "canal", "fecha"]], width="stretch", hide_index=True, disabled=True, key="workbench_track_table")
        with track_right:
            st.plotly_chart(track_figure, width="stretch")
            st.download_button("Exportar Track Vt (HTML)", track_figure.to_html(include_plotlyjs="cdn").encode("utf-8"), "comparacion_track_vt.html", "text/html", key="comparison_track_export")
    save_name = st.text_input("Nombre de la vista", key="workbench_view_name")
    if st.button("Guardar vista", key="save_workbench_view") and save_name.strip():
        repository.save_workbench_view(save_name, {"devices": selected_device_ids, "campaigns": campaign_ids, "filter_text": filter_text, "states": filter_states, "date": filter_date})
        repository.connection.commit()
        st.success("Vista guardada.")


def _render_device(repository):
    st.subheader("Workbench de dispositivo")
    devices = repository.devices()
    if devices.empty:
        st.info("Importa datos para explorar un dispositivo.")
        return
    device_options = {row.nombre: int(row.id) for row in devices.itertuples()}
    selected = st.selectbox("Dispositivo", list(device_options))
    device_id = device_options[selected]
    measurements = repository.measurements_for_devices([device_id])
    tracks = repository.tracks(device_id=device_id)
    st.metric("Mediciones I-V", len(measurements))
    st.metric("Tracks Vt", len(tracks))
    if not measurements.empty:
        st.dataframe(measurements[["campana", "archivo", "fecha", "descripcion", "clase", "estado"]], width="stretch", hide_index=True)
    if not tracks.empty:
        st.dataframe(tracks[["campana", "archivo", "canal", "fecha", "source_sheet"]], width="stretch", hide_index=True)
        selected_track = st.selectbox("Track Vt", tracks.apply(_label, axis=1).tolist())
        track = tracks.iloc[tracks.apply(_label, axis=1).tolist().index(selected_track)]
        selected_points = repository.track_points(int(track.id))
        st.metric("Duración [s]", f"{selected_points.t.max():.1f}" if not selected_points.empty else "-")
        st.metric("Deriva Vt [V]", f"{selected_points.vt.iloc[-1] - selected_points.vt.iloc[0]:.6g}" if len(selected_points) > 1 else "-")
        figure = track_chart(tracks[tracks.id == track.id], {int(track.id): selected_points})
        st.plotly_chart(figure, width="stretch")
        chart_downloads(figure, "track_vt", "device_track")
    st.divider()
    st.subheader("Editar nombres")
    with st.form("rename_device"):
        new_name = st.text_input("Nombre del dispositivo", value=selected)
        if st.form_submit_button("Guardar dispositivo") and new_name.strip() and new_name.strip() != selected:
            repository.rename_device(device_id, new_name)
            repository.connection.commit()
            st.success("Dispositivo actualizado.")
    campaigns = repository.campaigns(device_id)
    if not campaigns.empty:
        campaign_label = st.selectbox("Campaña a editar", [f"{row.numero} (id {row.id})" for row in campaigns.itertuples()])
        campaign_row = campaigns.iloc[[f"{row.numero} (id {row.id})" for row in campaigns.itertuples()].index(campaign_label)]
        new_campaign = st.text_input("Nombre de campaña", value=str(campaign_row.numero))
        if st.button("Guardar campaña") and new_campaign.strip() and new_campaign.strip() != str(campaign_row.numero):
            repository.rename_campaign(int(campaign_row.id), new_campaign)
            repository.connection.commit()
            st.success("Campaña actualizada.")


def _render_matching(repository):
    st.subheader("Matching y agrupación")
    measurements = repository.iv_measurements()
    if measurements.empty:
        st.info("No hay mediciones I-V para asociar.")
        return
    st.caption("Edita el destino de varias mediciones y guarda todas las asociaciones juntas.")
    measurements = measurements.copy()
    measurements["clave"] = measurements.apply(lambda row: re.sub(r"\.ri$", "", str(row.archivo), flags=re.IGNORECASE).lower(), axis=1)
    measurements["campana_destino"] = measurements["campana"]
    edited = st.data_editor(measurements[["id", "dispositivo", "campana", "archivo", "fecha", "clave", "campana_destino"]], width="stretch", hide_index=True, disabled=["id", "dispositivo", "campana", "archivo", "fecha", "clave"])
    if st.button("Guardar matching masivo", type="primary"):
        errors = []
        for row in edited.itertuples():
            campaigns = repository.campaigns(int(measurements.loc[measurements.id == row.id, "dispositivo_id"].iloc[0]))
            match = campaigns[campaigns.numero.astype(str) == str(row.campana_destino).strip()]
            if match.empty:
                errors.append(f"{row.archivo}: campaña no encontrada: {row.campana_destino}")
            else:
                repository.update_measurement_metadata(int(row.id), {"campana_id": int(match.iloc[0].id)})
        repository.connection.commit()
        if errors:
            st.warning("Algunas asociaciones no se guardaron.")
            st.dataframe(pd.DataFrame({"error": errors}), hide_index=True)
        else:
            st.success("Matching guardado en la base.")
    output = edited.to_csv(index=False).encode("utf-8")
    st.download_button("Exportar matching CSV", output, "matching_excel_base.csv", "text/csv")

    st.divider()
    st.subheader("Agrupar I-V con Track Vt")
    st.caption("Las mediciones y tracks de un grupo deben pertenecer al mismo dispositivo.")
    devices = repository.devices()
    device_options = {row.nombre: int(row.id) for row in devices.itertuples()}
    selected_device = st.selectbox("Dispositivo del grupo", list(device_options), key="group_device")
    device_id = device_options[selected_device]
    group_measurements = repository.iv_measurements()
    group_measurements = group_measurements[group_measurements.dispositivo_id == device_id]
    group_tracks = repository.tracks(device_id=device_id)
    measurement_options = {f"{row.campana} | {row.archivo}": int(row.id) for row in group_measurements.itertuples()}
    track_options = {f"{row.campana} | {row.canal} | {row.archivo}": int(row.id) for row in group_tracks.itertuples()}
    selected_group_measurements = st.multiselect("Mediciones I-V", list(measurement_options), key="group_measurements")
    selected_group_tracks = st.multiselect("Tracks Vt", list(track_options), key="group_tracks")
    group_name = st.text_input("Nombre del grupo", key="group_name")
    if st.button("Guardar grupo", type="primary", key="save_measurement_group"):
        try:
            repository.save_measurement_group(
                group_name,
                [measurement_options[label] for label in selected_group_measurements],
                [track_options[label] for label in selected_group_tracks],
            )
            repository.connection.commit()
            st.success("Grupo guardado.")
        except ValueError as error:
            st.error(str(error))
    groups = repository.measurement_groups()
    if not groups.empty:
        selected_group = st.selectbox("Grupo guardado", groups.nombre.tolist(), key="saved_group")
        group_id = int(groups.loc[groups.nombre == selected_group, "id"].iloc[0])
        st.dataframe(repository.group_measurements(group_id), width="stretch", hide_index=True)
        st.dataframe(repository.group_tracks(group_id), width="stretch", hide_index=True)


def _render_absorbed_dose(repository):
    st.subheader("Dosis absorbida")
    st.caption("Prototipo: compara varias mediciones del mismo dispositivo a una corriente objetivo.")
    devices = repository.devices()
    if devices.empty:
        st.info("Importa datos para analizar dosis absorbida.")
        return
    device_options = {row.nombre: int(row.id) for row in devices.itertuples()}
    selected_device = st.selectbox("Dispositivo", list(device_options), key="dose_device")
    measurements = repository.iv_measurements()
    measurements = measurements[measurements.dispositivo_id == device_options[selected_device]]
    if measurements.empty:
        st.info("El dispositivo no tiene mediciones I-V.")
        return
    options = {f"{row.campana} | {row.archivo}": int(row.id) for row in measurements.itertuples()}
    selected = st.multiselect("Mediciones", list(options), default=list(options)[:2], key="dose_measurements")
    target_current = st.number_input("Corriente objetivo [A]", value=0.00017, format="%.8g", key="dose_current")
    if len(selected) < 2:
        st.info("Selecciona al menos dos mediciones del mismo dispositivo.")
        return
    rows = []
    for label in selected:
        measurement_id = options[label]
        points = repository.points(measurement_id).sort_values("i")
        if len(points) < 2 or target_current < points.i.min() or target_current > points.i.max():
            st.warning(f"{label}: la corriente objetivo queda fuera del rango medido.")
            continue
        voltage = float(np.interp(target_current, points.i.to_numpy(), points.v.to_numpy()))
        rows.append({"medicion": label, "VT a corriente objetivo [V]": voltage})
    if len(rows) < 2:
        return
    result = pd.DataFrame(rows)
    result["delta VT respecto de la primera [V]"] = result.iloc[:, 1] - result.iloc[0, 1]
    st.dataframe(result, width="stretch", hide_index=True)


def render(repository):
    banner("Mesa de trabajo", "Workbench", "Armá comparaciones, revisá un dispositivo y conectá campañas con la base.")
    comparison, device, matching, dose, ztc = st.tabs(["Comparador", "Dispositivo", "Matching", "Dosis absorbida", "Análisis ZTC"])
    with comparison:
        _render_comparison(repository)
    with device:
        _render_device(repository)
    with matching:
        _render_matching(repository)
    with dose:
        _render_absorbed_dose(repository)
    with ztc:
        render_ztc_panel(repository)