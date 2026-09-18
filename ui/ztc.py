import json

import numpy as np
import plotly.graph_objects as go
import streamlit as st
import pandas as pd

from services.measurements import campaign_analysis_methods, extract_temperature, individual_result, temperature_measurements
from ui.charts import campaign_context, iv_chart
from ui.theme import banner
from utils.helpers import format_current


def campaign_label(row) -> str:
    treatment = str(row.numero)
    return f"{row.dispositivo} | {treatment}"


def render(repository):
    banner("Punto de operación", "Análisis ZTC", "Compará el desplazamiento de VT e I entre campañas. ZTC usa únicamente curvas I-V.", "ztc")
    _render_analysis(repository)


def render_panel(repository):
    st.subheader("Análisis ZTC")
    st.caption("Solo se pueden analizar barridos identificados como mediciones de temperatura.")
    _render_analysis(repository)


def _render_analysis(repository):
    campaigns = repository.campaigns()
    if campaigns.empty:
        st.info("Todavia no hay campanas cargadas.")
        return
    devices = repository.devices()
    device_labels = devices.nombre.tolist()
    manual_tab, automatic_tab = st.tabs(["Análisis manual", "Análisis automático"])
    with manual_tab:
        selected_device = st.selectbox("Dispositivo", device_labels, key="ztc_devices")
        device_id = int(devices.loc[devices.nombre == selected_device, "id"].iloc[0])
        manual_campaigns = campaigns[campaigns.dispositivo_id == device_id]
        thermal_campaign_ids = {
            int(campaign_id)
            for campaign_id in manual_campaigns.id
            if not temperature_measurements(repository.iv_measurements(int(campaign_id))).empty
        }
        manual_campaigns = manual_campaigns[manual_campaigns.id.isin(thermal_campaign_ids)]
        if manual_campaigns.empty:
            st.info("No hay campañas con barridos de temperatura para el dispositivo seleccionado.")
        else:
            labels = [campaign_label(row) for row in manual_campaigns.itertuples()]
            tab_single, tab_evolution = st.tabs(["Una campaña", "Evolución y secuencia"])
            with tab_single:
                selected = st.selectbox("Campaña", labels, key="ztc_single_campaign")
                campaign = manual_campaigns.iloc[labels.index(selected)]
                _render_campaign(repository, campaign, int(campaign.id))
            with tab_evolution:
                _render_evolution(repository, manual_campaigns, labels)
    with automatic_tab:
        _render_device_comparison(repository)


