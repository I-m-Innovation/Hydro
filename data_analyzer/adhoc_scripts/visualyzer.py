import pandas as pd
import matplotlib.pyplot as plt


csv_path = "./data_hampel_cleaned/out_03. Merone II salto_Hampel_processed.csv"

def plot_data():
    # Load data from CSV file
    print("Loading data from CSV file for visualization...")
    df = pd.read_csv("./csv_test.csv", usecols=["timestamp", "flow_ls_raw", "flow_ls_smoothed", "is_outlier"],
    )
    print("Data loaded successfully.")
    df["flow_ls_raw"] = df["flow_ls_raw"].astype("float32")
    df["flow_ls_smoothed"] = df["flow_ls_smoothed"].astype("float32")
    df["is_outlier"] = df["is_outlier"].astype("bool")
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"]).sort_values("timestamp")
    # df = df.tail(1000000)
    

    # Plot raw and smoothed data
    plt.figure(figsize=(12, 6))
    print("Plotting data raw...")
    plt.plot(
        df["timestamp"],
        df["flow_ls_raw"],
        label="Raw Data",
        color="gray",
        alpha=0.35,
        linewidth=0.8,
    )
    print("Plotting data smoothed...")
    plt.plot(
        df["timestamp"],
        df["flow_ls_smoothed"],
        label="Smoothed Data",
        color="blue",
        alpha=0.7,
        linewidth=1.0,
    )

    # Highlight outliers
    # print("Highlighting outliers...")
    # outliers = df[df["is_outlier"]]
    # plt.scatter(
    #     outliers["timestamp"],
    #     outliers["flow_ls_raw"],
    #     color="gray",
    #     label="Outliers",
    #     zorder=-999,
    #     s=6,
    # )

    plt.xlabel("Timestamp")
    plt.ylabel("Flow (ls)")
    plt.title("Flow Data with Hampel Filter Smoothing and Outliers")
    plt.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()



if __name__ == "__main__":
    plot_data()
