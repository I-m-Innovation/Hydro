import pandas as pd
from hampel import hampel
import psycopg

from db_manager.db.sql_loader import load_sql
from db_manager.config.settings import HAMPEL_WINDOW_SIZE, HAMPEL_SIGMA_THRESHOLD


MAX_NUMERIC = 9_999_999.999
MIN_NUMERIC = -9_999_999.999

# Misuratore target
TARGET_DEVICE_ID = "Gateway 1"

# Hard-coded DB connection params (local only for this job)
PGHOST = "portalehydro-db.postgres.database.azure.com"
PGUSER = "pgadmin_hydro"
PGPASSWORD = "Artemis_2026"
PGDBNAME = "hydro"
PGPORT = 5432


def get_conn():
    return psycopg.connect(
        dbname=PGDBNAME,
        user=PGUSER,
        password=PGPASSWORD,
        host=PGHOST,
        port=PGPORT,
    )


def _clamp_numeric(value):
    if value is None:
        return None
    if value > MAX_NUMERIC:
        return MAX_NUMERIC
    if value < MIN_NUMERIC:
        return MIN_NUMERIC
    return value


def regenerate_clean_measurements_single():
    sql_upsert = load_sql("upsert_cleaned_measurements.sql")

    with get_conn() as conn:
        with conn.cursor() as cur:
            # Carica tutte le misure raw trasformate per il misuratore scelto
            print(f"[start] loading measurements for device_id={TARGET_DEVICE_ID}")
            cur.execute("""
                SELECT device_id, ts_s, instant_flow_rate_2
                FROM hydro.tab_measurements
                WHERE device_id = %s
                ORDER BY ts_s;
            """, (TARGET_DEVICE_ID,))
            rows = cur.fetchall()

        if not rows:
            print(f"No measurements found for device_id={TARGET_DEVICE_ID}")
            return
        print(f"[loaded] rows={len(rows)}")

        df = pd.DataFrame(rows, columns=["device_id", "ts_s", "flow_raw"])
        # Remove rows with null timestamps or flow values before Hampel
        df["flow_raw"] = pd.to_numeric(df["flow_raw"], errors="coerce")
        df = df.dropna(subset=["ts_s", "flow_raw"]).reset_index(drop=True)
        print(f"[clean] valid_rows={len(df)} (dropped={len(rows) - len(df)})")
        if df.empty:
            print(f"No valid measurements found for device_id={TARGET_DEVICE_ID}")
            return
        series = df["flow_raw"].astype(float)

        print(f"[hampel] window={HAMPEL_WINDOW_SIZE} sigma={HAMPEL_SIGMA_THRESHOLD}")
        result = hampel(series, window_size=HAMPEL_WINDOW_SIZE, n_sigma=HAMPEL_SIGMA_THRESHOLD)
        filtered = result.filtered_data
        outlier_indices = set(result.outlier_indices)
        medians = result.medians
        thresholds = result.thresholds
        print(f"[hampel] outliers={len(outlier_indices)}")

        out_params = []
        total = len(df)
        log_every = max(1, total // 10)
        for i, row in df.iterrows():
            if i % log_every == 0:
                print(f"[progress] {i}/{total}")
            ts_s = row["ts_s"]
            if ts_s is None:
                continue
            is_outlier = i in outlier_indices
            flow_raw = row["flow_raw"]
            out_params.append((
                TARGET_DEVICE_ID,
                ts_s,
                _clamp_numeric(float(flow_raw)) if flow_raw is not None else None,
                _clamp_numeric(float(filtered[i])) if filtered is not None else None,
                bool(is_outlier),
                _clamp_numeric(float(medians[i])) if medians is not None else None,
                _clamp_numeric(float(thresholds[i])) if thresholds is not None else None
            ))

        with conn.cursor() as cur:
            # Rimuove i dati precedenti per il misuratore target
            print("[db] deleting previous clean rows")
            cur.execute("""
                DELETE FROM hydro.tab_measurements_clean
                WHERE id_misuratore = %s;
            """, (TARGET_DEVICE_ID,))
            # Re-inserisce i dati ricalcolati
            print(f"[db] upserting rows={len(out_params)}")
            cur.executemany(sql_upsert, out_params)
        conn.commit()
        print(f"[regenerate_single] device {TARGET_DEVICE_ID}: {len(out_params)} rows")


if __name__ == "__main__":
    regenerate_clean_measurements_single()
