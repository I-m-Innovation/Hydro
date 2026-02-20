'''

with this code we'll try to predict the yield of a pelton turbine based on the data 
we have collected during years of operation is some facilities.
The datas are collected in a csv file and we'll first to use those to deduce the 
actual yield of those turbines to then be able to predict the power output 
of the turbines based on the water flow and the head of the water. This information 
will be used to predict the power output for the facility called "trebisacce" which 
is to use a pelton turbine to generate power from the water flow of a river or stream.
'''

import os 
import pandas
import hampel as hampel

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    _HAS_PLOTLY = True
except Exception:
    go = None
    make_subplots = None
    _HAS_PLOTLY = False

# physical constants
p = 1000 # water density kg/m^3
g = 9.81 # m/s^2 gravitational acceleration 

'''
for each csv file we also need the H, also called head (salto in italian) and the Q, also called flow 
(portata in italian) to be able to calculate the power output of the turbine.
So other than the path we do neew more informations for each csv file.
We can make a dictionary with the csv file name as key and a tuple containing 
the path, the head and the flow as value.
'''

# csv data dictionary with the path, head and flow for each csv file
CSV_DATA = {
    "DBCAN" : {
        "name" : "Canaletta",
        "path" : "csv\\DBCAN.csv",
        "path_filtered" : "csv_filtered_H_fixed\\DBCAN_filtered_H_fixed.csv",
        "head" : 117, # in meters
        "flow" : [], # in m^3/s 
        "yield" : [] # in percentage
    },
    "DBPAR" : {
        "name" : "Partitore",
        "path" : "csv\\DBPAR.csv",
        "path_filtered" : "csv_filtered_H_fixed\\DBPAR_filtered_H_fixed.csv",
        "head" :346.24, # in meters
        "flow" : [], # in m^3/s
        "yield" : [] # in percentage
    },
    # "DBPGNEW" : {
    #     "name" :  "Ponte Giurino",
    #     "path" : "csv\\DBPGNEW.csv",
    #     "head" : 351, # in meters
    #     "flow" : [], # in m^3/s
    #     "yield" : [] # in percentage
    # },
    "DBST" : {
        "name" : "San Teodoro",
        "path" : "csv\\DBST.csv",
        "path_filtered" : "csv_filtered_H_fixed\\DBST_filtered_H_fixed.csv",
        "head" : 347.24, # in meters
        "flow" : [], # in m^3/s
        "yield" : [] # in percentage
    }
}


'''
per ogni csv eseguo le seguenti operazioni:
1- ordino i dati in base alla portata (flow) in modo crescente
2- per ogni riga  calcolo il rendimento per quella la portata di quella riga come 
[potenza_elettrica / (p * g * H * Q)]. 
3- salvo come dati: timestamp, portata, potenza elettrica, potenza idraulica e rendimento in un nuovo 
file csv.
4- usando i nuovi dati raccolti, creo un quinto file csv che mostra la media dei 
rendimenti per ogni portata in modo da avere un'idea generale dell'andamento 
del rendimento in funzione della portata. In questo modo dovremmo essere in grado 
di stimare il rendimento medio della turbina pelton in funzione della portata. 
5- usando una libreria come plotly creo un grafico 3D con la portata 
in ascissa e il rendimento in ordinata per ogni csv file, in modo da poter visualizzare
l'andamento del rendimento in funzione della portata per ogni csv file.

'''


os.makedirs("csv_filtered_H_fixed", exist_ok=True)
os.makedirs("csv_filtered_H_calculated", exist_ok=True)
CHARTS_DIR = os.path.join("..", "portale_hydro_3_0", "portale", "static", "portale", "pelton_yield_charts")
os.makedirs(CHARTS_DIR, exist_ok=True)

cols = ["timestamp", "Portata [l/s]", "Potenza [kW]", "Pressione [bar]"]
required_cols = ["Portata [l/s]", "Potenza [kW]"]

impianti = list(CSV_DATA.keys())
total_impianti = len(impianti)

