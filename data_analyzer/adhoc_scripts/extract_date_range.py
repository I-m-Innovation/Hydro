import pandas as pd
from datetime import datetime

# =========================
# Configurable parameters
# =========================
INPUT = r"C:\Users\Luca Parise\Desktop\sorgenti\Hydra_3_0\data_analyzer\csv_hampel\Gateway 1_hampel copy.csv"
OUTPUT = r"C:\Users\Luca Parise\Desktop\sorgenti\Hydra_3_0\data_analyzer\csv_hampel\Gateway 1_hampel_date_range.csv"
COL_TS = "data_misurazione"  # cambia se la tua colonna ha un altro nome

# Periodo di estrazione: da start_date a end_date (inclusi)
START_DATE = "2023-12-01 00:00:00"  # Formato: YYYY-MM-DD HH:MM:SS
END_DATE = "2023-12-31 23:59:59"    # Formato: YYYY-MM-DD HH:MM:SS


def main():
    print(f"Caricamento dati da: {INPUT}")
    
    # Legge il CSV
    df = pd.read_csv(INPUT)
    print(f"Righe caricate: {len(df)}")
    
    # Converte la colonna timestamp
    df[COL_TS] = pd.to_datetime(df[COL_TS], errors="coerce")
    
    # Crea i timestamp di inizio e fine
    start_ts = pd.Timestamp(START_DATE)
    end_ts = pd.Timestamp(END_DATE)
    
    print(f"Periodo di estrazione: dal {start_ts} al {end_ts}")
    
    # Filtra i dati nel range specificato
    original_count = len(df)
    df_filtered = df[(df[COL_TS] >= start_ts) & (df[COL_TS] <= end_ts)]
    filtered_count = len(df_filtered)
    
    print(f"Righe dopo filtro: {filtered_count} (rimosse: {original_count - filtered_count})")
    
    # Salva il risultato
    df_filtered.to_csv(OUTPUT, index=False)
    print(f"File salvato in: {OUTPUT}")
    
    # Statistiche finali
    if filtered_count > 0:
        first_date = df_filtered[COL_TS].min()
        last_date = df_filtered[COL_TS].max()
        print(f"Prima data estratta: {first_date}")
        print(f"Ultima data estratta: {last_date}")
    else:
        print("Nessun dato trovato nel periodo specificato!")


if __name__ == "__main__":
    main()