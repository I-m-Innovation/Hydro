import os
import pandas
import hampel as hampel
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from constants import p, g, TREBISACCE_HEAD, FLOW_BIN_LS


def _build_mean_efficiency_curve(paths):
    frames = []
    for path in paths:
        df_src = pandas.read_csv(path)
        for col in ["Portata [l/s]", "Rendimento", "Rendimento_is_outlier"]:
            if col in df_src.columns:
                df_src[col] = pandas.to_numeric(df_src[col], errors="coerce")
        if "Rendimento_is_outlier" in df_src.columns:
            df_src = df_src[df_src["Rendimento_is_outlier"] == False]
        df_src = df_src.dropna(subset=["Portata [l/s]", "Rendimento"])
        if df_src.empty:
            continue
        df_src["Portata_bin"] = (df_src["Portata [l/s]"] / FLOW_BIN_LS).round(0) * FLOW_BIN_LS
        frames.append(df_src[["Portata_bin", "Rendimento"]])
    if not frames:
        return pandas.DataFrame(columns=["Portata_bin", "Rendimento_mean", "N"])
    df_all = pandas.concat(frames, ignore_index=True)
    df_all = df_all[df_all["Portata_bin"] > 0]
    grouped = df_all.groupby("Portata_bin", as_index=False)["Rendimento"].agg(
        Rendimento_mean="mean",
        N="count",
    )
    grouped = grouped.sort_values(by="Portata_bin")
    if len(grouped) >= 3:
        window_size = min(50, max(3, len(grouped) // 2))
        results = hampel.hampel(grouped["Rendimento_mean"], window_size=window_size, n_sigma=3.0)
        is_outlier = [False] * len(grouped)
        for idx in results.outlier_indices:
            if 0 <= idx < len(grouped):
                is_outlier[idx] = True
        grouped["Rendimento_mean_is_outlier"] = is_outlier
    else:
        grouped["Rendimento_mean_is_outlier"] = False

    grouped["Rendimento_mean_is_outlier"] = (
        grouped["Rendimento_mean_is_outlier"]
        | (grouped["Rendimento_mean"] > 1)
        | (grouped["Rendimento_mean"] < 0)
    )
    return grouped


def _build_single_efficiency_curve(path, flow_bin_ls=1.0):
    df_src = pandas.read_csv(path)
    for col in ["Portata [l/s]", "Rendimento", "Rendimento_is_outlier"]:
        if col in df_src.columns:
            df_src[col] = pandas.to_numeric(df_src[col], errors="coerce")
    if "Rendimento_is_outlier" in df_src.columns:
        df_src = df_src[df_src["Rendimento_is_outlier"] == False]
    df_src = df_src.dropna(subset=["Portata [l/s]", "Rendimento"])
    if df_src.empty:
        return pandas.DataFrame(columns=["Portata_bin", "Rendimento_mean"])
    df_src["Portata_bin"] = (df_src["Portata [l/s]"] / flow_bin_ls).round(0) * flow_bin_ls
    df_src = df_src[df_src["Portata_bin"] > 0]
    grouped = df_src.groupby("Portata_bin", as_index=False)["Rendimento"].mean()
    grouped = grouped.sort_values(by="Portata_bin")
    grouped["Rendimento"] = grouped["Rendimento"].round(5)
    return grouped.rename(columns={"Rendimento": "Rendimento_mean"})


def build_and_save_mean_curves(calc_paths, charts_dir):
    '''
    Costruisce le curve di rendimento a partire dai CSV con H_calculated.
    - Usa i percorsi in calc_paths (esempio: csv_all\\h_calculated\\DBCAN_filtered_H_calculated.csv).
    - Crea la curva media di rendimento (mean_curve) e le curve dei singoli impianti.
    - Salva i risultati come CSV e grafici HTML.

    mean_curve è un DataFrame con le colonne principali:
    Portata_bin, Rendimento_mean, N, Potenza_attesa_trebisacce [kW]
    '''

    mean_curve = _build_mean_efficiency_curve(list(calc_paths.values()))
    if mean_curve.empty:
        return

    mean_curve["Q_[m3/s]"] = (mean_curve["Portata_bin"] / 1000).round(5)
    mean_curve["Potenza_attesa_trebisacce [kW]"] = (
        mean_curve["Rendimento_mean"] * p * g * TREBISACCE_HEAD * mean_curve["Q_[m3/s]"]
    ) / 1000
    mean_curve["Potenza_attesa_trebisacce [kW]"] = mean_curve["Potenza_attesa_trebisacce [kW]"].round(5)
    mean_curve["Portata_bin"] = mean_curve["Portata_bin"].round(5)
    mean_curve["Rendimento_mean"] = mean_curve["Rendimento_mean"].round(5)

    # costruisci curve di rendimento per i singoli impianti (DBCAN, DBPAR, DBST) e rinomina la colonna Rendimento_mean in modo univoco per ogni impianto
    curve_can = _build_single_efficiency_curve(calc_paths["DBCAN"]).rename(
        columns={"Rendimento_mean": "rendimento_CAN"}
    )
    curve_par = _build_single_efficiency_curve(calc_paths["DBPAR"]).rename(
        columns={"Rendimento_mean": "rendimento_PAR"}
    )
    curve_st = _build_single_efficiency_curve(calc_paths["DBST"]).rename(
        columns={"Rendimento_mean": "rendimento_ST"}
    )
    # unisci le curve dei singoli impianti alla curva media usando Portata_bin come chiave
    mean_curve = mean_curve.merge(curve_can, on="Portata_bin", how="left")
    mean_curve = mean_curve.merge(curve_par, on="Portata_bin", how="left")
    mean_curve = mean_curve.merge(curve_st, on="Portata_bin", how="left")
    # salva la curva media come CSV
    csv_curve_dir = os.path.join("csv_all", "curves")
    os.makedirs(csv_curve_dir, exist_ok=True)
    mean_curve_path = os.path.join(csv_curve_dir, "rendimento_medio_per_turbine_pelton.csv")
    mean_curve.to_csv(mean_curve_path, index=False)
    # costruisci grafico della curva media e grafico con curve di tutti gli impianti + media
    fig_mean = make_subplots(rows=1, cols=1)
    fig_mean.add_trace(
        go.Scatter(
            x=mean_curve["Portata_bin"],
            y=mean_curve["Rendimento_mean"] * 100,
            mode="lines+markers",
            line={"width": 2, "color": "#2563eb"},
            name="Rendimento medio (%)",
        )
    )
    fig_mean.update_layout(
        title_text="Rendimento medio vs Portata (media impianti H_calculated)",
        height=520,
        width=900,
    )
    fig_mean.update_xaxes(title_text="Portata [l/s]")
    fig_mean.update_yaxes(title_text="Rendimento (%)", range=[0, 100])
    fig_mean.write_html(os.path.join(charts_dir, "rendimento_medio_portata_trebisacce.html"))

    fig_all = make_subplots(rows=1, cols=1)
    if not curve_can.empty:
        _plot_curve_segments(fig_all, curve_can, "rendimento_CAN", "Canaletta", ["#93c5fd", "#1f77b4"])
    if not curve_par.empty:
        _plot_curve_segments(fig_all, curve_par, "rendimento_PAR", "Partitore", ["#fdba74", "#ff7f0e"])
    if not curve_st.empty:
        _plot_curve_segments(fig_all, curve_st, "rendimento_ST", "San Teodoro", ["#86efac", "#2ca02c"])

    _plot_mean_segments(fig_all, mean_curve)
    fig_all.update_layout(
        title_text="Curve rendimento: impianti + media",
        height=520,
        width=900,
        showlegend=True,
    )
    fig_all.update_xaxes(
        title_text="Portata [l/s]",
        showgrid=True,
        gridcolor="#d1d5db",
        gridwidth=1,
        showline=True,
        linecolor="#9ca3af",
        linewidth=2,
    )
    fig_all.update_yaxes(
        title_text="Rendimento (%)",
        range=[0, 100],
        showgrid=True,
        gridcolor="#d1d5db",
        gridwidth=1,
        showline=True,
        linecolor="#9ca3af",
        linewidth=2,
    )
    fig_all.write_html(os.path.join(charts_dir, "rendimento_curve_quattro.html"))


def _plot_curve_segments(fig, curve_df, col_name, label, colors):
    if curve_df.empty:
        return
    fig.add_trace(
        go.Scatter(
            x=curve_df["Portata_bin"],
            y=curve_df[col_name] * 100,
            mode="lines",
            line={"width": 2, "color": colors[0]},
            name=label,
            showlegend=True,
        )
    )


def _plot_mean_segments(fig, mean_curve):
    if mean_curve.empty:
        return
    has_outlier_col = "Rendimento_mean_is_outlier" in mean_curve.columns
    if has_outlier_col:
        inliers = mean_curve[mean_curve["Rendimento_mean_is_outlier"] == False]
        outliers = mean_curve[mean_curve["Rendimento_mean_is_outlier"] == True]
    else:
        inliers = mean_curve
        outliers = mean_curve.iloc[0:0]

    if not inliers.empty:
        fig.add_trace(
            go.Scatter(
                x=inliers["Portata_bin"],
                y=inliers["Rendimento_mean"] * 100,
                mode="lines",
                line={"width": 3, "color": "#d62728"},
                name="Media",
                showlegend=True,
            )
        )

    if not outliers.empty:
        fig.add_trace(
            go.Scatter(
                x=outliers["Portata_bin"],
                y=outliers["Rendimento_mean"] * 100,
                mode="markers",
                marker={"size": 6, "color": "#fca5a5", "opacity": 0.6},
                name="Media (outlier)",
                showlegend=True,
            )
        )

    if "Rendimento_mean_is_outlier" in mean_curve.columns:
        candidates = mean_curve[
            (mean_curve["Rendimento_mean_is_outlier"] == False)
            & (mean_curve["Rendimento_mean"] >= 0)
            & (mean_curve["Rendimento_mean"] <= 1)
        ]
    else:
        candidates = mean_curve[(mean_curve["Rendimento_mean"] >= 0) & (mean_curve["Rendimento_mean"] <= 1)]

    if not candidates.empty:
        max_row = candidates.loc[candidates["Rendimento_mean"].idxmax()]
        fig.add_trace(
            go.Scatter(
                x=[max_row["Portata_bin"]],
                y=[max_row["Rendimento_mean"] * 100],
                mode="markers",
                marker={
                    "size": 14,
                    "color": "#111827",
                    "symbol": "circle-open",
                    "line": {"width": 2, "color": "#111827"},
                },
                name="Max rendimento medio",
                showlegend=True,
            )
        )
