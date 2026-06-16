from db_manager.db.conn import get_conn
from db_manager.db.sql_loader import load_sql


def refresh_mv_flow_histogram_hours():
    sql_refresh = load_sql("refresh_mv_flow_histogram_hours.sql")

    with get_conn() as conn:
        conn.autocommit = True
        with conn.cursor() as cursor:
            cursor.execute(sql_refresh)

    print("Materialized view 'mv_flow_histogram_hours' refreshed successfully.")
