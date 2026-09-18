import plotly.graph_objects as go


def campaign_context(value: object) -> str:
    text = str(value or "").casefold()
    for marker, label in (("posthorno", "posthorno"), ("postcañon", "postcañón"), ("postcanon", "postcañón"),
                          ("curie", "Curie"), ("nada", "nada"), ("temperatura", "temperatura"), ("temp", "temperatura")):
        if marker in text:
            return label
    return "sin clasificar"


def iv_chart(measurements, points_by_measurement, ztc=None):
    figure = go.Figure()
    for row in measurements.itertuples():
        points = points_by_measurement[int(row.id)]
        campaign = getattr(row, "campana", "")
        device = getattr(row, "dispositivo", "")
        description = getattr(row, "descripcion", "")
        label = " | ".join(str(value) for value in (device, campaign, campaign_context(campaign), row.archivo, description) if str(value).strip())
        figure.add_trace(go.Scatter(x=points.v, y=points.i, mode="lines+markers", name=label, hovertemplate=f"{label}<br>V=%{{x}} V<br>I=%{{y}} A<extra></extra>"))
    if ztc:
        figure.add_trace(go.Scatter(x=[ztc[0]], y=[ztc[1]], mode="markers", name="ZTC", marker={"size": 13, "symbol": "star", "color": "crimson"}))
    figure.update_layout(height=560, margin={"l": 70, "r": 30, "t": 55, "b": 70}, xaxis_title="Voltaje [V]", yaxis_title="Corriente [A]", hovermode="x unified", template="plotly_white", legend_title="Medición", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font={"family": "Source Sans 3, sans-serif", "color": "#17212b"})
    figure.update_xaxes(showgrid=True, zeroline=True)
    figure.update_yaxes(showgrid=True, zeroline=True)
    return figure


def track_chart(tracks, points_by_track):
    figure = go.Figure()
    for row in tracks.itertuples():
        points = points_by_track[int(row.id)]
        figure.add_trace(go.Scatter(x=points.t, y=points.vt, mode="lines", name=f"{row.dispositivo} | {row.canal} | {row.archivo}"))
    figure.update_layout(height=560, margin={"l": 70, "r": 30, "t": 55, "b": 70}, xaxis_title="Tiempo [s]", yaxis_title="Vt [V]", hovermode="x unified", template="plotly_white", legend_title="Track Vt", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font={"family": "Source Sans 3, sans-serif", "color": "#17212b"})
    figure.update_xaxes(showgrid=True, zeroline=True)
    figure.update_yaxes(showgrid=True, zeroline=True)
    return figure


def chart_downloads(figure, filename: str, key: str):
    import streamlit as st

    st.download_button("Descargar gráfico HTML", figure.to_html(include_plotlyjs="cdn").encode("utf-8"), f"{filename}.html", "text/html", key=f"{key}_html")
    for file_format, mime in (("png", "image/png"), ("svg", "image/svg+xml")):
        try:
            content = figure.to_image(format=file_format)
        except (ValueError, RuntimeError):
            continue
        st.download_button(f"Descargar {file_format.upper()}", content, f"{filename}.{file_format}", mime, key=f"{key}_{file_format}")
