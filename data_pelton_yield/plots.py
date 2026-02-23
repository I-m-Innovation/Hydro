import os
import pandas
import hampel as hampel
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def _load_plot_data_from_path(data_path):
    df_plot = pandas.read_csv(data_path)
    for col in ["Portata [l/s]", "Rendimento"]:
        if col in df_plot.columns:
            df_plot[col] = pandas.to_numeric(df_plot[col], errors="coerce")
    df_plot = df_plot.dropna(subset=["Portata [l/s]", "Rendimento"])
    outliers = pandas.DataFrame()
    inliers = pandas.DataFrame()
    if "Rendimento_is_outlier" in df_plot.columns:
        outliers = df_plot[df_plot["Rendimento_is_outlier"] == True]
        inliers = df_plot[df_plot["Rendimento_is_outlier"] == False]
    return df_plot, inliers, outliers


def _load_power_plot_data_from_path(data_path):
    df_plot = pandas.read_csv(data_path)
    for col in ["Portata [l/s]", "Potenza [kW]", "Potenza_attesa [kW]"]:
        if col in df_plot.columns:
            df_plot[col] = pandas.to_numeric(df_plot[col], errors="coerce")
    df_plot = df_plot.dropna(subset=["Portata [l/s]", "Potenza [kW]", "Potenza_attesa [kW]"])
    return df_plot


def _downsample(df, max_points):
    if max_points is None or len(df) <= max_points:
        return df
    return df.sample(n=max_points, random_state=42)


