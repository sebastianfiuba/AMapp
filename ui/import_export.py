import streamlit as st

from services.excel_export import export_excel
from services.excel_import import import_excel


def render(repository):
    st.title("Importar / Exportar")
    uploaded = st.file_uploader("Selecciona un archivo Excel (.xlsx)", type=["xlsx"])
    if uploaded and st.button("Importar datos", type="primary"):
        with st.spinner("Importando..."):
            summary = import_excel(uploaded, repository)
        st.success(f"{summary['mediciones']} puntos importados; {summary['ignorados']} filas ignoradas.")
        st.write(f"{summary['dispositivos']} dispositivos, {summary['campanas']} campanas y {summary['puntos']} puntos nuevos.")
        if summary["errores"]:
            st.warning("Algunas filas requieren revision.")
            st.dataframe(summary["errores"], use_container_width=True, hide_index=True)
    st.divider()
    st.subheader("Exportar base completa")
    st.download_button("Descargar Excel", export_excel(repository), "mediciones_exportadas.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
