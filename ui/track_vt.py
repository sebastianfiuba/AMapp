import pandas as pd
import streamlit as st

from ui.charts import chart_downloads, track_chart
from ui.theme import banner


def render(repository):
    banner("Seguimiento temporal", "Análisis Track Vt", "Observá la deriva de Vt durante irradiación, temperatura o tratamiento.", "track")
    devices = repository.devices()
    if devices.empty:
        st.info("Todavía no hay dispositivos con Track Vt.")
        return
    device_labels = [f"{row.nombre} | tag={row.tag} | n={row.numero}" for row in devices.itertuples()]
    selected_devices = st.multiselect("Dispositivos", device_labels, default=device_labels[:1])
    device_ids = [int(devices.iloc[device_labels.index(label)].id) for label in selected_devices]
    frames = [repository.tracks(device_id=device_id) for device_id in device_ids]
    tracks = pd.concat([frame for frame in frames if not frame.empty], ignore_index=True) if any(not frame.empty for frame in frames) else pd.DataFrame()
    if tracks.empty:
        st.info("Los dispositivos seleccionados no tienen Track Vt.")
        return
    channels = sorted(tracks.canal.dropna().astype(str).unique())
    selected_channels = st.multiselect("Canal del instrumento", channels, default=channels, key="track_channels")
    if selected_channels:
        tracks = tracks[tracks.canal.astype(str).isin(selected_channels)]
    if tracks.empty:
        st.info("No hay Tracks Vt para los canales seleccionados.")
        return
    points = {int(row.id): repository.track_points(int(row.id)) for row in tracks.itertuples()}
    figure = track_chart(tracks, points)
    st.caption(f"{len(tracks)} tracks Vt")
    st.plotly_chart(figure, width="stretch")
    chart_downloads(figure, "comparacion_track_vt", "track_page")
    st.dataframe(tracks[["id", "dispositivo", "campana", "medicion", "canal", "fecha"]], width="stretch", hide_index=True)
    selected_label = st.selectbox(
        "Previsualizar medición Track Vt",
        tracks.apply(lambda row: f"ID {row.id} | {row.dispositivo} | {row.medicion} | {row.canal}", axis=1).tolist(),
        key="track_measurement_preview",
    )
    selected_id = int(selected_label.split("|")[0].replace("ID", "").strip())
    selected_row = tracks[tracks.id == selected_id].iloc[0]
    selected_points = repository.track_points(selected_id)
    st.dataframe(pd.DataFrame({
        "Característica": ["ID", "Dispositivo", "Medición", "Canal", "Puntos", "Tiempo inicial [s]", "Tiempo final [s]", "Vt mínimo [V]", "Vt máximo [V]"],
        "Valor": [selected_id, selected_row.dispositivo, selected_row.medicion, selected_row.canal, len(selected_points),
                  selected_points.t.min() if not selected_points.empty else "-", selected_points.t.max() if not selected_points.empty else "-",
                  selected_points.vt.min() if not selected_points.empty else "-", selected_points.vt.max() if not selected_points.empty else "-"],
    }), hide_index=True, width="stretch")
    st.dataframe(selected_points, hide_index=True, width="stretch")