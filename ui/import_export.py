import streamlit as st

from services.excel_export import export_excel, export_integrity
from services.excel_import import detect_input_type, import_excel, import_measurement


def render(repository):
    st.title("Importar / Exportar")
    uploaded = st.file_uploader("Selecciona un Excel o una medicion (.xlsx, .xls, .xlsm, .ri)", type=["xlsx", "xls", "xlsm", "ri"])
    if uploaded and st.button("Importar datos", type="primary"):
        with st.spinner("Importando..."):
            input_type = detect_input_type(uploaded)
            try:
                if input_type == "excel":
                    summary = import_excel(uploaded, repository)
                elif input_type == "medicion":
                    summary = import_measurement(uploaded, repository)
                else:
                    raise ValueError("tipo de archivo no reconocido; usa .xlsx, .xls, .xlsm o .ri")
            except ValueError as error:
                st.error(str(error))
                return
        st.success("Importacion finalizada")
        st.write(f"Mediciones nuevas: {summary.get('mediciones_nuevas', 0)} | Actualizadas: {summary.get('mediciones_actualizadas', 0)} | Ya existentes: {summary.get('ya_existentes', 0)}")
        st.write(f"Duplicados evitados: {summary.get('duplicados_evitados', 0)} | Puntos V/I nuevos: {summary.get('puntos_nuevos', 0)}")
        st.write(f"Tracks Vt nuevos: {summary.get('tracks_nuevos', 0)} | Puntos Track nuevos: {summary.get('track_points_nuevos', 0)}")
        st.write(f"Hojas sin clasificar nuevas: {summary.get('sin_clasificar_nuevos', 0)}")
        if summary["errores"]:
            st.warning("Algunas filas requieren revision.")
            st.dataframe(summary["errores"], use_container_width=True, hide_index=True)
    st.divider()
    st.subheader("Exportar base completa")
    integrity = export_integrity(repository)
    if any(integrity.values()):
        st.error(f"La base tiene posibles duplicados: {integrity}")
    else:
        st.success("Integridad OK: no hay mediciones, puntos ni Tracks duplicados.")
    st.download_button("Descargar Excel", export_excel(repository), "mediciones_exportadas.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    unclassified = repository.unclassified()
    if not unclassified.empty:
        st.subheader("Hojas sin clasificar")
        st.caption("Se conservaron aparte porque no tienen el formato I-V ni Track Vt reconocido.")
        st.dataframe(unclassified[["archivo_origen", "hoja", "tipo", "filas", "columnas"]], use_container_width=True, hide_index=True)
