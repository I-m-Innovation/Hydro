from pathlib import Path
from datetime import datetime
from time import perf_counter

import pandas as pd
from hampel import hampel
import pytz

# Mappatura hardcoded: id_misuratore -> path CSV raw
FILE_MAP = {
    "Gateway 1": "./data_analyzer/csv/out_01. Trebisacce.csv",
    "Sessa_Auronca": "./data_analyzer/csv/out_10. Sessa Auronca.csv",
    "Santissima": "",
    "SA6": "./data_analyzer/csv/out_07. SA6.csv",
    "SA3": "./data_analyzer/csv/out_06. SA3.csv",
    "Merone III salto": "./data_analyzer/csv/out_04. Merone III salto.csv",
    "Merone II salto": "./data_analyzer/csv/out_03. Merone II salto.csv",
    "Merone Camera di Manovra": "./data_analyzer/csv/out_02. Merone Camera di manovra.csv",
    "Fiumefreddi": "",
    "CU4": "./data_analyzer/csv/out_05. CU4.csv",
}

# Parametri Hampel
HAMPEL_WINDOW_SIZE = 50
HAMPEL_SIGMA_THRESHOLD = 3.0

# Output
OUT_DIR = Path("./csv_hampel")
OUT_DIR.mkdir(parents=True, exist_ok=True)

ROME_TZ = pytz.timezone("Europe/Rome")


def process_file(id_misuratore: str, path_csv: str):
    if not path_csv:
        print(f"[skip] {id_misuratore}: path vuoto")
        return
    path = Path(path_csv)
    if not path.exists():
        print(f"[skip] {id_misuratore}: file non trovato -> {path}")
        return

    print(f"[start] {id_misuratore} -> {path}")

    t_start = perf_counter()
    df = pd.read_csv(path)
    if "t" not in df.columns or "flow_ls" not in df.columns:
        print(f"[skip] {id_misuratore}: colonne mancanti (t, flow_ls)")
        return

    # Rimuovi righe duplicate con stesso timestamp e stesso valore
    before = len(df)
    df = df.drop_duplicates(subset=["t", "flow_ls"], keep="first")
    dropped = before - len(df)
    if dropped:
        print(f"[dedupe] {id_misuratore}: removed {dropped} duplicate rows")

    # Parse timestamp e normalizza
    df["data_misurazione"] = pd.to_datetime(df["t"], errors="coerce")
    df = df.dropna(subset=["data_misurazione"])
    df = df.drop_duplicates(subset=["data_misurazione"], keep="first")
    df = df.sort_values("data_misurazione").reset_index(drop=True)

    # Keep naive timestamps as-is (no timezone localization)


    series = df["flow_ls"].astype(float)

    result = hampel(series, window_size=HAMPEL_WINDOW_SIZE, n_sigma=HAMPEL_SIGMA_THRESHOLD)

    filtered = result.filtered_data
    outlier_indices = set(result.outlier_indices)
    medians = result.medians
    thresholds = result.thresholds

    is_outlier = [i in outlier_indices for i in range(len(df))]

    # updated_at = now (Europe/Rome)
    now_ts = datetime.now(ROME_TZ)

    out_df = pd.DataFrame({
        "id_misuratore": id_misuratore,
        "data_misurazione": df["data_misurazione"],
        "flow_ls_raw": df["flow_ls"].astype(float),
        "flow_ls_smoothed": filtered,
        "is_outlier": is_outlier,
        "window_median": medians,
        "thresholds": thresholds,
        "updated_at": now_ts,
    })

    out_path = OUT_DIR / f"{id_misuratore}_hampel.csv"
    out_df.to_csv(out_path, index=False)
    elapsed = perf_counter() - t_start
    print(f"[done] {id_misuratore} -> {out_path} ({elapsed:.1f}s)")


if __name__ == "__main__":
    total = len(FILE_MAP)
    start_all = perf_counter()
    for i, (misuratore, path_csv) in enumerate(FILE_MAP.items(), start=1):
        percent = (i / total) * 100
        print(f"[progress] {i}/{total} ({percent:.0f}%)")
        process_file(misuratore, path_csv)
    total_elapsed = perf_counter() - start_all
    print(f"[complete] processed {total} files in {total_elapsed:.1f}s")