def _render_campaign(repository, campaign, campaign_id: int):
    measurements = temperature_measurements(repository.iv_measurements(campaign_id))
    st.caption(f"{len(measurements)} medicion(es) disponibles")
    if st.button("Calcular / actualizar ZTC", type="primary"):
        try:
            result, dispersion = campaign_analysis_methods(repository, campaign_id, measurements)
            st.session_state[f"ztc_{campaign_id}"] = result
            st.session_state[f"ztc_dispersion_{campaign_id}"] = dispersion
            st.success("Analisis guardado.")
        except ValueError as error:
            st.error(str(error))
    result = st.session_state.get(f"ztc_{campaign_id}")
    stored = repository.ztc_results()
    if result is None and not stored.empty and campaign_id in stored.campana_id.values:
        row = stored[stored.campana_id == campaign_id].iloc[0]
        result = {"vt_ztc": row.vt_ztc, "i_ztc": row.i_ztc, "cantidad_mediciones": len(measurements),
                  "combined": {"vt_ztc": row.vt_ztc, "i_ztc": row.i_ztc},
                  "didt": {"vt_ztc": row.vt_ztc, "i_ztc": row.i_ztc}, "relative": {"vt_ztc": row.vt_ztc, "i_ztc": row.i_ztc}}
    if result:
        left, middle, right = st.columns(3)
        with left:
            st.metric("VT ZTC | combinado", f"{result['combined']['vt_ztc']:.6g} V")
            st.metric("I ZTC | combinado", format_current(result["combined"]["i_ztc"]))
        with middle:
            st.metric("VT ZTC | dI/dT", f"{result['didt']['vt_ztc']:.6g} V")
            st.metric("I ZTC | dI/dT", format_current(result["didt"]["i_ztc"]))
        with right:
            st.metric("VT ZTC | error relativo", f"{result['relative']['vt_ztc']:.6g} V")
            st.metric("I ZTC | error relativo", format_current(result["relative"]["i_ztc"]))
        st.caption(f"Dispersión relativa en dI/dT: {result.get('error_relativo', 0):.3%}")
        points = {int(row.id): repository.points(int(row.id)) for row in measurements.itertuples()}
        figure = go.Figure()
        colors = ["#0c7285", "#bd7b19", "#c34d46", "#4f6d7a", "#6b5b95", "#4d8b5f"]
        for index, measurement in enumerate(measurements.itertuples()):
            curve = points[int(measurement.id)]
            temperature = extract_temperature(measurement)
            context = campaign_context(campaign.numero)
            figure.add_trace(go.Scatter(x=curve.v, y=curve.i, mode="lines+markers", line={"color": colors[index % len(colors)]},
                                         name=f"{context} | {measurement.archivo} | {temperature:g} °C" if temperature is not None else f"{context} | {measurement.archivo}"))
        figure.add_trace(go.Scatter(x=[result["combined"]["vt_ztc"]], y=[result["combined"]["i_ztc"]], mode="markers", marker={"size": 16, "symbol": "star", "color": "crimson"}, name="ZTC combinado"))
        figure.add_trace(go.Scatter(x=[result["didt"]["vt_ztc"]], y=[result["didt"]["i_ztc"]], mode="markers", marker={"size": 14, "symbol": "x", "color": "crimson"}, name="ZTC dI/dT"))
        figure.add_trace(go.Scatter(x=[result["relative"]["vt_ztc"]], y=[result["relative"]["i_ztc"]], mode="markers", marker={"size": 14, "symbol": "diamond", "color": "black"}, name="ZTC error relativo"))
        figure.update_layout(template="plotly_white", xaxis_title="Voltaje [V]", yaxis_title="Corriente [A]", hovermode="x unified")
        st.plotly_chart(figure, width="stretch")
        rows = []
        for measurement in measurements.itertuples():
            try:
                rows.append({"Archivo": measurement.archivo, **individual_result(repository, int(measurement.id), result["combined"]["vt_ztc"], result["combined"]["i_ztc"])})
            except ValueError as error:
                st.warning(f"{measurement.archivo}: {error}")
        if rows:
            st.dataframe(rows, width="stretch", hide_index=True)
        dispersion = st.session_state.get(f"ztc_dispersion_{campaign_id}")
        if dispersion is None:
            try:
                _, dispersion = campaign_analysis_methods(repository, campaign_id, measurements)
            except ValueError:
                dispersion = None
        if dispersion is not None:
            _render_dispersion_dashboard(repository, measurements, dispersion, f"Campaña {campaign.numero}")


def _render_dispersion_dashboard(repository, measurements, dispersion: pd.DataFrame, title: str):
    st.subheader(f"Dispersión | {title}")
    left, right = st.columns(2)
    with left:
        figure = go.Figure()
        figure.add_trace(go.Scatter(x=dispersion.v, y=dispersion.relative_error * 100, mode="lines", name="Error relativo [%]"))
        figure.add_trace(go.Scatter(x=dispersion.v, y=np.abs(dispersion.d_i_d_t), mode="lines", name="|dI/dT|", yaxis="y2"))
        figure.add_trace(go.Scatter(x=dispersion.v, y=dispersion.combined_score, mode="lines", name="Score combinado", yaxis="y3"))
        figure.update_layout(template="plotly_white", xaxis_title="VT [V]", yaxis_title="Error relativo [%]", yaxis2={"title": "|dI/dT|", "overlaying": "y", "side": "right"}, yaxis3={"title": "Score combinado", "overlaying": "y", "side": "right", "position": 0.92}, hovermode="x unified")
        st.plotly_chart(figure, width="stretch")
    with right:
        st.dataframe(pd.DataFrame({"Dato": ["VT mínimo error relativo", "VT dI/dT", "Error relativo mínimo", "Temperaturas"],
                                   "Valor": [float(dispersion.loc[dispersion.relative_error.idxmin(), "v"]), float(dispersion.v.iloc[np.abs(dispersion.d_i_d_t).argmin()]),
                                              f"{dispersion.relative_error.min():.3%}", dispersion.temperatures.iloc[0]]}), hide_index=True, width="stretch")
        labels = {f"{row.archivo} | {extract_temperature(row):g} °C": int(row.id) for row in measurements.itertuples()}
        selected = st.selectbox("Medición para detalle", list(labels), key=f"dispersion_measurement_{title}")
        selected_points = repository.points(labels[selected])
        selected_row = measurements[measurements.id == labels[selected]].iloc[0]
        st.dataframe(pd.DataFrame({"Característica": ["Archivo", "Temperatura", "Puntos", "V mínimo", "V máximo", "I mínimo", "I máximo"],
                                   "Valor": [selected_row.archivo, extract_temperature(selected_row), len(selected_points), selected_points.v.min(), selected_points.v.max(), selected_points.i.min(), selected_points.i.max()]}), hide_index=True, width="stretch")


