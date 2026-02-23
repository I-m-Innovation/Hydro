import os
import pandas

from CSV_datas import CSV_DATA, save_csv_data
from constants import CHARTS_DIR
from compute import compute_h_mean, build_h_calculated
from io_data import load_and_prepare
from plots import plot_h_calculated_grid
from curves import build_and_save_mean_curves


def main():
    os.makedirs("csv_all\\h_calculated", exist_ok=True)
    os.makedirs(CHARTS_DIR, exist_ok=True)

    calc_paths = {}
    for impianto, meta in CSV_DATA.items():
        df = load_and_prepare(meta["path"])     # load and prepare the original CSV data
        h_mean = compute_h_mean(df)             # compute the mean head for this plant based on the original data
        df_h = build_h_calculated(df, h_mean)

        hmean_path = f"csv_all\\h_calculated\\{impianto}_filtered_H_calculated.csv"
        df_h.to_csv(
            hmean_path,
            index=False,
            columns=[
                "timestamp",
                "Portata [l/s]",
                "Potenza [kW]",
                "Pressione [bar]",
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
        print(f"[1/3] {impianto}: H_calculated CSV saved to {hmean_path}")
        calc_paths[impianto] = hmean_path

    print("[2/3] Starting Plotly 1x3 grid (H_calculated only) and saving chart...")
    plot_h_calculated_grid(calc_paths, CHARTS_DIR, max_points=10000)

    for impianto in calc_paths:
        df = pandas.read_csv(calc_paths[impianto])
        if "H_stimato" in df.columns:
            if "H_stimato_is_outlier" in df.columns:
                df = df[df["H_stimato_is_outlier"] == False]
            if not df.empty:
                head_mean = df["H_stimato"].mean()
                CSV_DATA[impianto]["estimated_head"] = head_mean
                print(f"[3/3] Estimated Head for {impianto} based on average pressure: {head_mean:.2f} m")

    save_csv_data(CSV_DATA)
    build_and_save_mean_curves(calc_paths, CHARTS_DIR)


if __name__ == "__main__":
    main()