def plot_rendimento_potenza_dual_axis(fig, row, col, data_path, title, legend_group, max_points=None):
    df_plot, inliers, outliers = _load_plot_data_from_path(data_path)
    inliers = _downsample(inliers, max_points)
    outliers = _downsample(outliers, max_points)
    if outliers.empty and inliers.empty:
        df_plot = _downsample(df_plot, max_points)

    fig.add_trace(
        go.Scattergl(
            x=inliers["Portata [l/s]"],
            y=inliers["Rendimento"] * 100,
            mode="markers",
            marker={"size": 4, "color": "#2563eb", "opacity": 0.6},
            name="Rendimento (%)",
            legendgroup=legend_group,
            legendgrouptitle_text=legend_group,
            showlegend=True,
        ),
        row=row,
        col=col,
    )

    if not outliers.empty:
        fig.add_trace(
            go.Scattergl(
                x=outliers["Portata [l/s]"],
                y=outliers["Rendimento"] * 100,
                mode="markers",
                marker={"size": 2, "color": "#93c5fd", "opacity": 0.3},
                name="Outliers rendimento",
                legendgroup=legend_group,
                showlegend=True,
            ),
            row=row,
            col=col,
        )
    if outliers.empty and inliers.empty:
        fig.add_trace(
            go.Scattergl(
                x=df_plot["Portata [l/s]"],
                y=df_plot["Rendimento"] * 100,
                mode="markers",
                marker={"size": 4, "color": "#2563eb", "opacity": 0.6},
                name="Rendimento (%)",
                legendgroup=legend_group,
                showlegend=True,
            ),
            row=row,
            col=col,
        )

    df_power = _load_power_plot_data_from_path(data_path)
    df_power = _downsample(df_power, max_points)
    if not df_power.empty:
        df_power = df_power.sort_values(by="Portata [l/s]")
        if len(df_power) >= 3:
            window_size = min(50, max(3, len(df_power) // 2))
            results_pow_meas = hampel.hampel(df_power["Potenza [kW]"], window_size=window_size, n_sigma=3.0)
            is_outlier_meas = [False] * len(df_power)
            for idx in results_pow_meas.outlier_indices:
                if 0 <= idx < len(df_power):
                    is_outlier_meas[idx] = True
            df_power["Potenza_is_outlier"] = is_outlier_meas
        else:
            df_power["Potenza_is_outlier"] = False

        if "Potenza_attesa_is_outlier" not in df_power.columns:
            if len(df_power) >= 3:
                results_pow_exp = hampel.hampel(df_power["Potenza_attesa [kW]"], window_size=window_size, n_sigma=3.0)
                is_outlier_exp = [False] * len(df_power)
                for idx in results_pow_exp.outlier_indices:
                    if 0 <= idx < len(df_power):
                        is_outlier_exp[idx] = True
                df_power["Potenza_attesa_is_outlier"] = is_outlier_exp
            else:
                df_power["Potenza_attesa_is_outlier"] = False

        df_power_meas_out = df_power[df_power["Potenza_is_outlier"] == True]
        df_power_exp_out = df_power[df_power["Potenza_attesa_is_outlier"] == True]

        if not df_power_meas_out.empty:
            fig.add_trace(
                go.Scattergl(
                    x=df_power_meas_out["Portata [l/s]"],
                    y=df_power_meas_out["Potenza [kW]"],
                    mode="markers",
                    marker={"size": 2, "color": "#fdba74", "opacity": 0.3},
                    name="Outliers potenza misurata",
                    legendgroup=legend_group,
                    showlegend=True,
                ),
                row=row,
                col=col,
                secondary_y=True,
            )

        if not df_power_exp_out.empty:
            fig.add_trace(
                go.Scattergl(
                    x=df_power_exp_out["Portata [l/s]"],
                    y=df_power_exp_out["Potenza_attesa [kW]"],
                    mode="markers",
                    marker={"size": 2, "color": "#86efac", "opacity": 0.3},
                    name="Outliers potenza attesa",
                    legendgroup=legend_group,
                    showlegend=True,
                ),
                row=row,
                col=col,
                secondary_y=True,
            )

        df_power_meas_in = df_power[df_power["Potenza_is_outlier"] == False]
        fig.add_trace(
            go.Scatter(
                x=df_power_meas_in["Portata [l/s]"],
                y=df_power_meas_in["Potenza [kW]"],
                mode="lines",
                line={"width": 2, "color": "#f97316"},
                name="Potenza misurata [kW]",
                legendgroup=legend_group,
                showlegend=True,
            ),
            row=row,
            col=col,
            secondary_y=True,
        )
        df_power_exp_in = df_power[df_power["Potenza_attesa_is_outlier"] == False]
        fig.add_trace(
            go.Scatter(
                x=df_power_exp_in["Portata [l/s]"],
                y=df_power_exp_in["Potenza_attesa [kW]"],
                mode="lines",
                line={"width": 2, "color": "#10b981"},
                name="Potenza attesa [kW]",
                legendgroup=legend_group,
                showlegend=True,
            ),
            row=row,
            col=col,
            secondary_y=True,
        )

    fig.update_xaxes(
        title_text="Portata [l/s]",
        row=row,
        col=col,
        dtick=10,
        showgrid=True,
        gridcolor="#d1d5db",
        gridwidth=1,
    )
    fig.update_yaxes(
        title_text="Rendimento (%)",
        row=row,
        col=col,
        range=[0, 100],
        fixedrange=True,
        dtick=5,
        showgrid=True,
        gridcolor="#d1d5db",
        gridwidth=1,
        secondary_y=False,
    )
    fig.update_yaxes(
        title_text="Potenza [kW]",
        row=row,
        col=col,
        secondary_y=True,
        range=[0, 500],
        fixedrange=True,
        dtick=50,
        showgrid=True,
        gridcolor="#d1d5db",
        gridwidth=1,
    )
    fig.add_annotation(
        text=title,
        xref="x domain",
        yref="y domain",
        x=0.5,
        y=1.05,
        showarrow=False,
        row=row,
        col=col,
    )


def _load_3d_plot_data(data_path, use_filtered=False):
    df = pandas.read_csv(data_path)
    for col in ["Portata [l/s]", "Rendimento", "Rendimento_filtered", "Pressione [bar]"]:
        if col in df.columns:
            df[col] = pandas.to_numeric(df[col], errors="coerce")
    y_col = "Rendimento_filtered" if use_filtered and "Rendimento_filtered" in df.columns else "Rendimento"
    df = df.dropna(subset=["Portata [l/s]", y_col, "Pressione [bar]"])
    return df, y_col


def _add_3d_trace(fig, row, col, data_path, title, use_filtered=False, max_points=None):
    df, y_col = _load_3d_plot_data(data_path, use_filtered=use_filtered)
    df = _downsample(df, max_points)
    outliers = pandas.DataFrame()
    inliers = df
    if "Rendimento_is_outlier" in df.columns:
        outliers = df[df["Rendimento_is_outlier"] == True]
        inliers = df[df["Rendimento_is_outlier"] == False]

    if not inliers.empty:
        fig.add_trace(
            go.Scatter3d(
                x=inliers["Portata [l/s]"],
                y=inliers[y_col] * 100,
                z=inliers["Pressione [bar]"],
                mode="markers",
                marker={"size": 2, "color": "#2563eb", "opacity": 0.6},
                name=f"{title} 3D",
                showlegend=False,
            ),
            row=row,
            col=col,
        )
    if not outliers.empty:
        fig.add_trace(
            go.Scatter3d(
                x=outliers["Portata [l/s]"],
                y=outliers[y_col] * 100,
                z=outliers["Pressione [bar]"],
                mode="markers",
                marker={"size": 2, "color": "#60a5fa"},
                name=f"{title} 3D outliers",
                showlegend=False,
            ),
            row=row,
            col=col,
        )
    scene_key = {1: "scene", 2: "scene2", 3: "scene3"}[col]
    fig.update_layout(
        **{
            scene_key: dict(
                xaxis=dict(
                    title="Portata [l/s]",
                    showgrid=True,
                    gridcolor="#000000",
                    showbackground=True,
                    backgroundcolor="#f3f4f6",
                    showline=True,
                    linecolor="#000000",
                    zeroline=False,
                ),
                yaxis=dict(
                    title="Rendimento (%)",
                    showgrid=True,
                    gridcolor="#000000",
                    showbackground=True,
                    backgroundcolor="#f3f4f6",
                    showline=True,
                    linecolor="#000000",
                    range=[0, 100],
                    zeroline=False,
                ),
                zaxis=dict(
                    title="Pressione [bar]",
                    showgrid=True,
                    gridcolor="#000000",
                    showbackground=True,
                    backgroundcolor="#f3f4f6",
                    showline=True,
                    linecolor="#000000",
                    zeroline=False,
                ),
            )
        }
    )


def _add_pressure_2d(fig, row, col, data_path, title, use_filtered=False, max_points=None):
    df, y_col = _load_3d_plot_data(data_path, use_filtered=use_filtered)
    df = _downsample(df, max_points)
    fig.add_trace(
        go.Scatter(
            x=df["Portata [l/s]"],
            y=df[y_col] * 100,
            mode="markers",
            marker=dict(
                size=4,
                color=df["Pressione [bar]"],
                colorscale="Viridis",
                showscale=(row == 3 and col == 3),
                colorbar=dict(
                    title="Pressione [bar]",
                    x=1.05,
                    y=0.13,
                    len=0.3,
                    
                ),
                opacity=0.8,
            ),
            name=f"{title} Pressione",
            showlegend=False,
        ),
        row=row,
        col=col,
    )
    fig.update_xaxes(
        title_text="Portata [l/s]",
        row=row,
        col=col,
        dtick=5,
        showgrid=True,
        gridcolor="#bdbdbd",
    )
    fig.update_yaxes(
        title_text="Rendimento (%)",
        row=row,
        col=col,
        range=[0, 100],
        dtick=5,
        showgrid=True,
        gridcolor="#cfcfcf",
    )


def plot_h_calculated_grid(calc_paths, charts_dir, max_points=10000, use_filtered=False):
    fig = make_subplots(
        rows=3,
        cols=3,
        specs=[
            [{"secondary_y": True}, {"secondary_y": True}, {"secondary_y": True}],
            [{"type": "scene"}, {"type": "scene"}, {"type": "scene"}],
            [{}, {}, {}],
        ],
        horizontal_spacing=0.06,
        vertical_spacing=0.1,
    )
    plot_rendimento_potenza_dual_axis(
        fig, 1, 1, calc_paths["DBCAN"], "Canaletta (H_calculated)", "Canaletta (H_calculated)", max_points=max_points
    )
    plot_rendimento_potenza_dual_axis(
        fig, 1, 2, calc_paths["DBPAR"], "Partitore (H_calculated)", "Partitore (H_calculated)", max_points=max_points
    )
    plot_rendimento_potenza_dual_axis(
        fig, 1, 3, calc_paths["DBST"], "San Teodoro (H_calculated)", "San Teodoro (H_calculated)", max_points=max_points
    )

    _add_3d_trace(fig, 2, 1, calc_paths["DBCAN"], "Canaletta", use_filtered=use_filtered, max_points=max_points)
    _add_3d_trace(fig, 2, 2, calc_paths["DBPAR"], "Partitore", use_filtered=use_filtered, max_points=max_points)
    _add_3d_trace(fig, 2, 3, calc_paths["DBST"], "San Teodoro", use_filtered=use_filtered, max_points=max_points)

    _add_pressure_2d(fig, 3, 1, calc_paths["DBCAN"], "Canaletta", use_filtered=use_filtered, max_points=max_points)
    _add_pressure_2d(fig, 3, 2, calc_paths["DBPAR"], "Partitore", use_filtered=use_filtered, max_points=max_points)
    _add_pressure_2d(fig, 3, 3, calc_paths["DBST"], "San Teodoro", use_filtered=use_filtered, max_points=max_points)

    fig.update_layout(
        height=1650,
        width=1600,
        title_text="Rendimento e Potenza vs Portata (H calculated) + 3D (Pressione) + 2D Pressione",
        showlegend=True,
        legend=dict(
            x=1.02,
            y=1.0,
            xanchor="left",
            yanchor="top",
        ),
        margin=dict(r=360, l=40, t=80, b=40),
    )
    fig.write_html(os.path.join(charts_dir, "pelton_yield_curve.html"))
    fig.show()
