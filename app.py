import streamlit as st

from config import APP_TITLE
from database.db import get_connection, initialize_database
from database.repository import Repository
from ui import dashboard, graphs, import_export, measurements, ztc


st.set_page_config(page_title=APP_TITLE, page_icon="📊", layout="wide")
initialize_database()


@st.cache_resource
def get_repository():
    return Repository(get_connection())


repository = get_repository()
page = st.sidebar.radio("Navegacion", ["📊 Dashboard", "🔬 Mediciones", "📈 Graficos", "🧮 Analisis ZTC", "📥 Importar / Exportar"])

if page == "📊 Dashboard":
    dashboard.render(repository)
elif page == "🔬 Mediciones":
    measurements.render(repository)
elif page == "📈 Graficos":
    graphs.render(repository)
elif page == "🧮 Analisis ZTC":
    ztc.render(repository)
else:
    import_export.render(repository)
