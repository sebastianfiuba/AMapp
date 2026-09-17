import json

import plotly.graph_objects as go
import streamlit as st
import pandas as pd

from services.measurements import campaign_analysis, extract_temperature, individual_result, temperature_measurements
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
    selected_device = st.selectbox("Dispositivo", device_labels, key="ztc_devices")
    device_id = int(devices.loc[devices.nombre == selected_device, "id"].iloc[0])
    campaigns = campaigns[campaigns.dispositivo_id == device_id]
    thermal_campaign_ids = {
        int(campaign_id)
        for campaign_id in campaigns.id
        if not temperature_measurements(repository.iv_measurements(int(campaign_id))).empty
    }
    campaigns = campaigns[campaigns.id.isin(thermal_campaign_ids)]
    if campaigns.empty:
        st.info("No hay campañas con barridos de temperatura para los dispositivos seleccionados.")
        return
    labels = [campaign_label(row) for row in campaigns.itertuples()]
    tab_single, tab_evolution, tab_devices = st.tabs(["Una campaña", "Evolución y secuencia", "Comparar dispositivos"])
    with tab_single:
        selected = st.selectbox("Campaña", labels, key="ztc_single_campaign")
        campaign = campaigns.iloc[labels.index(selected)]
        campaign_id = int(campaign.id)
        _render_campaign(repository, campaign, campaign_id)
    with tab_evolution:
        _render_evolution(repository, campaigns, labels)
    with tab_devices:
        _render_device_comparison(repository)


def _render_campaign(repository, campaign, campaign_id: int):
    measurements = temperature_measurements(repository.iv_measurements(campaign_id))
    st.caption(f"{len(measurements)} medicion(es) disponibles")
    method = st.selectbox("Método ZTC", ["dI/dT", "error relativo"], key=f"ztc_method_{campaign_id}", help="dI/dT busca pendiente térmica cero. Error relativo minimiza la diferencia porcentual entre corrientes a un mismo VT.")
    if st.button("Calcular / actualizar ZTC", type="primary"):
        try:
            result, _ = campaign_analysis(repository, campaign_id, measurements, method)
            st.session_state[f"ztc_{campaign_id}"] = result
            st.success("Analisis guardado.")
        except ValueError as error:
            st.error(str(error))
    result = st.session_state.get(f"ztc_{campaign_id}")
    stored = repository.ztc_results()
    if result is None and not stored.empty and campaign_id in stored.campana_id.values:
        row = stored[stored.campana_id == campaign_id].iloc[0]
        result = {"vt_ztc": row.vt_ztc, "i_ztc": row.i_ztc, "cantidad_mediciones": len(measurements)}
    if result:
        st.metric("VT ZTC", f"{result['vt_ztc']:.6g} V")
        st.metric("I ZTC", format_current(result["i_ztc"]))
        st.caption(f"Método: {result.get('metodo', method)} | Error relativo en el cruce: {result.get('error_relativo', 0):.3%}")
        points = {int(row.id): repository.points(int(row.id)) for row in measurements.itertuples()}
        figure = go.Figure()
        colors = ["#0c7285", "#bd7b19", "#c34d46", "#4f6d7a", "#6b5b95", "#4d8b5f"]
        for index, measurement in enumerate(measurements.itertuples()):
            curve = points[int(measurement.id)]
            temperature = extract_temperature(measurement)
            context = campaign_context(campaign.numero)
            figure.add_trace(go.Scatter(x=curve.v, y=curve.i, mode="lines+markers", line={"color": colors[index % len(colors)]},
                                         name=f"{context} | {measurement.archivo} | {temperature:g} °C" if temperature is not None else f"{context} | {measurement.archivo}"))
        figure.add_trace(go.Scatter(x=[result["vt_ztc"]], y=[result["i_ztc"]], mode="markers", marker={"size": 14, "symbol": "star", "color": "crimson"}, name="ZTC"))
        figure.update_layout(template="plotly_white", xaxis_title="Voltaje [V]", yaxis_title="Corriente [A]", hovermode="x unified")
        st.plotly_chart(figure, width="stretch")
        rows = []
        for measurement in measurements.itertuples():
            try:
                rows.append({"Archivo": measurement.archivo, **individual_result(repository, int(measurement.id), result["vt_ztc"], result["i_ztc"])})
            except ValueError as error:
                st.warning(f"{measurement.archivo}: {error}")
        if rows:
            st.dataframe(rows, width="stretch", hide_index=True)


