import plotly.graph_objects as go
import streamlit as st
import pandas as pd

from services.measurements import campaign_analysis, individual_result
from ui.charts import iv_chart
from utils.helpers import format_current


def render(repository):
    st.title("Análisis ZTC")
    st.caption("ZTC se calcula solamente sobre curvas I-V. Track Vt se analiza en su sección independiente.")
    campaigns = repository.campaigns()
    if campaigns.empty:
        st.info("Todavia no hay campanas cargadas.")
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
    measurements = repository.measurements(campaign_id)
    st.caption(f"{len(measurements)} medicion(es) disponibles")
    if st.button("Calcular / actualizar ZTC", type="primary"):
        try:
            result, _ = campaign_analysis(repository, campaign_id)
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
    st.subheader("Evolución de puntos ZTC")
    selected = st.multiselect("Campañas a analizar", labels, default=labels[:2], key="ztc_evolution_campaigns")
    selected_ids = [int(campaigns.iloc[labels.index(label)].id) for label in selected]
    if not selected_ids:
        st.info("Selecciona campañas para calcular su evolución.")
        return
    stored = repository.ztc_results()
    rows = []
    for campaign_id in selected_ids:
        campaign = campaigns[campaigns.id == campaign_id].iloc[0]
        try:
            result, _ = campaign_analysis(repository, campaign_id)
            rows.append({"campana_id": campaign_id, "dispositivo": campaign.dispositivo, "campaña": campaign.numero,
                         "VT ZTC [V]": result["vt_ztc"], "I ZTC [A]": result["i_ztc"], "mediciones": result["cantidad_mediciones"]})
        except ValueError as error:
            st.warning(f"{campaign.dispositivo} | {campaign.numero}: {error}")
    if not rows:
        return
    frame = pd.DataFrame(rows)
    st.dataframe(frame.drop(columns=["campana_id"]), width="stretch", hide_index=True)
    figure = go.Figure()
    figure.add_trace(go.Scatter(x=frame["campaña"], y=frame["VT ZTC [V]"], mode="lines+markers", name="VT ZTC"))
    figure.update_layout(template="plotly_white", xaxis_title="Campaña / etapa", yaxis_title="VT ZTC [V]")
    st.plotly_chart(figure, width="stretch")
    st.caption("Las campañas enlazadas en Secuencia se pueden ordenar por etapa para leer este gráfico como antes/después.")


def _render_links(repository, campaigns, labels):
    st.subheader("Secuencia de campañas")
    st.caption("Define qué campaña sigue a otra y marca el motivo para decidir comparaciones ZTC.")
    options = {label: int(campaigns.iloc[index].id) for index, label in enumerate(labels)}
    previous = st.selectbox("Campaña anterior", labels, key="link_previous")
    following = st.selectbox("Campaña siguiente", labels, key="link_following")
    order = st.number_input("Etapa", min_value=1, value=1, step=1)
    reason = st.text_input("Motivo / tratamiento", placeholder="Ej.: después de Curie, antes de horno")
    if st.button("Guardar secuencia", type="primary"):
        if previous == following:
            st.error("La campaña anterior y siguiente deben ser distintas.")
        else:
            repository.link_campaigns(options[previous], options[following], int(order), reason)
            repository.connection.commit()
            st.success("Secuencia guardada.")
    links = repository.campaign_links()
    if not links.empty:
        st.dataframe(links[["dispositivo", "anterior", "siguiente", "orden", "motivo"]], width="stretch", hide_index=True)
    _render_recommendations(repository, campaigns)


def _render_recommendations(repository, campaigns):
    st.subheader("Comparaciones recomendadas")
    measurements = repository.measurements()
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
