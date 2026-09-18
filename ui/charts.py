import plotly.graph_objects as go


CURVE_COLORS = ("#0c7285", "#bd7b19", "#c34d46", "#4f6d7a", "#6b5b95", "#4d8b5f")
ZTC_COLOR = "#a61b29"


def style_figure(figure, height: int = 560, right_margin: int = 30):
    figure.update_layout(
        height=height,
        margin={"l": 70, "r": right_margin, "t": 55, "b": 70},
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Source Sans 3, sans-serif", "color": "#17212b"},
    )
    return figure


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
        figure.add_trace(go.Scatter(x=[ztc[0]], y=[ztc[1]], mode="markers", name="ZTC", marker={"size": 13, "symbol": "star", "color": ZTC_COLOR}))
    style_figure(figure)
    figure.update_layout(xaxis_title="Voltaje [V]", yaxis_title="Corriente [A]", hovermode="x unified", legend_title="Medición")
    figure.update_xaxes(showgrid=True, zeroline=True)
    figure.update_yaxes(showgrid=True, zeroline=True)
    return figure


def track_chart(tracks, points_by_track):
    figure = go.Figure()
    for row in tracks.itertuples():
        points = points_by_track[int(row.id)]
        figure.add_trace(go.Scatter(x=points.t, y=points.vt, mode="lines", name=f"{row.dispositivo} | {row.canal} | {row.archivo}"))
    style_figure(figure)
    figure.update_layout(xaxis_title="Tiempo [s]", yaxis_title="Vt [V]", hovermode="x unified", legend_title="Track Vt")
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
