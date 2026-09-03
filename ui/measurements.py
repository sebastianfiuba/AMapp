import streamlit as st


def render(repository):
    st.title("Mediciones")
    devices = repository.devices()
    if devices.empty:
        st.info("Todavia no hay dispositivos cargados.")
        return
    device_name = st.selectbox("Dispositivo", devices.nombre.tolist())
    device_id = int(devices.loc[devices.nombre == device_name, "id"].iloc[0])
    campaigns = repository.campaigns(device_id)
    campaign_label = st.selectbox("Campana", campaigns.numero.tolist())
    campaign_id = int(campaigns.loc[campaigns.numero == campaign_label, "id"].iloc[0])
    measurements = repository.measurements(campaign_id)
    selected = st.selectbox("Medicion", measurements.archivo.tolist())
    row = measurements[measurements.archivo == selected].iloc[0]
    st.dataframe(row[["dispositivo", "campana", "archivo", "fecha", "descripcion", "clase", "estado"]].to_frame("Valor"), use_container_width=True)
    st.dataframe(repository.points(int(row.id)), use_container_width=True, hide_index=True)