def _render_evolution(repository, campaigns, labels):
    st.subheader("Evolución de puntos ZTC sobre curvas I-V")
    st.caption("Cada color representa una campaña; la estrella marca su punto ZTC.")
    devices = campaigns.dispositivo.unique().tolist()
    selected_device = st.selectbox("Dispositivo", devices, key="ztc_evolution_device")
    device_campaigns = campaigns[campaigns.dispositivo == selected_device].copy()
    device_labels = [campaign_label(row) for row in device_campaigns.itertuples()]
    selected = st.multiselect("Campañas a analizar", device_labels, default=device_labels, key="ztc_evolution_campaigns")
    set_name = st.text_input("Nombre del conjunto", key="ztc_evolution_set_name")
    if st.button("Guardar conjunto de evolución", key="save_ztc_evolution_set") and set_name.strip():
        repository.save_workbench_view(set_name, {"type": "ztc_evolution",
                                                  "device_id": int(device_campaigns.iloc[0].dispositivo_id),
                                                  "campaign_ids": [int(device_campaigns.iloc[device_labels.index(label)].id) for label in selected]})
        repository.connection.commit()
        st.success("Conjunto de evolución guardado.")
    saved_sets = repository.workbench_views()
    saved_sets = saved_sets[saved_sets.configuracion.str.contains('"type": "ztc_evolution"', regex=False)] if not saved_sets.empty else saved_sets
    if not saved_sets.empty:
        saved_name = st.selectbox("Cargar conjunto guardado", ["(ninguno)"] + saved_sets.nombre.tolist(), key="load_ztc_evolution_set")
        if saved_name != "(ninguno)":
            saved = json.loads(saved_sets.loc[saved_sets.nombre == saved_name, "configuracion"].iloc[0])
            selected = [label for label, value in zip(device_labels, device_campaigns.id) if int(value) in saved.get("campaign_ids", [])]
    selected_ids = [int(device_campaigns.iloc[device_labels.index(label)].id) for label in selected]
    if not selected_ids:
        st.info("Selecciona campañas para calcular su evolución.")
        return
    rows = []
    dispersions = []
    for campaign_id in selected_ids:
        campaign = campaigns[campaigns.id == campaign_id].iloc[0]
        measurements = temperature_measurements(repository.iv_measurements(campaign_id))
        try:
            result, dispersion = campaign_analysis_methods(repository, campaign_id, measurements)
            rows.append({"campana_id": campaign_id, "dispositivo": campaign.dispositivo, "campaña": campaign.numero,
                         "VT combinado [V]": result["combined"]["vt_ztc"], "I combinado [µA]": result["combined"]["i_ztc"] * 1_000_000,
                         "VT dI/dT [V]": result["didt"]["vt_ztc"], "I dI/dT [µA]": result["didt"]["i_ztc"] * 1_000_000,
                         "VT relativo [V]": result["relative"]["vt_ztc"], "I relativo [µA]": result["relative"]["i_ztc"] * 1_000_000,
                         "error relativo": result.get("error_relativo"), "mediciones": result["cantidad_mediciones"]})
            dispersions.append(dispersion.assign(campaña=str(campaign.numero), dispositivo=campaign.dispositivo))
        except ValueError as error:
            st.warning(f"{campaign.dispositivo} | {campaign.numero}: {error}")
    if not rows:
        return
    frame = pd.DataFrame(rows)
    st.dataframe(frame.drop(columns=["campana_id"]), width="stretch", hide_index=True)
    figure = go.Figure()
    colors = ["#0c7285", "#bd7b19", "#c34d46", "#4f6d7a", "#6b5b95", "#4d8b5f"]
    for index, row in frame.iterrows():
        measurements = temperature_measurements(repository.iv_measurements(int(row["campana_id"])))
        for measurement in measurements.itertuples():
            points = repository.points(int(measurement.id))
            figure.add_trace(go.Scatter(x=points.v, y=points.i, mode="lines", line={"color": colors[index % len(colors)]},
                                         legendgroup=str(row["campana_id"]), name=f"{row['dispositivo']} | {row['campaña']} | {campaign_context(row['campaña'])}"))
        figure.add_trace(go.Scatter(x=[row["VT combinado [V]"]], y=[row["I combinado [µA]"] / 1_000_000], mode="markers",
                         marker={"size": 16, "symbol": "star", "color": colors[index % len(colors)]},
                         legendgroup=str(row["campana_id"]), name=f"ZTC combinado | {row['campaña']}"))
        figure.add_trace(go.Scatter(x=[row["VT dI/dT [V]"]], y=[row["I dI/dT [µA]"] / 1_000_000], mode="markers",
                                     marker={"size": 14, "symbol": "star", "color": colors[index % len(colors)]},
                         legendgroup=str(row["campana_id"]), name=f"ZTC dI/dT | {row['campaña']}", showlegend=False))
    figure.update_layout(template="plotly_white", xaxis_title="Voltaje [V]", yaxis_title="Corriente [A]", hovermode="x unified")
    st.plotly_chart(figure, width="stretch")
    left, right = st.columns(2)
    with left:
        progression = go.Figure()
        progression.add_trace(go.Scatter(x=frame["campaña"], y=frame["I combinado [µA]"], mode="lines+markers", text=frame["dispositivo"], name="combinado"))
        progression.add_trace(go.Scatter(x=frame["campaña"], y=frame["I dI/dT [µA]"], mode="lines+markers", text=frame["dispositivo"], name="dI/dT"))
        progression.add_trace(go.Scatter(x=frame["campaña"], y=frame["I relativo [µA]"], mode="lines+markers", text=frame["dispositivo"], name="error relativo"))
        progression.update_layout(template="plotly_white", xaxis_title="Campaña", yaxis_title="I ZTC [µA]", hovermode="x unified")
        st.subheader("Progresión de I ZTC")
        st.plotly_chart(progression, width="stretch")
    with right:
        all_dispersion = pd.concat(dispersions, ignore_index=True)
        dispersion_figure = go.Figure()
        for (device, campaign), group in all_dispersion.groupby(["dispositivo", "campaña"]):
            dispersion_figure.add_trace(go.Scatter(x=group.v, y=group.relative_error * 100, mode="lines", name=f"{device} | {campaign}"))
        dispersion_figure.update_layout(template="plotly_white", xaxis_title="VT [V]", yaxis_title="Error relativo [%]", legend_title="Dispositivo | Campaña", hovermode="x unified")
        st.subheader("Dispersión de todas las campañas")
        st.plotly_chart(dispersion_figure, width="stretch")
        st.dataframe(all_dispersion.groupby(["dispositivo", "campaña"], as_index=False).agg(error_relativo_minimo=("relative_error", "min"), score_combinado_minimo=("combined_score", "min"), vt_error_minimo=("v", "min")), hide_index=True, width="stretch")
    st.caption("Las estrellas son los puntos ZTC de cada campaña. La tabla expresa la corriente en µA.")


