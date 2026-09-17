import streamlit as st

from config import APP_TITLE
from database.db import get_connection, initialize_database
from database.repository import Repository
import ui.dashboard as dashboard
import ui.import_export as import_export
import ui.measurements as measurements
import ui.workbench as workbench
from ui.theme import apply_theme


st.set_page_config(page_title=APP_TITLE, page_icon="📊", layout="wide")
apply_theme()
initialize_database()


@st.cache_resource
def get_repository():
    return Repository(get_connection())


repository = get_repository()
st.sidebar.markdown("## AMapp")
st.sidebar.caption("Laboratorio de curvas y campañas")
page = st.sidebar.radio("Navegación", ["📊 Dashboard", "🔬 Mediciones", "🧰 Workbench", "📥 Importar / Exportar"])

if page == "📊 Dashboard":
    dashboard.render(repository)
elif page == "🔬 Mediciones":
    measurements.render(repository)
elif page == "🧰 Workbench":
    workbench.render(repository)
else:
    import_export.render(repository)
