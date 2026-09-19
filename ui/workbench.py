import json
import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from services.measurements import extract_temperature, temperature_measurements
from ui.charts import CURVE_COLORS, campaign_context, chart_downloads, iv_chart, style_figure, track_chart
from ui.measurement_editor import recalculate_campaigns, render_measurement_editor
from ui.theme import banner
from ui.ztc import render_panel as render_ztc_panel


def _label(row):
    return f"ID {row.id} | {row.dispositivo} | {row.campana} | {row.archivo}"


def _measurement_details(repository, measurement_id: int) -> None:
    points = repository.points(measurement_id)
    if points.empty:
        st.info("La medición no tiene puntos.")
        return
    st.subheader("Características de la medición")
    details = pd.DataFrame({
        "Característica": ["Puntos", "Voltaje mínimo [V]", "Voltaje máximo [V]", "Corriente mínima [A]", "Corriente máxima [A]"],
        "Valor": [len(points), points.v.min(), points.v.max(), points.i.min(), points.i.max()],
    })
    st.dataframe(details, hide_index=True, width="stretch")
    st.dataframe(points, hide_index=True, width="stretch")


def _render_measurement_comparison(repository):
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
    measurements = repository.iv_measurements(include_deleted=True)
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
    active_labels = [label for label, measurement_id in measurement_labels.items() if bool(measurements.loc[measurements.id == measurement_id, "activa"].iloc[0])]
    selected_labels = st.multiselect("Mediciones seleccionadas", list(measurement_labels), default=active_labels, key="workbench_measurements")
    selected_ids = [measurement_labels[label] for label in selected_labels]
    selected_measurements = measurements[measurements.id.isin(selected_ids)]
    active_selected = selected_measurements[selected_measurements.activa.astype(bool)]
    st.caption(f"{len(active_selected)} curvas I-V activas seleccionadas")
    render_measurement_editor(repository, selected_measurements, "workbench_measurements")
    points = {int(row.id): repository.points(int(row.id)) for row in active_selected.itertuples()}
    iv_figure = iv_chart(active_selected, points)
    st.plotly_chart(iv_figure, width="stretch")
    st.download_button("Exportar gráfico I-V (HTML)", iv_figure.to_html(include_plotlyjs="cdn").encode("utf-8"), "comparacion_iv.html", "text/html", key="comparison_iv_export")
    if selected_ids:
        detail_label = st.selectbox("Previsualizar medición", selected_labels, key="workbench_measurement_detail")
        detail_id = measurement_labels[detail_label]
        detail_row = selected_measurements[selected_measurements.id == detail_id]
        if not detail_row.empty:
            st.dataframe(detail_row[["id", "dispositivo", "campana", "archivo", "fecha", "descripcion", "clase", "estado"]], hide_index=True, width="stretch")
            _measurement_details(repository, detail_id)

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
        st.data_editor(tracks[["id", "dispositivo", "campana", "medicion", "canal", "fecha"]], width="stretch", hide_index=True, disabled=True, key="workbench_track_table")
        st.plotly_chart(track_figure, width="stretch")
        st.download_button("Exportar Track Vt (HTML)", track_figure.to_html(include_plotlyjs="cdn").encode("utf-8"), "comparacion_track_vt.html", "text/html", key="comparison_track_export")
    save_name = st.text_input("Nombre de la vista", key="workbench_view_name")
    if st.button("Guardar vista", key="save_workbench_view") and save_name.strip():
        repository.save_workbench_view(save_name, {"devices": selected_device_ids, "campaigns": campaign_ids, "filter_text": filter_text, "states": filter_states, "date": filter_date})
        repository.connection.commit()
        st.success("Vista guardada.")


