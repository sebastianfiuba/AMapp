import streamlit as st
import pandas as pd

from services.excel_export import export_excel, export_integrity
from services.excel_import import detect_input_type, import_excel, import_measurement, import_rar, rar_device_groups
from ui.theme import banner
from ui.measurement_editor import render_measurement_editor


def render(repository):
    banner("Datos y trazabilidad", "Importar / Exportar", "Cargá mediciones, revisá formatos no clasificados y descargá una copia completa.")
    uploaded = st.file_uploader("Selecciona un Excel, una medición o un RAR (.xlsx, .xls, .xlsm, .ri, .rar)", type=["xlsx", "xls", "xlsm", "ri", "rar"])
    duplicate_mode = "renombrar"
    input_type = detect_input_type(uploaded) if uploaded else ""
    selected_devices = None
    if uploaded and input_type == "rar":
        try:
            device_groups = rar_device_groups(uploaded)
        except ValueError as error:
            st.error(str(error))
        else:
            if device_groups:
                selection_mode = st.radio(
                    "Dispositivos del RAR",
                    ["Todos", "Un dispositivo", "Rango de dispositivos"],
                    horizontal=True,
                    key="rar_device_selection_mode",
                )
                if selection_mode == "Un dispositivo":
                    family = st.selectbox("Familia", list(device_groups), key="rar_device_family")
                    devices = device_groups[family]
                    selected = st.selectbox("Dispositivo", [device for _, device in devices], key="rar_single_device")
                    selected_devices = {selected}
                elif selection_mode == "Rango de dispositivos":
                    family = st.selectbox("Familia del rango", list(device_groups), key="rar_range_family")
                    devices = device_groups[family]
                    numbers = [number for number, _ in devices]
                    if len(numbers) == 1:
                        st.caption(f"Único dispositivo disponible: {devices[0][1]}")
                        selected_devices = {devices[0][1]}
                    else:
                        first, last = st.slider(
                            "Rango inclusivo",
                            min_value=min(numbers),
                            max_value=max(numbers),
                            value=(min(numbers), max(numbers)),
                            key=f"rar_device_range_{family}",
                        )
                        selected_devices = {device for number, device in devices if first <= number <= last}
            else:
                st.info("El RAR no contiene mediciones .ri con dispositivo y número reconocibles.")
    if uploaded and st.button("Importar datos", type="primary"):
        with st.spinner("Importando..."):
            try:
                if input_type == "excel":
                    summary = import_excel(uploaded, repository, duplicate_mode)
                elif input_type == "medicion":
                    summary = import_measurement(uploaded, repository, duplicate_mode)
                elif input_type == "rar":
                    summary = import_rar(uploaded, repository, selected_devices=selected_devices)
                else:
                    raise ValueError("tipo de archivo no reconocido; usa .xlsx, .xls, .xlsm, .ri o .rar")
            except ValueError as error:
                st.error(str(error))
                return
        st.success("Importacion finalizada")
        st.write(f"Mediciones nuevas: {summary.get('mediciones_nuevas', 0)} | Actualizadas: {summary.get('mediciones_actualizadas', 0)} | Ya existentes: {summary.get('ya_existentes', 0)}")
        st.write(f"Duplicados evitados: {summary.get('duplicados_evitados', 0)} | Puntos V/I nuevos: {summary.get('puntos_nuevos', 0)}")
        st.write(f"Tracks Vt nuevos: {summary.get('tracks_nuevos', 0)} | Puntos Track nuevos: {summary.get('track_points_nuevos', 0)}")
        st.write(f"Hojas sin clasificar nuevas: {summary.get('sin_clasificar_nuevos', 0)}")
        if "archivos_seleccionados" in summary:
            st.write(f"Archivos .ri revisados: {summary['archivos_seleccionados']}")
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
    try:
        export_content = export_excel(repository)
    except Exception as error:
        st.error(f"No se pudo generar el Excel; la base sigue disponible para editar: {error}")
    else:
        st.download_button(
            "Exportar base completa (Excel)", export_content, "mediciones_exportadas.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="export_complete_database",
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
    elif selected_table == "Campañas" and not frame.empty:
        edited = st.data_editor(frame[["id", "dispositivo", "numero"]], disabled=["id", "dispositivo"],
                                width="stretch", hide_index=True, key="database_campaigns_editor")
        if st.button("Guardar cambios de campañas", type="primary", key="save_database_campaigns"):
            for row in edited.itertuples(index=False):
                repository.rename_campaign(int(row.id), str(row.numero))
            repository.connection.commit()
            st.success("Campañas actualizadas.")
            st.rerun()
    elif selected_table == "Dispositivos" and not frame.empty:
        edited = st.data_editor(frame[["id", "nombre", "tag", "numero"]], disabled=["id", "tag", "numero"],
                                width="stretch", hide_index=True, key="database_devices_editor")
        if st.button("Guardar cambios de dispositivos", type="primary", key="save_database_devices"):
            for row in edited.itertuples(index=False):
                repository.rename_device(int(row.id), str(row.nombre))
            repository.connection.commit()
            st.success("Dispositivos actualizados.")
            st.rerun()
    else:
        st.dataframe(frame, width="stretch", hide_index=True)
    st.download_button("Descargar tabla visible CSV", frame.to_csv(index=False).encode("utf-8"), f"{selected_table.lower().replace(' ', '_')}.csv", "text/csv", key="database_table_csv")
