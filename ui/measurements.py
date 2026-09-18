import streamlit as st

from ui.charts import chart_downloads, iv_chart
from ui.measurement_editor import render_measurement_editor
from ui.track_vt import render_panel as render_track_panel
from ui.theme import banner


def render_iv_panel(repository):
    devices = repository.devices()
    if devices.empty:
        st.info("Todavia no hay dispositivos cargados.")
        return
    device_options = {row.nombre: int(row.id) for row in devices.itertuples()}
    selected_devices = st.multiselect("Dispositivos", list(device_options), default=list(device_options)[:1], key="measurements_devices")
    device_ids = [device_options[name] for name in selected_devices]
    campaigns = repository.campaigns()
    campaigns = campaigns[campaigns.dispositivo_id.isin(device_ids)]
    campaign_options = {f"{row.dispositivo} | {row.numero}": int(row.id) for row in campaigns.itertuples()}
    selected_campaigns = st.multiselect("Campañas", list(campaign_options), default=list(campaign_options)[:1], key="measurements_campaigns")
    campaign_ids = [campaign_options[label] for label in selected_campaigns]
    measurements = repository.iv_measurements(include_deleted=True)
    measurements = measurements[measurements.dispositivo_id.isin(device_ids) & measurements.campana_id.isin(campaign_ids)]
    if measurements.empty:
        st.info("Selecciona un dispositivo y una campaña con datos I-V.")
        return
    render_measurement_editor(repository, measurements, "measurements_iv")
    measurement_options = {f"{row.dispositivo} | {row.campana} | {row.archivo}": int(row.id) for row in measurements.itertuples()}
    active_labels = [label for label, measurement_id in measurement_options.items() if bool(measurements.loc[measurements.id == measurement_id, "activa"].iloc[0])]
    selected_measurements = st.multiselect("Mediciones activas para la vista previa", list(measurement_options), default=active_labels[:3], key="measurements_preview")
    selected_ids = {measurement_options[label] for label in selected_measurements}
    preview = measurements[measurements.id.isin(selected_ids) & measurements.activa.astype(bool)]
    if preview.empty:
        st.info("Selecciona al menos una medición para previsualizar.")
        return
    points = {int(row.id): repository.points(int(row.id)) for row in preview.itertuples()}
    figure = iv_chart(preview, points)
    st.subheader("Vista previa")
    st.plotly_chart(figure, width="stretch")
    chart_downloads(figure, "mediciones_seleccionadas", "measurements_preview")
    st.dataframe(preview[["dispositivo", "campana", "archivo", "fecha", "descripcion", "clase", "estado"]], width="stretch", hide_index=True)
    selected = st.selectbox("Detalle de medición", list(measurement_options), key="measurement_detail")
    row = measurements[measurements.id == measurement_options[selected]].iloc[0]
    st.dataframe(row[["dispositivo", "campana", "archivo", "fecha", "descripcion", "clase", "estado"]].to_frame("Valor"), width="stretch")
    st.dataframe(repository.points(int(row.id)), width="stretch", hide_index=True)


def render(repository):
    banner("Explorador", "Mediciones", "Consultá curvas I-V y mediciones Track Vt desde una sola sección.")
    iv_tab, track_tab = st.tabs(["I-V", "Track Vt"])
    with iv_tab:
        render_iv_panel(repository)
    with track_tab:
        render_track_panel(repository)
