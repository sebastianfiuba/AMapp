import streamlit as st

from ui.charts import iv_chart
from ui.measurement_editor import render_measurement_editor
from ui.theme import banner


def render(repository):
    banner("Vista rápida", "Gráficos", "Inspeccioná las curvas I-V de una campaña sin entrar al análisis ZTC.")
    campaigns = repository.campaigns()
    if campaigns.empty:
        st.info("Todavia no hay campanas cargadas.")
        return
    labels = [f"{row.dispositivo} - Campana {row.numero}" for row in campaigns.itertuples()]
    selected = st.selectbox("Campana", labels)
    campaign = campaigns.iloc[labels.index(selected)]
    measurements = repository.measurements(int(campaign.id))
    render_measurement_editor(repository, measurements, "graphs_measurements")
    measurements = measurements[measurements.activa.astype(bool)]
    if measurements.empty:
        st.info("Las mediciones de la campaña están inactivas.")
        return
    points = {int(row.id): repository.points(int(row.id)) for row in measurements.itertuples()}
    st.plotly_chart(iv_chart(measurements, points), width="stretch")