def _render_links(repository, campaigns, labels):
    _render_sequence_editor(repository, campaigns, labels)
    _render_recommendations(repository, campaigns)


def _render_device_comparison(repository):
    st.subheader("ZTC de todos los dispositivos")
    st.caption("Se analizan únicamente barridos con temperatura numérica para entregar una comparación automática revisable.")
    devices = repository.devices()
    campaigns = repository.campaigns()
    rows = []
    curves = []
    for device in devices.itertuples():
        device_campaigns = campaigns[campaigns.dispositivo_id == device.id]
        for campaign in device_campaigns.itertuples():
            thermal = temperature_measurements(repository.iv_measurements(int(campaign.id)))
            if thermal.empty:
                continue
            try:
                result, _ = campaign_analysis_methods(repository, int(campaign.id), thermal)
            except ValueError:
                continue
            rows.append({"dispositivo": device.nombre,
                         "campaña original": campaign.numero, "VT dI/dT [V]": result["didt"]["vt_ztc"],
                         "VT combinado [V]": result["combined"]["vt_ztc"], "I combinado [A]": result["combined"]["i_ztc"],
                         "I dI/dT [A]": result["didt"]["i_ztc"], "I dI/dT": format_current(result["didt"]["i_ztc"]),
                         "VT relativo [V]": result["relative"]["vt_ztc"], "I relativo [A]": result["relative"]["i_ztc"],
                         "I relativo": format_current(result["relative"]["i_ztc"]), "error relativo": result.get("error_relativo")})
            curves.append((device.nombre, campaign.numero, result["didt"]["vt_ztc"], result["didt"]["i_ztc"], result["relative"]["vt_ztc"], result["relative"]["i_ztc"]))
    if not rows:
        st.info("No hay campañas con al menos dos temperaturas numéricas.")
        return
    frame = pd.DataFrame(rows)
    st.dataframe(frame, width="stretch", hide_index=True)
    figure = go.Figure()
    for device_name, campaign_number, vt_didt, current_didt, vt_relative, current_relative in curves:
        figure.add_trace(go.Scatter(x=[vt_didt], y=[current_didt], mode="markers+text", text=[f"{device_name} | {campaign_number} | dI/dT"], textposition="top center",
                                    name=f"{device_name} | {campaign_number} | dI/dT", hovertemplate="%{text}<br>VT=%{x} V<br>I=%{y} A<extra></extra>"))
        figure.add_trace(go.Scatter(x=[vt_relative], y=[current_relative], mode="markers", marker={"symbol": "diamond"},
                                    text=[f"{device_name} | {campaign_number} | relativo"], name=f"{device_name} | {campaign_number} | relativo", hovertemplate="%{text}<br>VT=%{x} V<br>I=%{y} A<extra></extra>"))
    figure.update_layout(template="plotly_white", xaxis_title="VT ZTC [V]", yaxis_title="I ZTC [A]", legend_title="Dispositivo | Campaña", hovermode="closest")
    st.plotly_chart(figure, width="stretch")
    progression = go.Figure()
    for device_name, device_frame in frame.groupby("dispositivo"):
        progression.add_trace(go.Scatter(x=device_frame["campaña original"].astype(str), y=device_frame["I combinado [A]"], mode="lines+markers", name=f"{device_name} | combinado"))
        progression.add_trace(go.Scatter(x=device_frame["campaña original"].astype(str), y=device_frame["I dI/dT [A]"], mode="lines+markers", name=f"{device_name} | dI/dT"))
        progression.add_trace(go.Scatter(x=device_frame["campaña original"].astype(str), y=device_frame["I relativo [A]"], mode="lines+markers", name=f"{device_name} | relativo"))
    progression.update_layout(template="plotly_white", xaxis_title="Campaña original", yaxis_title="I ZTC [A]", legend_title="Dispositivo")
    st.plotly_chart(progression, width="stretch")


