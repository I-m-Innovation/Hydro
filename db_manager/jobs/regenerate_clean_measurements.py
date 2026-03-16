import pandas as pd
from hampel import hampel

from db_manager.db.conn import get_conn
from db_manager.db.sql_loader import load_sql
from db_manager.config.settings import HAMPEL_WINDOW_SIZE, HAMPEL_SIGMA_THRESHOLD


MAX_NUMERIC = 9_999_999.999
MIN_NUMERIC = -9_999_999.999


def _clamp_numeric(value):
    if value is None:
        return None
    if value > MAX_NUMERIC:
        return MAX_NUMERIC
    if value < MIN_NUMERIC:
        return MIN_NUMERIC
    return value


def regenerate_clean_measurements():
    sql_upsert = load_sql("upsert_cleaned_measurements.sql")

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                        SELECT DISTINCT id_misuratore
                        FROM hydro.tab_measurements_clean
                        ORDER BY id_misuratore;
                        """)
            device_ids = [row[0] for row in cur.fetchall()]

        if not device_ids:
            print("No measurements to regenerate.")
            return

        total_rows = 0
        for device_id in device_ids:
            print(f"[regenerate] start device {device_id}")
            with conn.cursor() as cur:
                cur.execute("""
                            SELECT data_misurazione, flow_ls_raw
                            FROM hydro.tab_measurements_clean
                            WHERE id_misuratore = %s
                            ORDER BY data_misurazione;
                            """, (device_id,))
                rows = cur.fetchall()

            if not rows:
                continue

            df = pd.DataFrame(rows, columns=["ts_s", "flow_raw"])
            series = df["flow_raw"].astype(float)

            result = hampel(
                series,
                window_size=HAMPEL_WINDOW_SIZE,
                n_sigma=HAMPEL_SIGMA_THRESHOLD,
            )
            filtered = result.filtered_data
            outlier_indices = set(result.outlier_indices)
            medians = result.medians
            thresholds = result.thresholds

            out_params = []
            for i, row in df.iterrows():
                ts_s = row["ts_s"]
                if ts_s is None:
                    continue
                is_outlier = i in outlier_indices
                flow_raw = row["flow_raw"]
                out_params.append((
                    device_id,
                    ts_s,
                    _clamp_numeric(float(flow_raw)) if flow_raw is not None else None,
                    _clamp_numeric(float(filtered[i])) if filtered is not None else None,
                    bool(is_outlier),
                    _clamp_numeric(float(medians[i])) if medians is not None else None,
                    _clamp_numeric(float(thresholds[i])) if thresholds is not None else None,
                ))

            with conn.cursor() as cur:
                cur.executemany(sql_upsert, out_params)
            conn.commit()

            total_rows += len(out_params)
            print(f"[regenerate] device {device_id}: {len(out_params)} rows")

        print(f"[regenerate] upserted {total_rows} rows")


if __name__ == "__main__":
    regenerate_clean_measurements()
