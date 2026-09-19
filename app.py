import streamlit as st

from config import APP_TITLE
from database.db import get_connection, initialize_database
from database.repository import Repository
import ui.dashboard as dashboard
import ui.import_export as import_export
import ui.measurements as measurements
import ui.workbench as workbench
import ui.ztc as ztc
from ui.theme import apply_theme


st.set_page_config(page_title=APP_TITLE, page_icon="📊", layout="wide")
apply_theme()
initialize_database()


@st.cache_resource
def get_repository():
    return Repository(get_connection())


repository = get_repository()
st.markdown("# AMapp")
st.caption("Laboratorio de curvas y campañas")
sections = ["Dashboard", "Análisis automático", "Análisis manual", "Datos"]
section = st.radio("Secciones", sections, horizontal=True, label_visibility="collapsed", key="main_section")
st.sidebar.markdown("## AMapp")
st.sidebar.markdown(f"**Sección activa**  \n{section}")
st.sidebar.markdown("---")
st.sidebar.caption("Navegación rápida")
for item in sections:
    st.sidebar.markdown(f"{'▸' if item == section else '·'} {item}")

if section == "Dashboard":
    dashboard.render(repository)
elif section == "Análisis automático":
    ztc.render_automatic(repository)
elif section == "Análisis manual":
    workbench.render_manual(repository)
else:
    data_measurements, data_import = st.tabs(["Mediciones", "Importar / Exportar"])
    with data_measurements:
        measurements.render(repository)
    with data_import:
        import_export.render(repository)
