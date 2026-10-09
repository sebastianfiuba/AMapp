from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from services.vt_analysis import (
    available_temperatures,
    delta_vt_at_currents,
    parse_target_currents,
    preferred_temperature,
)
from ui.theme import banner


def render_automatic(repository) -> None:
    banner("Análisis automático", "Desplazamiento de VT", "Calculá VT y ΔVT a corriente constante con mediciones I‑V del mismo dispositivo.", "ztc")
    devices = repository.devices()
    if devices.empty:
        st.info("Todavía no hay dispositivos con mediciones I-V.")
        return
    device_options = {row.nombre: int(row.id) for row in devices.itertuples()}
    selected_device = st.selectbox("Dispositivo", list(device_options), key="automatic_delta_vt_device")
    measurements = repository.iv_measurements(include_deleted=True, include_unaccepted=True)
    measurements = measurements[
        (measurements.dispositivo_id == device_options[selected_device])
        & measurements.activa.astype(bool)
        & measurements.aceptada.astype(bool)
    ]
    st.caption("Se incluyen automáticamente las mediciones I-V activas y aceptadas del dispositivo.")
    _render_current_modes(repository, measurements, "automatic_delta_vt")


def render_manual(repository) -> None:
    st.subheader("Análisis manual de VT (ΔVT)")
    st.caption("Filtrá y elegí mediciones I-V de un único dispositivo. No se usan Tracks Vt.")
    devices = repository.devices()
    if devices.empty:
        st.info("Todavía no hay dispositivos con mediciones I-V.")
        return
    device_options = {row.nombre: int(row.id) for row in devices.itertuples()}
    selected_device = st.selectbox("Dispositivo", list(device_options), key="manual_delta_vt_device")
    device_id = device_options[selected_device]
    measurements = repository.iv_measurements(include_deleted=True, include_unaccepted=True)
    measurements = measurements[measurements.dispositivo_id == device_id]
    campaigns = repository.campaigns(device_id)
    campaign_options = {
        f"{row.numero} (id {row.id})": int(row.id)
        for row in campaigns.itertuples()
    }
    selected_campaigns = st.multiselect("Campañas", list(campaign_options), key="manual_delta_vt_campaigns")
    if selected_campaigns:
        campaign_ids = [campaign_options[label] for label in selected_campaigns]
        measurements = measurements[measurements.campana_id.isin(campaign_ids)]
    search_text = st.text_input("Buscar en todas las columnas", key="manual_delta_vt_search")
    state_options = sorted(measurements.estado.dropna().astype(str).unique()) if not measurements.empty else []
    filter_states = st.multiselect("Estados", state_options, key="manual_delta_vt_states")
    filter_date = st.text_input("Filtro de fecha", placeholder="Ej.: 2025-03", key="manual_delta_vt_date")
    class_options = sorted(measurements.clase.dropna().astype(str).unique()) if not measurements.empty else []
    filter_classes = st.multiselect("Clase", class_options, key="manual_delta_vt_classes")
    if search_text:
        searchable = measurements.fillna("").astype(str).agg(" ".join, axis=1)
        measurements = measurements[searchable.str.contains(search_text, case=False, regex=False)]
    if filter_states:
        measurements = measurements[measurements.estado.astype(str).isin(filter_states)]
    if filter_date:
        measurements = measurements[measurements.fecha.astype(str).str.contains(filter_date, case=False, regex=False)]
    if filter_classes:
        measurements = measurements[measurements.clase.astype(str).isin(filter_classes)]
    if measurements.empty:
        st.info("No hay mediciones I-V para los filtros seleccionados.")
        return

    measurement_options = {
        f"{row.campana} | {row.archivo} (id {row.id})": int(row.id)
        for row in measurements.itertuples()
    }
    default_measurements = [
        label for label, measurement_id in measurement_options.items()
        if bool(measurements.loc[measurements.id == measurement_id, "activa"].iloc[0])
        and bool(measurements.loc[measurements.id == measurement_id, "aceptada"].iloc[0])
    ]
    selected_labels = st.multiselect(
        "Mediciones seleccionadas",
        list(measurement_options),
        default=default_measurements,
        key="manual_delta_vt_measurements",
    )
    selected_ids = [measurement_options[label] for label in selected_labels]
    selected = measurements[measurements.id.isin(selected_ids)]
    if selected.empty:
        st.info("Seleccioná al menos una medición.")
        return
    _render_current_modes(repository, selected, "manual_delta_vt")