def _render_sequence_editor(repository, campaigns, labels):
    st.subheader("Secuencia del dispositivo")
    options = {label: int(campaigns.iloc[index].id) for index, label in enumerate(labels)}
    previous = st.selectbox("Campaña anterior", labels, key="evolution_previous")
    following = st.selectbox("Campaña siguiente", labels, key="evolution_following")
    indeterminate = st.checkbox("Orden todavía indeterminado", key="evolution_indeterminate")
    order = st.number_input("Etapa", min_value=1, value=1, step=1, disabled=indeterminate, key="evolution_order")
    reason = st.text_input("Motivo / tratamiento", placeholder="Ej.: posthorno, nada, Curie", key="evolution_reason")
    if st.button("Guardar secuencia", key="evolution_save_sequence"):
        if previous == following:
            st.error("La campaña anterior y siguiente deben ser distintas.")
        else:
            repository.link_campaigns(options[previous], options[following], None if indeterminate else int(order), reason)
            repository.connection.commit()
            st.success("Secuencia guardada.")
    links = repository.campaign_links()
    links = links[links.dispositivo == campaigns.iloc[0].dispositivo] if not links.empty else links
    if not links.empty:
        st.dataframe(links[["anterior", "siguiente", "orden", "motivo"]], width="stretch", hide_index=True)


def _render_recommendations(repository, campaigns):
    st.subheader("Comparaciones recomendadas")
    measurements = temperature_measurements(repository.iv_measurements())
    stored = repository.ztc_results()
    recommendations = []
    for device_id, device_campaigns in campaigns.groupby("dispositivo_id"):
        device_campaigns = device_campaigns.sort_values("id")
        for previous_index in range(len(device_campaigns) - 1):
            previous = device_campaigns.iloc[previous_index]
            following = device_campaigns.iloc[previous_index + 1]
            previous_count = int((measurements.campana_id == previous.id).sum()) if not measurements.empty else 0
            following_count = int((measurements.campana_id == following.id).sum()) if not measurements.empty else 0
            if not previous_count or not following_count:
                continue
            has_ztc = int(previous.id in stored.campana_id.values) + int(following.id in stored.campana_id.values)
            score = min(previous_count, following_count) + has_ztc * 2
            recommendations.append({"dispositivo": previous.dispositivo, "anterior": previous.numero,
                                    "siguiente": following.numero, "curvas comparables": min(previous_count, following_count),
                                    "ZTC calculado": f"{has_ztc}/2", "prioridad": score})
    if recommendations:
        frame = pd.DataFrame(recommendations).sort_values("prioridad", ascending=False)
        st.dataframe(frame.drop(columns="prioridad"), width="stretch", hide_index=True)
    else:
        st.info("Todavía no hay dos campañas consecutivas del mismo dispositivo con curvas I-V para recomendar.")
