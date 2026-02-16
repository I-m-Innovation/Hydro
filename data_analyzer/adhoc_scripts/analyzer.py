from pathlib import Path

import pandas as pd
import hampel as hampel


def main(path_csv="", output_dir=""):
    # Load data from CSV file
    print("Loading data from CSV file...")
    df = pd.read_csv(path_csv)
    print("Data loaded successfully.")

    # Sort by timestamp before applying Hampel (step-by-step)
    df["t"] = pd.to_datetime(df["t"], errors="coerce")
    df = df.dropna(subset=["t"]) # Remove rows with invalid timestamps
    df = df.drop_duplicates(subset=["t"], keep="first") # Remove duplicate timestamp     
    df = df.sort_values("t") # Sort by timestamp
    df = df.reset_index(drop=True) # Reset index after sorting

    # Extract the relevant column as a pandas Series
    col_ls_series = df["flow_ls"]  #Series pandas. Ottima se continui a usare funzioni pandas (filtri, aggregazioni, plotting).
    print("Calling Hampel filter...")
    results = hampel.hampel(col_ls_series, window_size=50, n_sigma=3.0)
    print(results.filtered_data)
    
    print("Processing results...")
    filtered_series = pd.Series(results.filtered_data)
    outlier_indices = results.outlier_indices
    medians_windows_series = pd.Series(results.medians)
    median_absolute_deviations_series = pd.Series(results.median_absolute_deviations)
    thresholds = pd.Series(results.thresholds)
    
    #creting a new empty array with same length as df and filling it with False
    is_outlier = [False] * len(df)
    for index in outlier_indices:
        is_outlier[index] = True
    
    # creating new csv with results
    print("Creating output CSV file...")
    output_dir_path = Path(output_dir) if output_dir else None
    if output_dir_path:
        output_dir_path.mkdir(parents=True, exist_ok=True)

    output_df = pd.DataFrame({
        "timestamp": df["t"],
        "flow_ls_raw": df["flow_ls"],
        "flow_ls_smoothed": filtered_series,
        "is_outlier": is_outlier,
        "window_median": medians_windows_series,
        "thresholds": thresholds
    })
    if output_dir_path:
        output_path = output_dir_path / (Path(path_csv).stem + "_processed.csv")
    else:
        output_path = Path(path_csv + "_processed.csv")
    output_df.to_csv(output_path, index=False)
    print(f"Output CSV file created at: {output_path}")


if __name__ == "__main__":
    #takes the paths of csv_hampel directory
    paths_csv = [
        "./csv_hampel/out_01. Trebisacce_Hampel.csv",
        "./csv_hampel/out_02. Merone Camera di manovra_Hampel.csv",
        "./csv_hampel/out_03. Merone II salto_Hampel.csv",
        "./csv_hampel/out_04. Merone III salto_Hampel.csv",
        "./csv_hampel/out_05. CU4_Hampel.csv",
        "./csv_hampel/out_06. SA3_Hampel.csv",
        "./csv_hampel/out_07. SA6_Hampel.csv",
        "./csv_hampel/out_10. Sessa Auronca_Hampel.csv",
    ]
    output_dir = "./data_hampel_cleaned"
    for path in paths_csv:
        print(f"Processing file: {path}")
        main(path, output_dir=output_dir)
        print(f"Finished processing file: {path}\n")
        
    print("All files processed.")


FILE_MAP = {
    "Gateway 1" : "./csv/out_01. Trebisacce.csv",
    "Sessa_Auronca" : "./csv/out_10. Sessa Auronca.csv",
    "Santissima" : "",
    "SA6":"./csv/out_07. SA6.csv",
    "SA3":"./csv/out_06. SA3.csv",
    "Merone III salto":"./csv/out_04. Merone III salto.csv",
    "Merone II salto":"./csv/out_03. Merone II salto.csv",
    "Merone Camera di Manovra":"./csv/out_02. Merone Camera di manovra.csv",
    "Fiumefreddi":"",
    "CU4":"./csv/out_05. CU4.csv", 
}