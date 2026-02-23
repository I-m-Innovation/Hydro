import pandas
import hampel as hampel

from constants import p, g


def _hampel_filtered(series):
    if len(series) < 3:
        return series, [False] * len(series)
    window_size = min(50, max(3, len(series) // 2))
    results = hampel.hampel(series, window_size=window_size, n_sigma=3.0)
    filtered = pandas.Series(results.filtered_data)
    flags = [False] * len(series)
    for idx in results.outlier_indices:
        if 0 <= idx < len(series):
            flags[idx] = True
    return filtered, flags


def compute_h_mean(df):
    if "H_stimato_is_outlier" in df.columns:
        h_stimato_in = df[df["H_stimato_is_outlier"] == False]["H_stimato"]
        if not h_stimato_in.empty:
            return h_stimato_in.mean()
    return df["H_stimato"].mean()


def build_h_calculated(df, h_mean):
    df_h = df.copy()
    df_h["H_medio_usato"] = round(h_mean, 5)

    df_h["potenza_idraulica"] = (p * g * h_mean * df_h["Q_[m3/s]"]).round(5)
    df_h["Rendimento"] = ((df_h["Potenza [kW]"] * 1000) / df_h["potenza_idraulica"]).round(5)

    filtered_rend, flags_rend = _hampel_filtered(df_h["Rendimento"])
    df_h["Rendimento_filtered"] = filtered_rend.round(5)
    df_h["Rendimento_is_outlier"] = flags_rend

    df_h["Potenza_attesa [kW]"] = (
        df_h["Rendimento"] * p * g * h_mean * df_h["Q_[m3/s]"]
    ).div(1000).round(5)

    filtered_pow, flags_pow = _hampel_filtered(df_h["Potenza_attesa [kW]"])
    df_h["Potenza_attesa_filtered [kW]"] = filtered_pow.round(5)
    df_h["Potenza_attesa_is_outlier"] = flags_pow

    return df_h
