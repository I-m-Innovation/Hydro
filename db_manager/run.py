from datetime import datetime, timedelta
import pytz

from db_manager.db.conn import get_conn
from db_manager.db.schema import ensure_raw_table, ensure_etl_state_table, ensure_measurements_index, ensure_flow_histogram_table, ensure_mv_flow_daily_avg, ensure_mv_led_status, ensure_mv_flow_exceedance_raw_vs_smoothed_2d
from db_manager.jobs.ingest_eventhub import load_eventhub_configs, start_consumers
from db_manager.jobs.transform_raw import transform_raw_to_measurements
from db_manager.jobs.refresh_stats import refresh_stats
from db_manager.jobs.clean_measurements import clean_measurements
from db_manager.jobs.refresh_duration_curve_mv import refresh_duration_curve_mv
from db_manager.jobs.refresh_flow_histogram import refresh_flow_histogram
from db_manager.jobs.refresh_mv_flow_daily_avg import refresh_mv_flow_daily_avg
from db_manager.jobs.refresh_mv_flow_exceedance_raw_vs_smoothed_2d import (
    refresh_mv_flow_exceedance_raw_vs_smoothed_2d,
)
from db_manager.jobs.refresh_mv_led_status import refresh_mv_led_status

from db_manager.config.settings import RAW_TABLE_NAME, SECONDS_BETWEEN_RAW_TO_MEASUREMENTS_TRANSFORM, SECONDS_BETWEEN_REFRESH_STATS, SECONDS_BETWEEN_CLEAN_MEASUREMENTS, SECONDS_BETWEEN_REFRESH_FLOW_HISTOGRAM, SECONDS_BETWEEN_REFRESH_LED_STATUS, MV_FLOW_DAILY_AVG_REFRESH_HOUR, MV_FLOW_DAILY_AVG_REFRESH_MINUTE, MV_FLOW_DAILY_AVG_REFRESH_TZ, DURATION_CURVE_MV_REFRESH_HOUR, DURATION_CURVE_MV_REFRESH_MINUTE, DURATION_CURVE_MV_REFRESH_TZ, FLOW_EXCEEDANCE_MV_REFRESH_HOUR, FLOW_EXCEEDANCE_MV_REFRESH_MINUTE, FLOW_EXCEEDANCE_MV_REFRESH_TZ


from time import sleep
import threading 

def start_refresh_mv_flow_daily_avg_nightly(hour=MV_FLOW_DAILY_AVG_REFRESH_HOUR, minute=MV_FLOW_DAILY_AVG_REFRESH_MINUTE, tz_name=MV_FLOW_DAILY_AVG_REFRESH_TZ):
    # runs refresh_mv_flow_daily_avg every night at the specified hour and minute in the specified timezone
    def loop():
        tz = pytz.timezone(tz_name)
        i = 1
        while True:
            try: 
                now = datetime.now(tz)
                target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if target <= now:
                    target += timedelta(days=1)
                    
                sleep_seconds = (target - now).total_seconds()
                print(f"Refresh mv_flow_daily_avg job {i} sleeping for {sleep_seconds}.")
                sleep(sleep_seconds)
                
                refresh_mv_flow_daily_avg()
                print(f"Refresh mv_flow_daily_avg job {i} executed successfully.")
                i += 1
            except Exception as e:
                print(f"Error executing refresh mv_flow_daily_avg job {i}: {e}")
                sleep(60)  # Sleep for a minute before retrying in case of error
    print(f"[scheduler] refresh_mv_flow_daily_avg_nightly started (every day at {hour:02d}:{minute:02d} {tz_name})")
    thread = threading.Thread(target=loop, daemon=True)
    thread.start()

def start_refresh_duration_curve_mv_nightly(hour=DURATION_CURVE_MV_REFRESH_HOUR, minute=DURATION_CURVE_MV_REFRESH_MINUTE, tz_name=DURATION_CURVE_MV_REFRESH_TZ):
    # runs refresh_duration_curve_mv every night at the specified hour and minute in the specified timezone
    def loop():
        tz = pytz.timezone(tz_name)
        i = 1
        while True:
            try: 
                now = datetime.now(tz)
                target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if target <= now:
                    target += timedelta(days=1)

                sleep_seconds = (target - now).total_seconds()
                print(f"Refresh duration_curve_mv job {i} sleeping for {sleep_seconds}.")
                sleep(sleep_seconds)

                refresh_duration_curve_mv()
                print(f"Refresh duration_curve_mv job {i} executed successfully.")
                i += 1
            except Exception as e:
                print(f"Error executing refresh duration_curve_mv job {i}: {e}")
                sleep(60)  # Sleep for a minute before retrying in case of error
    print(
        "[scheduler] refresh_duration_curve_mv_nightly started "
        f"(every day at {hour:02d}:{minute:02d} {tz_name})"
    )
    thread = threading.Thread(target=loop, daemon=True)
    thread.start()


