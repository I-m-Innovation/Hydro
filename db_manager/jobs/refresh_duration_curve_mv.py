from db_manager.db.conn import get_conn
from db_manager.db.sql_loader import load_sql

def refresh_duration_curve_mv():
    sql_refresh = load_sql("refresh_mvflow_duration_curve_daily.sql")

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql_refresh)
        conn.commit()
    print("Duration curve materialized view refreshed successfully.")