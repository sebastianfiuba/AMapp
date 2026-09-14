import streamlit as st

from config import APP_TITLE
from database.db import get_connection, initialize_database
from database.repository import Repository
from ui import dashboard, graphs, import_export, iv, measurements, track_vt, workbench, ztc


st.set_page_config(page_title=APP_TITLE, page_icon="📊", layout="wide")
initialize_database()


@st.cache_resource
def get_repository():
    return Repository(get_connection())


repository = get_repository()
page = st.sidebar.radio("Navegación", ["📊 Dashboard", "⚡ I-V", "⏱ Track Vt", "🔬 Mediciones", "🧰 Workbench", "🧮 Análisis ZTC", "📥 Importar / Exportar"])

if page == "📊 Dashboard":
    dashboard.render(repository)
elif page == "⚡ I-V":
    iv.render(repository)
elif page == "⏱ Track Vt":
    track_vt.render(repository)
elif page == "🔬 Mediciones":
    measurements.render(repository)
elif page == "📈 Graficos":
    graphs.render(repository)
elif page == "🧮 Análisis ZTC":
    ztc.render(repository)
elif page == "🧰 Workbench":
    workbench.render(repository)
else:
    import_export.render(repository)
