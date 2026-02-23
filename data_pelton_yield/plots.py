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


def plot_h_calculated_grid(calc_paths, charts_dir, max_points=10000):
    fig = make_subplots(
        rows=1,
        cols=3,
        specs=[[{"secondary_y": True}, {"secondary_y": True}, {"secondary_y": True}]],
        horizontal_spacing=0.06,
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

    fig.update_layout(
        height=520,
        width=1600,
        title_text="Rendimento e Potenza vs Portata (H calculated)",
        showlegend=True,
    )
    fig.write_html(os.path.join(charts_dir, "pelton_yield_curve.html"))
    fig.show()
