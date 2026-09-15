import plotly.express as px
import streamlit as st

from ui.theme import banner

def render(repository):
    banner("Centro de control", "Estado del laboratorio", "Una lectura rápida de dispositivos, campañas, curvas y seguimiento temporal.")
    counts = repository.counts()
    columns = st.columns(4)
    metrics = [("Dispositivos", counts["devices"]), ("Campañas", counts["campaigns"]), ("Mediciones I-V", counts["measurements"]), ("Puntos I-V", counts["points"])]
    for column, (label, value) in zip(columns, metrics):
        column.metric(label, value)
    st.markdown("#### Seguimiento temporal")
    columns = st.columns(4)
    metrics = [("Tracks Vt", counts["tracks"]), ("Puntos Track", counts["track_points"]), ("Sin clasificar", counts["unclassified"]), ("Análisis ZTC", counts["ztc"])]
    for column, (label, value) in zip(columns, metrics):
        column.metric(label, value)
    measurements = repository.measurements()
    if not measurements.empty:
        summary = measurements.groupby("dispositivo", as_index=False).size().rename(columns={"size": "mediciones"})
        figure = px.bar(summary, x="dispositivo", y="mediciones", title="Curvas I-V por dispositivo", color_discrete_sequence=["#0c7285"])
        figure.update_layout(template="plotly_white", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(figure, width="stretch")
    else:
        st.info("Importa un Excel para comenzar a explorar mediciones.")
