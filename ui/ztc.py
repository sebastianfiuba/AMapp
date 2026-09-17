import plotly.graph_objects as go
import streamlit as st
import pandas as pd

from services.measurements import campaign_analysis, individual_result, temperature_measurements
from ui.charts import iv_chart
from ui.theme import banner
from utils.helpers import format_current


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
    selected_devices = st.multiselect("Dispositivos", device_labels, default=device_labels[:1], key="ztc_devices")
    device_ids = [int(devices.loc[devices.nombre == name, "id"].iloc[0]) for name in selected_devices]
    campaigns = campaigns[campaigns.dispositivo_id.isin(device_ids)]
    thermal_campaign_ids = {
        int(campaign_id)
        for campaign_id in campaigns.id
        if not temperature_measurements(repository.iv_measurements(int(campaign_id))).empty
    }
    campaigns = campaigns[campaigns.id.isin(thermal_campaign_ids)]
    if campaigns.empty:
        st.info("No hay campañas con barridos de temperatura para los dispositivos seleccionados.")
        return
    labels = [f"{row.dispositivo} | {row.numero}" for row in campaigns.itertuples()]
    tab_single, tab_evolution, tab_links = st.tabs(["Una campaña", "Evolución", "Secuencia"])
    with tab_single:
        selected = st.selectbox("Campaña", labels, key="ztc_single_campaign")
        campaign = campaigns.iloc[labels.index(selected)]
        campaign_id = int(campaign.id)
        _render_campaign(repository, campaign, campaign_id)
    with tab_evolution:
        _render_evolution(repository, campaigns, labels)
    with tab_links:
        _render_links(repository, campaigns, labels)


def _render_campaign(repository, campaign, campaign_id: int):
    measurements = temperature_measurements(repository.iv_measurements(campaign_id))
    st.caption(f"{len(measurements)} medicion(es) disponibles")
    if st.button("Calcular / actualizar ZTC", type="primary"):
        try:
            result, _ = campaign_analysis(repository, campaign_id, measurements)
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
        points = {int(row.id): repository.points(int(row.id)) for row in measurements.itertuples()}
        st.plotly_chart(iv_chart(measurements, points, (result["vt_ztc"], result["i_ztc"])), width="stretch")
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
    selected = st.multiselect("Campañas a analizar", labels, default=labels[:2], key="ztc_evolution_campaigns")
    selected_ids = [int(campaigns.iloc[labels.index(label)].id) for label in selected]
    if not selected_ids:
        st.info("Selecciona campañas para calcular su evolución.")
        return
    stored = repository.ztc_results()
    rows = []
    for campaign_id in selected_ids:
        campaign = campaigns[campaigns.id == campaign_id].iloc[0]
        measurements = temperature_measurements(repository.iv_measurements(campaign_id))
        try:
            result, _ = campaign_analysis(repository, campaign_id, measurements)
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
                                         legendgroup=str(row["campana_id"]), name=f"{row['dispositivo']} | {row['campaña']}"))
        figure.add_trace(go.Scatter(x=[row["VT ZTC [V]"]], y=[row["I ZTC [µA]"] / 1_000_000], mode="markers",
                                     marker={"size": 14, "symbol": "star", "color": colors[index % len(colors)]},
                                     legendgroup=str(row["campana_id"]), name=f"ZTC | {row['campaña']}"))
    figure.update_layout(template="plotly_white", xaxis_title="Voltaje [V]", yaxis_title="Corriente [A]", hovermode="x unified")
    st.plotly_chart(figure, width="stretch")
    st.caption("Las estrellas son los puntos ZTC de cada campaña. La tabla expresa la corriente en µA.")


def _render_links(repository, campaigns, labels):
    st.subheader("Secuencia de campañas")
    st.caption("Define qué campaña sigue a otra y marca el motivo para decidir comparaciones ZTC.")
    options = {label: int(campaigns.iloc[index].id) for index, label in enumerate(labels)}
    previous = st.selectbox("Campaña anterior", labels, key="link_previous")
    following = st.selectbox("Campaña siguiente", labels, key="link_following")
    indeterminate = st.checkbox("Orden todavía indeterminado", help="Usalo cuando sabés que hay relación, pero aún no la etapa exacta.")
    order = st.number_input("Etapa", min_value=1, value=1, step=1, disabled=indeterminate)
    reason = st.text_input("Motivo / tratamiento", placeholder="Ej.: después de Curie, antes de horno")
    if st.button("Guardar secuencia", type="primary"):
        if previous == following:
            st.error("La campaña anterior y siguiente deben ser distintas.")
        else:
            repository.link_campaigns(options[previous], options[following], None if indeterminate else int(order), reason)
            repository.connection.commit()
            st.success("Secuencia guardada.")
    links = repository.campaign_links()
    if not links.empty:
        display_links = links[["dispositivo", "anterior", "siguiente", "orden", "motivo"]].copy()
        display_links["orden"] = display_links["orden"].replace(0, "Indeterminada").fillna("Indeterminada")
        st.dataframe(display_links, width="stretch", hide_index=True)
    _render_recommendations(repository, campaigns)


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
