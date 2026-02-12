from db_manager.config.settings import RAW_TABLE_NAME
from db_manager.db.conn import get_conn
from db_manager.db.sql_loader import load_sql

def ensure_raw_table():
    try:
        with get_conn() as conn:
            sql = load_sql("ensure_raw_table.sql").replace("{RAW_TABLE_NAME}", RAW_TABLE_NAME)
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
        print("[schema] raw table ok")
    except Exception as e:
        print(f"[schema] raw table error: {e}")
        raise

def ensure_etl_state_table():
    try:
        with get_conn() as conn:
            sql = load_sql("ensure_etl_state_table.sql")
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
        print("[schema] etl_state table ok")
    except Exception as e:
        print(f"[schema] etl_state table error: {e}")
        raise

def ensure_measurements_index():
    try:
        with get_conn() as conn:
            sql = load_sql("ensure_measurements_index.sql")
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
        print("[schema] measurements index ok")
    except Exception as e:
        print(f"[schema] measurements index error: {e}")
        raise

def ensure_flow_histogram_table():
    try:
        with get_conn() as conn:
            sql = load_sql("ensure_flow_histogram_table.sql")
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
        print("[schema] flow histogram table ok")
    except Exception as e:
        print(f"[schema] flow histogram table error: {e}")
        raise

def ensure_mv_flow_daily_avg():
    try:
        with get_conn() as conn:
            sql = load_sql("ensure_mv_flow_daily_avg.sql")
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
        print("[schema] mv_flow_daily_avg ok")
    except Exception as e:
        print(f"[schema] mv_flow_daily_avg error: {e}")
        raise

def ensure_mv_led_status():
    try:
        with get_conn() as conn:
            sql = load_sql("ensure_mv_led_status.sql")
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
        print("[schema] mv_led_status ok")
    except Exception as e:
        print(f"[schema] mv_led_status error: {e}")
        raise