def _render_current_modes(repository, measurements: pd.DataFrame, key: str) -> None:
    if measurements.empty:
        st.info("No hay mediciones I-V activas y aceptadas para analizar.")
        return
    temperatures = available_temperatures(measurements)
    temperature_options = [None, *temperatures]
    default_temperature = preferred_temperature(temperatures)
    selected_temperature = st.selectbox(
        "Temperatura del barrido",
        temperature_options,
        index=temperature_options.index(default_temperature),
        format_func=lambda temperature: (
            "Sin filtro (todas las temperaturas)" if temperature is None else f"{temperature:g} °C"
        ),
        key=f"{key}_temperature",
        help="Si existe un barrido a 26 °C se prioriza; si no, se usa 28 °C. También podés elegir otra temperatura o analizar todas.",
    )
    if selected_temperature is not None:
        measurements = measurements[
            measurements.apply(
                lambda row: extract_temperature(row) == selected_temperature,
                axis=1,
            )
        ]
        st.caption(f"Se analizarán los barridos identificados a {selected_temperature:g} °C.")
    if measurements.empty:
        st.info("No hay mediciones a la temperatura seleccionada.")
        return
    tabs = st.tabs(["Una corriente", "Múltiples corrientes"])
    with tabs[0]:
        current = st.number_input("Corriente objetivo [A]", value=0.00017, format="%.8g", key=f"{key}_single_current")
        _render_comparison(repository, measurements, [float(current)], f"{key}_single")
    with tabs[1]:
        value = st.text_input(
            "Corrientes objetivo [A], separadas por punto y coma",
            value="0.0001; 0.00017; 0.0002",
            key=f"{key}_multiple_currents",
        )
        try:
            currents = parse_target_currents(value)
        except ValueError as error:
            st.error(str(error))
        else:
            _render_comparison(repository, measurements, currents, f"{key}_multiple")


def _render_comparison(repository, measurements: pd.DataFrame, currents: list[float], key: str) -> None:
    options = {
        f"{row.campana} | {row.archivo} (id {row.id})": int(row.id)
        for row in measurements.itertuples()
    }
    reference_label = st.selectbox("Medición de referencia", list(options), key=f"{key}_reference")
    reference_id = options[reference_label]
    try:
        results, warnings = delta_vt_at_currents(repository, measurements, currents, reference_id)
    except ValueError as error:
        st.error(str(error))
        return
    for warning in dict.fromkeys(warnings):
        st.warning(warning)
    if results.empty:
        st.info("No fue posible interpolar VT en el rango de las mediciones seleccionadas.")
        return
    st.caption("ΔVT = VT de la medición − VT de referencia. La interpolación es lineal y no extrapola.")
    st.dataframe(
        results[["Medición", "Corriente [A]", "VT [V]", "ΔVT [V]", "Referencia"]],
        width="stretch",
        hide_index=True,
        key=f"{key}_results",
    )
    figure = go.Figure()
    for label, group in results.groupby("Medición", sort=False):
        figure.add_trace(go.Scatter(
            x=group["Corriente [A]"],
            y=group["ΔVT [V]"],
            mode="lines+markers",
            name=label,
        ))
    figure.update_layout(
        xaxis_title="Corriente [A]",
        yaxis_title="ΔVT [V]",
        hovermode="x unified",
    )
    st.plotly_chart(figure, width="stretch", key=f"{key}_chart")
