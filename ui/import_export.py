import streamlit as st
import pandas as pd

from services.excel_export import export_excel, export_integrity
from services.excel_import import detect_input_type, import_excel, import_measurement
from ui.theme import banner
from ui.measurement_editor import render_measurement_editor


def render(repository):
    banner("Datos y trazabilidad", "Importar / Exportar", "Cargá mediciones, revisá formatos no clasificados y descargá una copia completa.")
    uploaded = st.file_uploader("Selecciona un Excel o una medicion (.xlsx, .xls, .xlsm, .ri)", type=["xlsx", "xls", "xlsm", "ri"])
    duplicate_mode = "renombrar"
    if uploaded and st.button("Importar datos", type="primary"):
        with st.spinner("Importando..."):
            input_type = detect_input_type(uploaded)
            try:
                if input_type == "excel":
                    summary = import_excel(uploaded, repository, duplicate_mode)
                elif input_type == "medicion":
                    summary = import_measurement(uploaded, repository, duplicate_mode)
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
            st.dataframe(summary["errores"], width="stretch", hide_index=True)
    st.divider()
    st.subheader("Exportar base completa")
    integrity = export_integrity(repository)
    if any(integrity.values()):
        st.error(f"La base tiene posibles duplicados: {integrity}")
    else:
        st.success("Integridad OK: no hay mediciones, puntos ni Tracks duplicados.")
    st.download_button(
        "Exportar base completa (Excel)",
        export_excel(repository),
        "mediciones_exportadas.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="export_complete_database",
    )
    _render_database_view(repository)
    unclassified = repository.unclassified()
    if not unclassified.empty:
        st.subheader("Hojas sin clasificar")
        st.caption("Se conservaron aparte porque no tienen el formato I-V ni Track Vt reconocido.")
        st.dataframe(unclassified[["archivo_origen", "hoja", "tipo", "filas", "columnas"]], width="stretch", hide_index=True)


def _render_database_view(repository):
    st.divider()
    st.subheader("Visualizar y editar base de datos")
    tables = {
        "Dispositivos": repository.devices,
        "Campañas": repository.campaigns,
        "Mediciones": repository.measurements,
        "Puntos I-V": repository.all_points,
        "Tracks Vt": repository.tracks,
        "Puntos Track Vt": repository.all_track_points,
        "Resultados ZTC": repository.ztc_results,
        "Grupos": repository.measurement_groups,
        "Secuencias": repository.campaign_links,
        "Sin clasificar": repository.unclassified,
    }
    selected_table = st.selectbox("Tabla", list(tables), key="database_table_view")
    frame = (repository.measurements(include_deleted=True) if selected_table == "Mediciones" else tables[selected_table]()).copy()
    filter_text = st.text_input("Filtrar registros", key="database_table_filter", placeholder="Texto en cualquier columna")
    if filter_text and not frame.empty:
        searchable = frame.fillna("").astype(str).agg(" ".join, axis=1)
        frame = frame[searchable.str.contains(filter_text, case=False, regex=False)]
    st.caption(f"{len(frame)} registro(s) visibles")
    if selected_table == "Mediciones" and not frame.empty:
        render_measurement_editor(repository, frame, "database_measurements")
    else:
        st.dataframe(frame, width="stretch", hide_index=True)
    st.download_button("Descargar tabla visible CSV", frame.to_csv(index=False).encode("utf-8"), f"{selected_table.lower().replace(' ', '_')}.csv", "text/csv", key="database_table_csv")