def _render_thermal_device_comparison(repository):
    st.subheader("Comparación automática de barridos térmicos")
    campaigns = repository.campaigns()
    devices = repository.devices()
    if campaigns.empty or devices.empty:
        st.info("Importa campañas de más de un dispositivo para comparar.")
        return
    device_options = {row.nombre: int(row.id) for row in devices.itertuples()}
    reference_name = st.selectbox("Dispositivo de referencia", list(device_options), key="thermal_reference_device")
    reference_id = device_options[reference_name]
    reference_campaigns = campaigns[campaigns.dispositivo_id == reference_id]
    reference_options = {f"{row.numero} (id {row.id})": int(row.id) for row in reference_campaigns.itertuples()}
    selected_reference = st.selectbox("Campaña térmica de referencia", list(reference_options), key="thermal_reference_campaign")
    reference_id_campaign = reference_options[selected_reference]
    reference_measurements = temperature_measurements(repository.iv_measurements(reference_id_campaign))
    if reference_measurements.empty:
        st.info("La campaña de referencia no tiene barridos térmicos identificables.")
        return
    other_ids = [value for name, value in device_options.items() if value != reference_id]
    selected_other = st.multiselect("Comparar con dispositivos", [name for name in device_options if name != reference_name], default=[name for name in device_options if name != reference_name], key="thermal_other_devices")
    selected_other_ids = [device_options[name] for name in selected_other]
    candidate_campaigns = campaigns[campaigns.dispositivo_id.isin(selected_other_ids)]
    candidate_rows = []
    for campaign in candidate_campaigns.itertuples():
        thermal = temperature_measurements(repository.iv_measurements(int(campaign.id)))
        if not thermal.empty:
            candidate_rows.append({"id": int(campaign.id), "dispositivo": campaign.dispositivo, "campaña": campaign.numero, "mediciones": len(thermal)})
    if not candidate_rows:
        st.info("No hay barridos térmicos en los otros dispositivos seleccionados.")
        return
    candidates = pd.DataFrame(candidate_rows)
    selected_candidates = st.multiselect("Campañas térmicas a comparar", [f"{row.dispositivo} | {row.campaña} (id {row.id})" for row in candidates.itertuples()], default=[f"{row.dispositivo} | {row.campaña} (id {row.id})" for row in candidates.itertuples()], key="thermal_candidate_campaigns")
    selected_campaign_ids = [int(label.rsplit("id ", 1)[1].rstrip(")")) for label in selected_candidates]
    selected_campaign_ids.append(reference_id_campaign)
    figure = go.Figure()
    rows = []
    for campaign_id in selected_campaign_ids:
        campaign = campaigns[campaigns.id == campaign_id].iloc[0]
        thermal = temperature_measurements(repository.iv_measurements(campaign_id))
        for measurement in thermal.itertuples():
            points = repository.points(int(measurement.id))
            temperature = extract_temperature(measurement)
            context = campaign_context(campaign.numero)
            label = f"{campaign.dispositivo} | {campaign.numero} | {context} | {measurement.archivo} | {temperature:g} °C" if temperature is not None else f"{campaign.dispositivo} | {campaign.numero} | {context} | {measurement.archivo}"
            figure.add_trace(go.Scatter(x=points.v, y=points.i, mode="lines", name=label))
        rows.append({"dispositivo": campaign.dispositivo, "campaña": campaign.numero, "barridos térmicos": len(thermal)})
    style_figure(figure)
    figure.update_layout(xaxis_title="Voltaje [V]", yaxis_title="Corriente [A]", hovermode="x unified", legend_title="Dispositivo | Campaña | Medición | Temperatura")
    st.plotly_chart(figure, width="stretch")
    st.download_button("Exportar comparación térmica (HTML)", figure.to_html(include_plotlyjs="cdn").encode("utf-8"), "comparacion_barridos_termicos.html", "text/html", key="thermal_comparison_export")
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


def _render_comparison(repository):
    search_tab, thermal_tab = st.tabs(["Buscador I-V y Track Vt", "Barridos térmicos entre dispositivos"])
    with search_tab:
        _render_measurement_comparison(repository)
    with thermal_tab:
        _render_thermal_device_comparison(repository)


