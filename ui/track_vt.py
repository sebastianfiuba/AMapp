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
    points = {int(row.id): repository.track_points(int(row.id)) for row in tracks.itertuples()}
    figure = track_chart(tracks, points)
    st.caption(f"{len(tracks)} tracks Vt")
    st.plotly_chart(figure, width="stretch")
    chart_downloads(figure, "comparacion_track_vt", "track_page")
    st.dataframe(tracks[["dispositivo", "campana", "archivo", "canal", "fecha"]], width="stretch", hide_index=True)