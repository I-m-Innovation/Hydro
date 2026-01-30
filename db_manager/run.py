from db_manager.db.conn import get_conn
from db_manager.db.schema import ensure_raw_table, ensure_etl_state_table, ensure_measurements_index, ensure_flow_histogram_table
from db_manager.jobs.ingest_eventhub import load_eventhub_configs, start_consumers
from db_manager.jobs.transform_raw import transform_raw_to_measurements
from db_manager.jobs.refresh_stats import refresh_stats
from db_manager.jobs.clean_measurements import clean_measurements
from db_manager.jobs.refresh_duration_curve_mv import refresh_duration_curve_mv
from db_manager.jobs.refresh_flow_histogram import refresh_flow_histogram

from db_manager.config.settings import RAW_TABLE_NAME, SECONDS_BETWEEN_RAW_TO_MEASUREMENTS_TRANSFORM, SECONDS_BETWEEN_REFRESH_STATS, SECONDS_BETWEEN_CLEAN_MEASUREMENTS, SECONDS_BETWEEN_REFRESH_MV, SECONDS_BETWEEN_REFRESH_FLOW_HISTOGRAM

from time import sleep
import threading 


def start_transform_scheduler(interval_seconds=300):
    # Runs the ETL transform in a background thread on a fixed interval.
    def loop():
        i = 1
        while True: 
            try:
                transform_raw_to_measurements()
                print(f"Transform job {i} executed successfully.")
                i += 1
            except Exception as e:
                print(f"Error executing transform job {i}: {e}")
            sleep(interval_seconds)
    # Start periodic raw -> measurements transform.
    print(f"[scheduler] transform_raw started (every {interval_seconds}s)")
    thread = threading.Thread(target=loop, daemon=True)
    thread.start()

def start_refresh_stats_scheduler(interval_seconds=86400):
    # Runs the stats refresh in a background thread on a fixed interval.
    def loop():
        i = 1
        while True:
            try:
                refresh_stats()
                print(f"Refresh stats job {i} executed successfully.")
                i += 1
            except Exception as e:
                print(f"Error executing refresh stats job {i}: {e}")
            sleep(interval_seconds)
    # Start periodic stats refresh.
    print(f"[scheduler] refresh_stats started (every {interval_seconds}s)")
    thread = threading.Thread(target=loop, daemon=True)
    thread.start()

def start_clean_measurements_scheduler(interval_seconds=300):
    # runs the measurements cleaning in a background thread on a fixed interval 
    def loop():
        i = 1
        while True:
            try:
                clean_measurements()
                print(f"Clean measurements job {i} executed successfully.")
                i += 1
            except Exception as e:
                print(f"Error executing clean measurements job {i}: {e}")
            sleep(interval_seconds)
    # start periodic measurements cleaning
    print(f"[scheduler] clean_measurements started (every {interval_seconds}s)")
    thread = threading.Thread(target=loop, daemon=True)
    thread.start()

def start_refresh_mv_scheduler(interval_seconds=86400):
    # runs materialized view refresh in a background thread on a fixed interval
    def loop():
        i = 1
        while True:
            try: 
                refresh_duration_curve_mv()
                print(f"Refresh duration curve MV job {i} executed successfully.")
                i += 1
            except Exception as e:
                print(f"Error executing refresh duration curve MV job {i}: {e}")
            sleep(interval_seconds)
    # start periodic materialized view refresh
    print(f"[scheduler] refresh_duration_curve_mv started (every {interval_seconds}s)")
    thread = threading.Thread(target=loop, daemon=True)
    thread.start()

def start_refresh_flow_histogram_scheduler(interval_seconds=3600):
    # runs flow histogram refresh in a background thread on a fixed interval
    def loop():
        i = 1
        while True:
            try:
                refresh_flow_histogram()
                print(f"Refresh flow histogram job {i} executed successfully.")
                i += 1
            except Exception as e:
                print(f"Error executing flow histogram job {i}: {e}")
            sleep(interval_seconds)
    # start periodic flow histogram refresh
    print(f"[scheduler] refresh_flow_histogram started (every {interval_seconds}s)")
    thread = threading.Thread(target=loop, daemon=True)
    thread.start()

def main():
    # Basic DB connectivity check.
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                cur.fetchone()
        print("Connection to database successful")
    except Exception as e:
        print(f"Error connecting to database: {e}")
        raise

    # Load EventHub configs from DB before starting consumers.
    eventhub_configs = load_eventhub_configs()

    # Ensure required tables/indexes exist before processing data.
    try:
        ensure_raw_table()
        ensure_etl_state_table()
        ensure_measurements_index()
        ensure_flow_histogram_table()
        print(f"\nTable {RAW_TABLE_NAME} checked/created successfully.\n")
    except Exception as e:
        print(f"Error creating/checking table {RAW_TABLE_NAME}: {e}")
        raise

    if not eventhub_configs:
        print("No valid eventhub configurations found.")
        raise RuntimeError("No valid eventhub configurations found.")
    length = len(eventhub_configs)
    print(f"\n--- CREATING {length} EVENT HUB CONSUMER CLIENTS ---\n")
    
    
    # Start background jobs before blocking on consumers.
    start_transform_scheduler(SECONDS_BETWEEN_RAW_TO_MEASUREMENTS_TRANSFORM) 
    start_refresh_stats_scheduler(SECONDS_BETWEEN_REFRESH_STATS) 
    start_clean_measurements_scheduler(SECONDS_BETWEEN_CLEAN_MEASUREMENTS)
    start_refresh_mv_scheduler(SECONDS_BETWEEN_REFRESH_MV)
    start_refresh_flow_histogram_scheduler(SECONDS_BETWEEN_REFRESH_FLOW_HISTOGRAM)
    start_consumers(eventhub_configs)


if __name__ == "__main__":
    main()
