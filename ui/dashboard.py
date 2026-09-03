import plotly.express as px
import streamlit as st


def render(repository):
    st.title("Dashboard")
    counts = repository.counts()
    columns = st.columns(5)
    for column, (label, value) in zip(columns, [("Dispositivos", counts["devices"]), ("Campanas", counts["campaigns"]), ("Mediciones", counts["measurements"]), ("Puntos", counts["points"]), ("Analisis ZTC", counts["ztc"])]):
        column.metric(label, value)
    measurements = repository.measurements()
    if not measurements.empty:
        summary = measurements.groupby("dispositivo", as_index=False).size().rename(columns={"size": "mediciones"})
        st.plotly_chart(px.bar(summary, x="dispositivo", y="mediciones", title="Mediciones por dispositivo"), use_container_width=True)
    else:
        st.info("Importa un Excel para comenzar a explorar mediciones.")
