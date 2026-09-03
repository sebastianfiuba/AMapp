import plotly.graph_objects as go


def iv_chart(measurements, points_by_measurement, ztc=None):
    figure = go.Figure()
    for row in measurements.itertuples():
        points = points_by_measurement[int(row.id)]
        figure.add_trace(go.Scatter(x=points.v, y=points.i, mode="lines+markers", name=str(row.archivo)))
    if ztc:
        figure.add_trace(go.Scatter(x=[ztc[0]], y=[ztc[1]], mode="markers", name="ZTC", marker={"size": 13, "symbol": "star", "color": "crimson"}))
    figure.update_layout(xaxis_title="Voltaje [V]", yaxis_title="Corriente [A]", hovermode="x unified", template="plotly_white", legend_title="Medicion")
    figure.update_xaxes(showgrid=True, zeroline=True)
    figure.update_yaxes(showgrid=True, zeroline=True)
    return figure