for idx, impianto in enumerate(impianti, start=1):
    percent = int((idx / total_impianti) * 100)
    # read the csv file
    df = pandas.read_csv(CSV_DATA[impianto]["path"])
    # normalize column names
    df.columns = df.columns.str.strip()
    # skip files missing required columns
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        print(f"[1/3] {impianto}: missing columns {missing} in {CSV_DATA[impianto]['path']}, skipping.")
        continue
    # ensure numeric columns are parsed correctly
    df["Portata [l/s]"] = pandas.to_numeric(df["Portata [l/s]"], errors="coerce")
    df["Portata [l/s]"] = df["Portata [l/s]"].round(2)
    df["Potenza [kW]"] = pandas.to_numeric(df["Potenza [kW]"], errors="coerce")
    df["Pressione [bar]"] = pandas.to_numeric(df["Pressione [bar]"], errors="coerce")
    df["Potenza [kW]"] = df["Potenza [kW]"].round(5)
    df["Pressione [bar]"] = df["Pressione [bar]"].round(5)
    # sort the data by flow in ascending order
    df = df.sort_values(by="Portata [l/s]", ascending=True)
    # drop rows with missing values in any of the output columns
    df = df.dropna(subset=cols)
    # keep only the rows with flow greater than 0 and power greater than 0
    df = df[(df["Portata [l/s]"] > 0) & (df["Potenza [kW]"] > 0)]
    # estimated head from pressure for each row
    df["H_stimato"] = (df["Pressione [bar]"] * 100000) / (p * g)
    df["H_stimato"] = df["H_stimato"].round(5)
    if len(df) >= 3:
        window_size = min(50, max(3, len(df) // 2))
        results_h = hampel.hampel(df["H_stimato"], window_size=window_size, n_sigma=3.0)
        is_outlier_h = [False] * len(df)
        for idx in results_h.outlier_indices:
            if 0 <= idx < len(df):
                is_outlier_h[idx] = True
        df["H_stimato_is_outlier"] = is_outlier_h
    else:
        df["H_stimato_is_outlier"] = False

    # calculate the yield for each row and save it in a new column --> efficienza = [potenza_elettrica / (p * g * H * Q)]
    H = CSV_DATA[impianto]["head"]
    if H is None or H <= 0:
        raise ValueError(f"Invalid head for {impianto}: {H}")
    df["Q_[m3/s]"] = df["Portata [l/s]"] / 1000 # convert flow from l/s to m^3/s
    df["Q_[m3/s]"] = df["Q_[m3/s]"].round(5)
    df["potenza_idraulica"] = p * g * H * df["Q_[m3/s]"]
    df["potenza_idraulica"] = df["potenza_idraulica"].round(5)
    df["Rendimento"] = (df["Potenza [kW]"]*1000) / df["potenza_idraulica"]
    df["Rendimento"] = df["Rendimento"].round(5)
    # expected electrical power (kW): eta * p * g * Q * H
    df["Potenza_attesa [kW]"] = (df["Rendimento"] * p * g * H * df["Q_[m3/s]"]) / 1000
    df["Potenza_attesa [kW]"] = df["Potenza_attesa [kW]"].round(5)
    # hampel filter to flag outliers in expected power
    if len(df) >= 3:
        window_size = min(50, max(3, len(df) // 2))
        results_pow = hampel.hampel(df["Potenza_attesa [kW]"], window_size=window_size, n_sigma=3.0)
        df["Potenza_attesa_filtered [kW]"] = pandas.Series(results_pow.filtered_data).round(5)
        is_outlier_pow = [False] * len(df)
        for idx in results_pow.outlier_indices:
            if 0 <= idx < len(df):
                is_outlier_pow[idx] = True
        df["Potenza_attesa_is_outlier"] = is_outlier_pow
    else:
        df["Potenza_attesa_filtered [kW]"] = df["Potenza_attesa [kW]"]
        df["Potenza_attesa_is_outlier"] = False

    # hampel filter to flag outliers in measured power
    if len(df) >= 3:
        window_size = min(50, max(3, len(df) // 2))
        results_pow_meas = hampel.hampel(df["Potenza [kW]"], window_size=window_size, n_sigma=3.0)
        is_outlier_pow_meas = [False] * len(df)
        for idx in results_pow_meas.outlier_indices:
            if 0 <= idx < len(df):
                is_outlier_pow_meas[idx] = True
        df["Potenza_is_outlier"] = is_outlier_pow_meas
    else:
        df["Potenza_is_outlier"] = False
    # hampel filter to flag outliers in rendimento
    if len(df) >= 3:
        window_size = min(50, max(3, len(df) // 2))
        results = hampel.hampel(df["Rendimento"], window_size=window_size, n_sigma=3.0)
        df["Rendimento_filtered"] = pandas.Series(results.filtered_data).round(5)
        is_outlier = [False] * len(df)
        for idx in results.outlier_indices:
            if 0 <= idx < len(df):
                is_outlier[idx] = True
        df["Rendimento_is_outlier"] = is_outlier
    else:
        df["Rendimento_filtered"] = df["Rendimento"]
        df["Rendimento_is_outlier"] = False

    # build a second dataset using H_mean (mean of non-outlier H_stimato)
    if "H_stimato_is_outlier" in df.columns:
        h_stimato_in = df[df["H_stimato_is_outlier"] == False]["H_stimato"]
        H_mean = h_stimato_in.mean() if not h_stimato_in.empty else H
    else:
        H_mean = H

    df_hmean = df.copy()
    df_hmean["H_medio_usato"] = round(H_mean, 5)
    df_hmean["potenza_idraulica"] = (p * g * H_mean * df_hmean["Q_[m3/s]"]).round(5)
    df_hmean["Rendimento"] = ((df_hmean["Potenza [kW]"] * 1000) / df_hmean["potenza_idraulica"]).round(5)

    if len(df_hmean) >= 3:
        window_size = min(50, max(3, len(df_hmean) // 2))
        results = hampel.hampel(df_hmean["Rendimento"], window_size=window_size, n_sigma=3.0)
        df_hmean["Rendimento_filtered"] = pandas.Series(results.filtered_data).round(5)
        is_outlier = [False] * len(df_hmean)
        for idx in results.outlier_indices:
            if 0 <= idx < len(df_hmean):
                is_outlier[idx] = True
        df_hmean["Rendimento_is_outlier"] = is_outlier
    else:
        df_hmean["Rendimento_filtered"] = df_hmean["Rendimento"]
        df_hmean["Rendimento_is_outlier"] = False

    df_hmean["Potenza_attesa [kW]"] = (df_hmean["Rendimento"] * p * g * H_mean * df_hmean["Q_[m3/s]"]) / 1000
    df_hmean["Potenza_attesa [kW]"] = df_hmean["Potenza_attesa [kW]"].round(5)

    if len(df_hmean) >= 3:
        window_size = min(50, max(3, len(df_hmean) // 2))
        results_pow = hampel.hampel(df_hmean["Potenza_attesa [kW]"], window_size=window_size, n_sigma=3.0)
        df_hmean["Potenza_attesa_filtered [kW]"] = pandas.Series(results_pow.filtered_data).round(5)
        is_outlier_pow = [False] * len(df_hmean)
        for idx in results_pow.outlier_indices:
            if 0 <= idx < len(df_hmean):
                is_outlier_pow[idx] = True
        df_hmean["Potenza_attesa_is_outlier"] = is_outlier_pow
    else:
        df_hmean["Potenza_attesa_filtered [kW]"] = df_hmean["Potenza_attesa [kW]"]
        df_hmean["Potenza_attesa_is_outlier"] = False
    # save the filtered data in a new csv file
    df.to_csv(
        CSV_DATA[impianto]["path_filtered"], 
        index=False, 
        columns=cols
        + [
            "Q_[m3/s]",
            "potenza_idraulica",
            "Rendimento",
            "Rendimento_filtered",
            "Rendimento_is_outlier",
            "Potenza [kW]",
            "Potenza_is_outlier",
            "Potenza_attesa [kW]",
            "Potenza_attesa_filtered [kW]",
            "Potenza_attesa_is_outlier",
            "H_stimato",
            "H_stimato_is_outlier",
        ]
        )
    print(f"[1/3] {impianto}: filtered CSV saved to {CSV_DATA[impianto]['path_filtered']}")

    hmean_path = f"csv_filtered_H_calculated\\{impianto}_filtered_H_calculated.csv"
    df_hmean.to_csv(
        hmean_path,
        index=False,
        columns=cols
        + [
            "Q_[m3/s]",
            "potenza_idraulica",
            "Rendimento",
            "Rendimento_filtered",
            "Rendimento_is_outlier",
            "Potenza [kW]",
            "Potenza_is_outlier",
            "Potenza_attesa [kW]",
            "Potenza_attesa_filtered [kW]",
            "Potenza_attesa_is_outlier",
            "H_stimato",
            "H_stimato_is_outlier",
            "H_medio_usato",
        ],
    )
    print(f"[1/3] {impianto}: H_mean CSV saved to {hmean_path}")


def _load_plot_data_from_path(data_path):
    df_plot = pandas.read_csv(data_path)
    # ensure numeric types for plotting
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
        # detect outliers for measured power (on the fly)
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

        # expected power outliers: use precomputed if available, otherwise compute
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
    fig.update_xaxes(title_text="Portata [l/s]", row=row, col=col)
    fig.update_yaxes(title_text="Rendimento (%)", row=row, col=col, secondary_y=False)
    fig.update_yaxes(title_text="Potenza [kW]", row=row, col=col, secondary_y=True)
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



MAX_POINTS_PER_GROUP = 10000
print("[2/3] Starting Plotly 2x3 grid and saving chart...")
fixed_paths = {
    "DBCAN": CSV_DATA["DBCAN"]["path_filtered"],
    "DBPAR": CSV_DATA["DBPAR"]["path_filtered"],
    "DBST": CSV_DATA["DBST"]["path_filtered"],
}
calc_paths = {
    "DBCAN": "csv_filtered_H_calculated\\DBCAN_filtered_H_calculated.csv",
    "DBPAR": "csv_filtered_H_calculated\\DBPAR_filtered_H_calculated.csv",
    "DBST": "csv_filtered_H_calculated\\DBST_filtered_H_calculated.csv",
}

fig = make_subplots(
    rows=2,
    cols=3,
    specs=[
        [{"secondary_y": True}, {"secondary_y": True}, {"secondary_y": True}],
        [{"secondary_y": True}, {"secondary_y": True}, {"secondary_y": True}],
    ],
    horizontal_spacing=0.06,
    vertical_spacing=0.12,
)
plot_rendimento_potenza_dual_axis(
    fig, 1, 1, fixed_paths["DBCAN"], "Canaletta (H_fixed)", "Canaletta (H_fixed)", max_points=MAX_POINTS_PER_GROUP
)
plot_rendimento_potenza_dual_axis(
    fig, 1, 2, fixed_paths["DBPAR"], "Partitore (H_fixed)", "Partitore (H_fixed)", max_points=MAX_POINTS_PER_GROUP
)
plot_rendimento_potenza_dual_axis(
    fig, 1, 3, fixed_paths["DBST"], "San Teodoro (H_fixed)", "San Teodoro (H_fixed)", max_points=MAX_POINTS_PER_GROUP
)

plot_rendimento_potenza_dual_axis(
    fig, 2, 1, calc_paths["DBCAN"], "Canaletta (H_calculated)", "Canaletta (H_calculated)", max_points=MAX_POINTS_PER_GROUP
)
plot_rendimento_potenza_dual_axis(
    fig, 2, 2, calc_paths["DBPAR"], "Partitore (H_calculated)", "Partitore (H_calculated)", max_points=MAX_POINTS_PER_GROUP
)
plot_rendimento_potenza_dual_axis(
    fig, 2, 3, calc_paths["DBST"], "San Teodoro (H_calculated)", "San Teodoro (H_calculated)", max_points=MAX_POINTS_PER_GROUP
)

fig.update_layout(
    height=900,
    width=1600,
    title_text="Rendimento e Potenza vs Portata (H fixed vs H calculated)",
    showlegend=True,
)
fig.write_html(os.path.join(CHARTS_DIR, "pelton_yield_curve.html"))
fig.show()


# estimated head based on non-outlier H_stimato values
for impianto in impianti:
    df = pandas.read_csv(CSV_DATA[impianto]["path_filtered"])
    if "H_stimato" in df.columns:
        if "H_stimato_is_outlier" in df.columns:
            df = df[df["H_stimato_is_outlier"] == False]
        if not df.empty:
            head_mean = df["H_stimato"].mean()
            print(f"[3/3] Estimated Head for {impianto} based on average pressure: {head_mean:.2f} m")


'''
potrei creare un altro file csv contenente i vari valori di portata e rendimento 
per ogni csv file. In questo modo potrei avere un'idea generale dell'andamento 
del rendimento in funzione della portata per ogni csv file. 
Potrei quindi calcolare una media del rendimento dei tre csv file per ogni portata e creare un grafico che mostra 
l'andamento del rendimento medio in funzione della portata per una turbina pelton. 
Usando questo rendimento medio potrei stimare la potenza elettrica attesa per ogni portata usando la 
formula: potenza_elettrica_attesa = rendimento_medio * p * g * H * Q.

Quindi per trebissacce il salto al momento è di ~183m
I dati di portata c'è li abbiamo 
p e q sono dati fisici costanti
il rendimento/portata lo possiamo stimare con i dati che abbiamo raccolto 
dagli altri csv file, facendo una media del rendimento per ogni portata.

Per il momento potrei costruire il file csv e provare a plottare
il grafico del rendimento medio in funzione della portata, per vedere 
se è coerente con quello che ci aspettiamo da una turbina pelton.

'''

# Build a mean efficiency curve vs flow (using H_fixed data) and estimate expected power for Trebisacce.
TREBISACCE_HEAD = 183  # meters
FLOW_BIN_LS = 0.10     # bin size in l/s

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
        grouped["Rendimento_is_outlier"] = is_outlier
        grouped = grouped[grouped["Rendimento_is_outlier"] == False].copy()
        grouped = grouped.drop(columns=["Rendimento_is_outlier"])
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

mean_curve = _build_mean_efficiency_curve(
    [CSV_DATA["DBCAN"]["path_filtered"], CSV_DATA["DBPAR"]["path_filtered"], CSV_DATA["DBST"]["path_filtered"]]
)
if not mean_curve.empty:
    mean_curve["Q_[m3/s]"] = (mean_curve["Portata_bin"] / 1000).round(5)
    mean_curve["Potenza_attesa_trebisacce [kW]"] = (
        mean_curve["Rendimento_mean"] * p * g * TREBISACCE_HEAD * mean_curve["Q_[m3/s]"]
    ) / 1000
    mean_curve["Potenza_attesa_trebisacce [kW]"] = mean_curve["Potenza_attesa_trebisacce [kW]"].round(5)
    mean_curve["Portata_bin"] = mean_curve["Portata_bin"].round(5)
    mean_curve["Rendimento_mean"] = mean_curve["Rendimento_mean"].round(5)

    # add per-plant mean efficiency columns to the mean curve CSV
    curve_can = _build_single_efficiency_curve(CSV_DATA["DBCAN"]["path_filtered"]).rename(
        columns={"Rendimento_mean": "rendimento_CAN"}
    )
    curve_par = _build_single_efficiency_curve(CSV_DATA["DBPAR"]["path_filtered"]).rename(
        columns={"Rendimento_mean": "rendimento_PAR"}
    )
    curve_st = _build_single_efficiency_curve(CSV_DATA["DBST"]["path_filtered"]).rename(
        columns={"Rendimento_mean": "rendimento_ST"}
    )

    mean_curve = mean_curve.merge(curve_can, on="Portata_bin", how="left")
    mean_curve = mean_curve.merge(curve_par, on="Portata_bin", how="left")
    mean_curve = mean_curve.merge(curve_st, on="Portata_bin", how="left")

    CSV_CURVE_DIR = os.path.join("csv_pelton_yield_curve")
    os.makedirs(CSV_CURVE_DIR, exist_ok=True)
    mean_curve_path = os.path.join(CSV_CURVE_DIR, "rendimento_medio_per_turbine_pelton.csv")
    mean_curve.to_csv(mean_curve_path, index=False)
    print(f"[3/3] Mean efficiency curve saved to {mean_curve_path}")

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
        title_text="Rendimento medio vs Portata (media impianti H_fixed)",
        height=520,
        width=900,
    )
    fig_mean.update_xaxes(title_text="Portata [l/s]")
    fig_mean.update_yaxes(title_text="Rendimento (%)", range=[0, 100])
    fig_mean.write_html(os.path.join(CHARTS_DIR, "rendimento_medio_portata_trebisacce.html"))

    # Plot all four yield curves (three plants + mean)
    def _build_single_efficiency_curve(path):
        df_src = pandas.read_csv(path)
        for col in ["Portata [l/s]", "Rendimento", "Rendimento_is_outlier"]:
            if col in df_src.columns:
                df_src[col] = pandas.to_numeric(df_src[col], errors="coerce")
        if "Rendimento_is_outlier" in df_src.columns:
            df_src = df_src[df_src["Rendimento_is_outlier"] == False]
        df_src = df_src.dropna(subset=["Portata [l/s]", "Rendimento"])
        if df_src.empty:
            return pandas.DataFrame(columns=["Portata_bin", "Rendimento_median"])
        df_src["Portata_bin"] = (df_src["Portata [l/s]"] / FLOW_BIN_LS).round(0) * FLOW_BIN_LS
        df_src = df_src[df_src["Portata_bin"] > 0]
        grouped = df_src.groupby("Portata_bin", as_index=False)["Rendimento"].mean()
        grouped = grouped.sort_values(by="Portata_bin")
        grouped["Rendimento"] = grouped["Rendimento"].round(5)
        return grouped.rename(columns={"Rendimento": "Rendimento_mean"})

    fig_all = make_subplots(rows=1, cols=1)
    if not curve_can.empty:
        low_can = curve_can[curve_can["Portata_bin"] < 7]
        mid_can = curve_can[(curve_can["Portata_bin"] >= 7) & (curve_can["Portata_bin"] <= 100)]
        high_can = curve_can[curve_can["Portata_bin"] > 100]
        if not low_can.empty:
            fig_all.add_trace(
                go.Scatter(
                    x=low_can["Portata_bin"],
                    y=low_can["rendimento_CAN"] * 100,
                    mode="lines",
                    line={"width": 2, "color": "#93c5fd"},
                    name="Canaletta",
                    showlegend=True,
                )
            )
        if not mid_can.empty:
            fig_all.add_trace(
                go.Scatter(
                    x=mid_can["Portata_bin"],
                    y=mid_can["rendimento_CAN"] * 100,
                    mode="lines",
                    line={"width": 2, "color": "#1f77b4"},
                    name="Canaletta",
                    showlegend=False,
                )
            )
        if not high_can.empty:
            fig_all.add_trace(
                go.Scatter(
                    x=high_can["Portata_bin"],
                    y=high_can["rendimento_CAN"] * 100,
                    mode="lines",
                    line={"width": 2, "color": "#93c5fd"},
                    name="Canaletta",
                    showlegend=False,
                )
            )
    if not curve_par.empty:
        low_par = curve_par[curve_par["Portata_bin"] < 7]
        mid_par = curve_par[(curve_par["Portata_bin"] >= 7) & (curve_par["Portata_bin"] <= 100)]
        high_par = curve_par[curve_par["Portata_bin"] > 100]
        if not low_par.empty:
            fig_all.add_trace(
                go.Scatter(
                    x=low_par["Portata_bin"],
                    y=low_par["rendimento_PAR"] * 100,
                    mode="lines",
                    line={"width": 2, "color": "#fdba74"},
                    name="Partitore",
                    showlegend=True,
                )
            )
        if not mid_par.empty:
            fig_all.add_trace(
                go.Scatter(
                    x=mid_par["Portata_bin"],
                    y=mid_par["rendimento_PAR"] * 100,
                    mode="lines",
                    line={"width": 2, "color": "#ff7f0e"},
                    name="Partitore",
                    showlegend=False,
                )
            )
        if not high_par.empty:
            fig_all.add_trace(
                go.Scatter(
                    x=high_par["Portata_bin"],
                    y=high_par["rendimento_PAR"] * 100,
                    mode="lines",
                    line={"width": 2, "color": "#fdba74"},
                    name="Partitore",
                    showlegend=False,
                )
            )
    if not curve_st.empty:
        low_st = curve_st[curve_st["Portata_bin"] < 7]
        mid_st = curve_st[(curve_st["Portata_bin"] >= 7) & (curve_st["Portata_bin"] <= 100)]
        high_st = curve_st[curve_st["Portata_bin"] > 100]
        if not low_st.empty:
            fig_all.add_trace(
                go.Scatter(
                    x=low_st["Portata_bin"],
                    y=low_st["rendimento_ST"] * 100,
                    mode="lines",
                    line={"width": 2, "color": "#86efac"},
                    name="San Teodoro",
                    showlegend=True,
                )
            )
        if not mid_st.empty:
            fig_all.add_trace(
                go.Scatter(
                    x=mid_st["Portata_bin"],
                    y=mid_st["rendimento_ST"] * 100,
                    mode="lines",
                    line={"width": 2, "color": "#2ca02c"},
                    name="San Teodoro",
                    showlegend=False,
                )
            )
        if not high_st.empty:
            fig_all.add_trace(
                go.Scatter(
                    x=high_st["Portata_bin"],
                    y=high_st["rendimento_ST"] * 100,
                    mode="lines",
                    line={"width": 2, "color": "#86efac"},
                    name="San Teodoro",
                    showlegend=False,
                )
            )

    low_mean = mean_curve[mean_curve["Portata_bin"] < 7]
    mid_mean = mean_curve[(mean_curve["Portata_bin"] >= 7) & (mean_curve["Portata_bin"] <= 100)]
    high_mean = mean_curve[mean_curve["Portata_bin"] > 100]
    if not low_mean.empty:
        fig_all.add_trace(
            go.Scatter(
                x=low_mean["Portata_bin"],
                y=low_mean["Rendimento_mean"] * 100,
                mode="lines",
                line={"width": 3, "color": "#fecaca"},
                name="Media",
                showlegend=True,
            )
        )
    if not mid_mean.empty:
        fig_all.add_trace(
            go.Scatter(
                x=mid_mean["Portata_bin"],
                y=mid_mean["Rendimento_mean"] * 100,
                mode="lines",
                line={"width": 3, "color": "#d62728"},
                name="Media",
                showlegend=False,
            )
        )
    if not high_mean.empty:
        fig_all.add_trace(
            go.Scatter(
                x=high_mean["Portata_bin"],
                y=high_mean["Rendimento_mean"] * 100,
                mode="lines",
                line={"width": 3, "color": "#fecaca"},
                name="Media",
                showlegend=False,
            )
        )

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
    fig_all.write_html(os.path.join(CHARTS_DIR, "rendimento_curve_quattro.html"))
