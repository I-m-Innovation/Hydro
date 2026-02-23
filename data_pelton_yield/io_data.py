import pandas
import hampel as hampel

from constants import p, g, cols, required_cols


def _hampel_flags(series):
    # if the series is too short, return all False (no outliers)
    if len(series) < 3:
        return [False] * len(series)
    window_size = min(50, max(3, len(series) // 2))
    results = hampel.hampel(series, window_size=window_size, n_sigma=3.0)
    flags = [False] * len(series)
    for idx in results.outlier_indices:
        if 0 <= idx < len(series):
            flags[idx] = True
    return flags


def load_and_prepare(path):
    df = pandas.read_csv(path)
    df.columns = df.columns.str.strip()  # remove leading/trailing whitespace from column names

    # check for required columns and raise error if missing
    missing = []
    for col in required_cols:
        if col not in df.columns:
            missing.append(col)
    if missing:
        raise ValueError(f"Missing columns {missing} in {path}")

    # convert to numeric, coerce errors to NaN, round values, and filter out invalid rows
    df["Portata [l/s]"] = pandas.to_numeric(df["Portata [l/s]"], errors="coerce")
    df["Potenza [kW]"] = pandas.to_numeric(df["Potenza [kW]"], errors="coerce")
    df["Pressione [bar]"] = pandas.to_numeric(df["Pressione [bar]"], errors="coerce")
    
    df["Portata [l/s]"] = df["Portata [l/s]"].round(2)
    df["Potenza [kW]"] = df["Potenza [kW]"].round(5)
    df["Pressione [bar]"] = df["Pressione [bar]"].round(5)

    df = df.sort_values(by="Portata [l/s]", ascending=True)
    df = df.dropna(subset=cols)
    df = df[(df["Portata [l/s]"] > 0) & (df["Potenza [kW]"] > 0)] # delete rows with non-positive flow or power

    # ensure Portata [l/s] and Q_[m3/s] are present and consistent
    df["Portata [l/s]"] = df["Portata [l/s]"].round(2)
    df["Q_[m3/s]"] = (df["Portata [l/s]"] / 1000).round(5)
    df = df[df["Q_[m3/s]"] > 0]

    # estimated head from pressure for each row
    df["H_stimato"] = (df["Pressione [bar]"] * 100000) / (p * g) # convert bar to Pa, then divide by (density * gravity) to get head in meters
    df["H_stimato"] = df["H_stimato"].round(5)
    df["H_stimato_is_outlier"] = _hampel_flags(df["H_stimato"])

    # outliers in measured power
    df["Potenza_is_outlier"] = _hampel_flags(df["Potenza [kW]"])

    return df
