import streamlit as st

from ui.charts import chart_downloads, iv_chart
from ui.theme import banner


def render(repository):
    banner("Caracterización eléctrica", "Análisis I-V", "Compará curvas de tensión-corriente por dispositivo y campaña.")
    campaigns = repository.campaigns()
    if campaigns.empty:
        st.info("Todavía no hay campañas con mediciones I-V.")
        return
    labels = [f"{row.dispositivo} | {row.numero}" for row in campaigns.itertuples()]
    selected = st.multiselect("Campañas a comparar", labels, default=labels[:1])
    ids = [int(campaigns.iloc[labels.index(label)].id) for label in selected]
    measurements = repository.measurements_for_campaigns(ids)
    if measurements.empty:
        st.info("Las campañas seleccionadas no tienen curvas I-V.")
        return
    points = {int(row.id): repository.points(int(row.id)) for row in measurements.itertuples()}
    figure = iv_chart(measurements, points)
    st.caption(f"{len(measurements)} curvas I-V")
    st.plotly_chart(figure, width="stretch")
    chart_downloads(figure, "comparacion_iv", "iv_page")
    st.dataframe(measurements[["dispositivo", "campana", "archivo", "fecha", "clase", "estado"]], width="stretch", hide_index=True)