import streamlit as st

from ui.charts import iv_chart


def render(repository):
    st.title("Graficos")
    campaigns = repository.campaigns()
    if campaigns.empty:
        st.info("Todavia no hay campanas cargadas.")
        return
    labels = [f"{row.dispositivo} - Campana {row.numero}" for row in campaigns.itertuples()]
    selected = st.selectbox("Campana", labels)
    campaign = campaigns.iloc[labels.index(selected)]
    measurements = repository.measurements(int(campaign.id))
    points = {int(row.id): repository.points(int(row.id)) for row in measurements.itertuples()}
    st.plotly_chart(iv_chart(measurements, points), use_container_width=True)
