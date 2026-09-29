import plotly.express as px
import streamlit as st

from ui.charts import style_figure
from ui.theme import banner
from services.assistant import answer_question

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
        style_figure(figure, height=500)
        st.plotly_chart(figure, width="stretch")
    else:
        st.info("Importa un Excel para comenzar a explorar mediciones.")
    st.divider()
    st.subheader("Analista local")
    st.caption("Análisis contextual con Ollama local gratuito si está disponible; si no, usa cálculos directos de la base.")
    if "dashboard_chat" not in st.session_state:
        st.session_state.dashboard_chat = []
    for message in st.session_state.dashboard_chat:
        with st.chat_message(message["role"]):
            st.write(message["content"])
    question = st.chat_input("Ej.: analiza dispositivo 17, campaña 15", key="dashboard_chat_input")
    if question:
        answer = answer_question(repository, question)
        st.session_state.dashboard_chat.extend([
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer},
        ])
        st.rerun()
