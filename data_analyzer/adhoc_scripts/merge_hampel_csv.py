from pathlib import Path
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR / "csv_hampel"
OUT_FILE = BASE_DIR / "measurements_clean_full.csv"
OUT_FILE_DEDUP = BASE_DIR / "measurements_clean_full_dedup.csv"


def main():
    files = sorted(SRC_DIR.glob("*.csv"))
    if not files:
        print(f"[merge] no csv files found in {SRC_DIR}")
        return

    dfs = []
    for f in files:
        df = pd.read_csv(f)
        dfs.append(df)

    merged = pd.concat(dfs, ignore_index=True)
    # Ensure correct ordering
    merged["data_misurazione"] = pd.to_datetime(merged["data_misurazione"], errors="coerce")
    merged = merged.dropna(subset=["data_misurazione"])
    merged = merged.sort_values(["id_misuratore", "data_misurazione"])

    merged.to_csv(OUT_FILE, index=False)
    print(f"[merge] wrote {len(merged)} rows to {OUT_FILE}")

    # Deduplicate by primary key (id_misuratore, data_misurazione)
    dedup = merged.drop_duplicates(subset=["id_misuratore", "data_misurazione"], keep="first")
    dedup.to_csv(OUT_FILE_DEDUP, index=False)
    print(f"[dedup] wrote {len(dedup)} rows to {OUT_FILE_DEDUP}")


if __name__ == "__main__":
    main()