def _render_evolution(repository, campaigns, labels):
    st.subheader("Evolución de puntos ZTC sobre curvas I-V")
    st.caption("Cada color representa una campaña; la estrella marca su punto ZTC.")
    devices = campaigns.dispositivo.unique().tolist()
    selected_device = st.selectbox("Dispositivo", devices, key="ztc_evolution_device")
    device_campaigns = campaigns[campaigns.dispositivo == selected_device].copy()
    device_labels = [campaign_label(row) for row in device_campaigns.itertuples()]
    selected = st.multiselect("Campañas a analizar", device_labels, default=device_labels[:2], key="ztc_evolution_campaigns")
    subcampaign_name = st.text_input("Nombre normalizado", value="Subcampaña 1", key="ztc_subcampaign_name")
    set_name = st.text_input("Nombre del conjunto", key="ztc_evolution_set_name")
    if st.button("Guardar conjunto de evolución", key="save_ztc_evolution_set") and set_name.strip():
        repository.save_workbench_view(set_name, {"type": "ztc_evolution", "subcampaign": subcampaign_name.strip() or "Subcampaña 1",
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
            subcampaign_name = saved.get("subcampaign", subcampaign_name)
            selected = [label for label, value in zip(device_labels, device_campaigns.id) if int(value) in saved.get("campaign_ids", [])]
            st.caption(f"Visualizando: {subcampaign_name}")
    selected_ids = [int(device_campaigns.iloc[device_labels.index(label)].id) for label in selected]
    if not selected_ids:
        st.info("Selecciona campañas para calcular su evolución.")
        return
    stored = repository.ztc_results()
    rows = []
    for campaign_id in selected_ids:
        campaign = campaigns[campaigns.id == campaign_id].iloc[0]
        measurements = temperature_measurements(repository.iv_measurements(campaign_id))
        try:
            result, _ = campaign_analysis(repository, campaign_id, measurements, "dI/dT")
            rows.append({"campana_id": campaign_id, "dispositivo": campaign.dispositivo, "campaña": campaign.numero,
                         "VT ZTC [V]": result["vt_ztc"], "I ZTC [µA]": result["i_ztc"] * 1_000_000, "mediciones": result["cantidad_mediciones"]})
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
        figure.add_trace(go.Scatter(x=[row["VT ZTC [V]"]], y=[row["I ZTC [µA]"] / 1_000_000], mode="markers",
                                     marker={"size": 14, "symbol": "star", "color": colors[index % len(colors)]},
                                     legendgroup=str(row["campana_id"]), name=f"ZTC | {row['campaña']}"))
    figure.update_layout(template="plotly_white", xaxis_title="Voltaje [V]", yaxis_title="Corriente [A]", hovermode="x unified")
    st.plotly_chart(figure, width="stretch")
    progression = go.Figure(go.Scatter(x=frame["campaña"], y=frame["I ZTC [µA]"], mode="lines+markers", text=frame["dispositivo"], name="I ZTC"))
    progression.update_layout(template="plotly_white", xaxis_title="Campaña", yaxis_title="I ZTC [µA]", hovermode="x unified")
    st.subheader("Progresión de I ZTC")
    st.plotly_chart(progression, width="stretch")
    st.caption("Las estrellas son los puntos ZTC de cada campaña. La tabla expresa la corriente en µA.")


def _render_links(repository, campaigns, labels):
    _render_sequence_editor(repository, campaigns, labels)
    _render_recommendations(repository, campaigns)


def _render_device_comparison(repository):
    st.subheader("ZTC de todos los dispositivos")
    st.caption("Se analizan únicamente barridos con temperatura numérica y se muestran bajo una subcampaña normalizada.")
    subcampaign_name = st.text_input("Subcampaña a visualizar", value="Subcampaña 1", key="ztc_devices_subcampaign")
    method = st.selectbox("Método ZTC", ["dI/dT", "error relativo"], key="ztc_devices_method")
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
                result, _ = campaign_analysis(repository, int(campaign.id), thermal, method)
            except ValueError:
                continue
            rows.append({"subcampaña": subcampaign_name.strip() or "Subcampaña 1", "dispositivo": device.nombre,
                         "campaña original": campaign.numero, "VT ZTC [V]": result["vt_ztc"],
                         "I ZTC [A]": result["i_ztc"], "I ZTC": format_current(result["i_ztc"]),
                         "error relativo": result.get("error_relativo")})
            curves.append((device.nombre, campaign.numero, result["vt_ztc"], result["i_ztc"]))
    if not rows:
        st.info("No hay campañas con al menos dos temperaturas numéricas.")
        return
    frame = pd.DataFrame(rows)
    st.dataframe(frame, width="stretch", hide_index=True)
    figure = go.Figure()
    for device_name, campaign_number, vt, current in curves:
        figure.add_trace(go.Scatter(x=[vt], y=[current], mode="markers+text", text=[f"{device_name} | {campaign_number}"], textposition="top center",
                                    name=f"{device_name} | {campaign_number}", hovertemplate="%{text}<br>VT=%{x} V<br>I=%{y} A<extra></extra>"))
    figure.update_layout(template="plotly_white", xaxis_title="VT ZTC [V]", yaxis_title="I ZTC [A]", legend_title="Dispositivo | Campaña", hovermode="closest")
    st.plotly_chart(figure, width="stretch")
    progression = go.Figure()
    for device_name, device_frame in frame.groupby("dispositivo"):
        progression.add_trace(go.Scatter(x=device_frame["campaña original"].astype(str), y=device_frame["I ZTC [A]"], mode="lines+markers", name=device_name))
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