def _render_device(repository):
    st.subheader("Workbench de dispositivo")
    devices = repository.devices()
    if devices.empty:
        st.info("Importa datos para explorar un dispositivo.")
        return
    device_options = {row.nombre: int(row.id) for row in devices.itertuples()}
    selected = st.selectbox("Dispositivo", list(device_options))
    device_id = device_options[selected]
    measurements = repository.measurements_for_devices([device_id], include_deleted=True)
    tracks = repository.tracks(device_id=device_id)
    st.metric("Mediciones I-V", len(measurements))
    st.metric("Tracks Vt", len(tracks))
    if not measurements.empty:
        render_measurement_editor(repository, measurements, "workbench_device_measurements")
    if not tracks.empty:
        st.dataframe(tracks[["id", "campana", "archivo", "canal", "fecha", "source_sheet"]], width="stretch", hide_index=True)
        selected_track = st.selectbox("Medición Track Vt", tracks.apply(_label, axis=1).tolist())
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
    measurements = repository.iv_measurements(include_deleted=True)
    if measurements.empty:
        st.info("No hay mediciones I-V para asociar.")
        return
    st.caption("Edita el destino de varias mediciones y guarda todas las asociaciones juntas.")
    measurements = measurements.copy()
    measurements["clave"] = measurements.apply(lambda row: re.sub(r"\.ri$", "", str(row.archivo), flags=re.IGNORECASE).lower(), axis=1)
    measurements["campana_destino"] = measurements["campana"]
    edited = st.data_editor(measurements[["id", "dispositivo", "campana", "archivo", "fecha", "clave", "activa", "campana_destino"]], width="stretch", hide_index=True, disabled=["id", "dispositivo", "campana", "archivo", "fecha", "clave"], column_config={"activa": st.column_config.CheckboxColumn("Activa", help="Desmarcar excluye esta medición de gráficos y cálculos.")})
    if st.button("Guardar matching masivo", type="primary"):
        errors = []
        changed_campaigns = set()
        for row in edited.itertuples():
            original = measurements.loc[measurements.id == row.id].iloc[0]
            campaigns = repository.campaigns(int(original.dispositivo_id))
            match = campaigns[campaigns.numero.astype(str) == str(row.campana_destino).strip()]
            if match.empty:
                errors.append(f"{row.archivo}: campaña no encontrada: {row.campana_destino}")
            else:
                repository.update_measurement_metadata(int(row.id), {"campana_id": int(match.iloc[0].id), "activa": bool(row.activa)})
                changed_campaigns.update({int(original.campana_id), int(match.iloc[0].id)})
        repository.connection.commit()
        recalculate_campaigns(repository, changed_campaigns)
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
    if not selected:
        st.info("Selecciona mediciones del mismo dispositivo.")
        return
    rows = []
    selected_frames = []
    for label in selected:
        measurement_id = options[label]
        points = repository.points(measurement_id).sort_values("i").drop_duplicates(subset=["i"])
        selected_frames.append((measurement_id, points))
        if len(points) < 2 or target_current < points.i.min() or target_current > points.i.max():
            st.warning(f"{label}: la corriente objetivo queda fuera del rango medido.")
            continue
        voltage = float(np.interp(target_current, points.i.to_numpy(), points.v.to_numpy()))
        rows.append({"medicion": label, "VT a corriente objetivo [V]": voltage})
    if not rows:
        return
    result = pd.DataFrame(rows)
    result["delta VT respecto de la primera [V]"] = result.iloc[:, 1] - result.iloc[0, 1]
    preview = measurements[measurements.id.isin([measurement_id for measurement_id, _ in selected_frames])]
    figure = iv_chart(preview, {measurement_id: points for measurement_id, points in selected_frames})
    for row in result.itertuples():
        figure.add_trace(go.Scatter(x=[row[1]], y=[target_current], mode="markers", marker={"size": 11, "symbol": "x"}, name=f"Corriente elegida | {row[0]}"))
        figure.add_vline(x=row[1], line_dash="dot", line_color="rgba(190, 50, 50, 0.55)")
        figure.add_hline(y=target_current, line_dash="dot", line_color="rgba(50, 90, 190, 0.55)")
    st.subheader("Previsualización de dosis absorbida")
    st.plotly_chart(figure, width="stretch")
    st.download_button("Exportar gráfico de dosis (HTML)", figure.to_html(include_plotlyjs="cdn").encode("utf-8"), "dosis_absorbida.html", "text/html", key="dose_export")
    st.dataframe(result, width="stretch", hide_index=True)


def render(repository, include_ztc: bool = True):
    banner("Mesa de trabajo", "Workbench", "Armá comparaciones, revisá un dispositivo y conectá campañas con la base.")
    tab_names = ["Comparador", "Dispositivo", "Matching", "Dosis absorbida"]
    if include_ztc:
        tab_names.append("Análisis ZTC")
    tabs = st.tabs(tab_names)
    comparison, device, matching, dose = tabs[:4]
    with comparison:
        _render_comparison(repository)
    with device:
        _render_device(repository)
    with matching:
        _render_matching(repository)
    with dose:
        _render_absorbed_dose(repository)


def render_manual(repository):
    render(repository, include_ztc=False)