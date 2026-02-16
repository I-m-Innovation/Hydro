import pandas as pd

INPUT = r"C:\Users\Luca Parise\Desktop\sorgenti\Hydra_3_0\data_analyzer\csv_hampel\Gateway 1_hampel copy.csv"
OUTPUT = r"C:\Users\Luca Parise\Desktop\sorgenti\Hydra_3_0\data_analyzer\csv_hampel\Gateway 1_hampel copy_filtered.csv"
COL_TS = "data_misurazione"  # cambia se la tua colonna ha un altro nome

cutoff = pd.Timestamp("2023-12-04 00:00:30")

df = pd.read_csv(INPUT)
df[COL_TS] = pd.to_datetime(df[COL_TS], errors="coerce")
df = df[df[COL_TS] >= cutoff]

df.to_csv(OUTPUT, index=False)