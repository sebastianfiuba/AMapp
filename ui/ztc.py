import plotly.graph_objects as go
import streamlit as st

from services.measurements import campaign_analysis, individual_result
from ui.charts import iv_chart
from utils.helpers import format_current


def render(repository):
    st.title("Analisis ZTC")
    campaigns = repository.campaigns()
    if campaigns.empty:
        st.info("Todavia no hay campanas cargadas.")
        return
    labels = [f"{row.dispositivo} - Campana {row.numero}" for row in campaigns.itertuples()]
    selected = st.selectbox("Campana", labels)
    campaign = campaigns.iloc[labels.index(selected)]
    campaign_id = int(campaign.id)
    measurements = repository.measurements(campaign_id)
    st.caption(f"{len(measurements)} medicion(es) disponibles")
    if st.button("Calcular / actualizar ZTC", type="primary"):
        try:
            result, _ = campaign_analysis(repository, campaign_id)
            st.session_state[f"ztc_{campaign_id}"] = result
            st.success("Analisis guardado.")
        except ValueError as error:
            st.error(str(error))
    result = st.session_state.get(f"ztc_{campaign_id}")
    stored = repository.ztc_results()
    if result is None and not stored.empty and campaign_id in stored.campana_id.values:
        row = stored[stored.campana_id == campaign_id].iloc[0]
        result = {"vt_ztc": row.vt_ztc, "i_ztc": row.i_ztc, "cantidad_mediciones": len(measurements)}
    if result:
        st.metric("VT ZTC", f"{result['vt_ztc']:.6g} V")
        st.metric("I ZTC", format_current(result["i_ztc"]))
        points = {int(row.id): repository.points(int(row.id)) for row in measurements.itertuples()}
        st.plotly_chart(iv_chart(measurements, points, (result["vt_ztc"], result["i_ztc"])), use_container_width=True)
        rows = []
        for measurement in measurements.itertuples():
            try:
                rows.append({"Archivo": measurement.archivo, **individual_result(repository, int(measurement.id), result["vt_ztc"], result["i_ztc"])})
            except ValueError as error:
                st.warning(f"{measurement.archivo}: {error}")
        if rows:
            st.dataframe(rows, use_container_width=True, hide_index=True)