def start_refresh_flow_exceedance_mv_nightly(
    hour=FLOW_EXCEEDANCE_MV_REFRESH_HOUR,
    minute=FLOW_EXCEEDANCE_MV_REFRESH_MINUTE,
    tz_name=FLOW_EXCEEDANCE_MV_REFRESH_TZ,
):
    # runs refresh_mv_flow_exceedance_raw_vs_smoothed_2d nightly
    def loop():
        tz = pytz.timezone(tz_name)
        i = 1
        while True:
            try:
                now = datetime.now(tz)
                target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if target <= now:
                    target += timedelta(days=1)

                sleep_seconds = (target - now).total_seconds()
                print(f"Refresh flow_exceedance_mv job {i} sleeping for {sleep_seconds}.")
                sleep(sleep_seconds)

                refresh_mv_flow_exceedance_raw_vs_smoothed_2d()
                print(f"Refresh flow_exceedance_mv job {i} executed successfully.")
                i += 1
            except Exception as e:
                print(f"Error executing refresh flow_exceedance_mv job {i}: {e}")
                sleep(60)
    print(
        "[scheduler] refresh_flow_exceedance_mv_nightly started "
        f"(every day at {hour:02d}:{minute:02d} {tz_name})"
    )
    thread = threading.Thread(target=loop, daemon=True)
    thread.start()


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

def start_refresh_led_status_scheduler(interval_seconds=60):
    # runs led status MV refresh in a background thread on a fixed interval
    def loop():
        i = 1
        while True:
            try:
                refresh_mv_led_status()
                print(f"Refresh mv_led_status job {i} executed successfully.")
                i += 1
            except Exception as e:
                print(f"Error executing refresh mv_led_status job {i}: {e}")
            sleep(interval_seconds)
    print(f"[scheduler] refresh mv_led_status started (every {interval_seconds}s)")
    thread = threading.Thread(target=loop, daemon=True)
    thread.start()

def main():
    print(r"""
 __        __   _                            _         ____  ____      __  __                                  
 \ \      / /__| | ___ ___  _ __ ___   ___  | |_ ___  |  _ \| __ )    |  \/  | __ _ _ __   __ _  __ _  ___ _ __ 
  \ \ /\ / / _ \ |/ __/ _ \| '_ ` _ \ / _ \ | __/ _ \ | | | |  _ \    | |\/| |/ _` | '_ \ / _` |/ _` |/ _ \ '__|
   \ V  V /  __/ | (_| (_) | | | | | |  __/ | || (_) || |_| | |_) |   | |  | | (_| | | | | (_| | (_| |  __/ |   
    \_/\_/ \___|_|\___\___/|_| |_| |_|\___|  \__\___/ |____/|____/    |_|  |_|\__,_|_| |_|\__,_|\__, |\___|_|   
                                                                                                |___/          
    """)
    
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
        ensure_mv_flow_daily_avg()
        ensure_mv_led_status()
        ensure_mv_flow_exceedance_raw_vs_smoothed_2d()
        print(
            "\nSchema checks completed: "
            f"{RAW_TABLE_NAME}, etl_state, measurements_index, "
            "flow_histogram, mv_flow_daily_avg, mv_led_status, "
            "mv_flow_exceedance_raw_vs_smoothed_2d.\n"
        )
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
    start_refresh_duration_curve_mv_nightly()
    start_refresh_flow_exceedance_mv_nightly()
    start_refresh_flow_histogram_scheduler(SECONDS_BETWEEN_REFRESH_FLOW_HISTOGRAM)
    start_refresh_mv_flow_daily_avg_nightly()
    start_refresh_led_status_scheduler(SECONDS_BETWEEN_REFRESH_LED_STATUS)
    start_consumers(eventhub_configs)


if __name__ == "__main__":
    main()
