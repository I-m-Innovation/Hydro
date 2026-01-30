from db_manager.config.settings import FLOW_HIST_BINS, FLOW_HIST_WINDOW_HOURS
from db_manager.db.conn import get_conn
from db_manager.db.sql_loader import load_sql


def refresh_flow_histogram():
    sql_refresh = load_sql("refresh_flow_histogram.sql")
    sql_refresh = sql_refresh.replace("{BINS}", str(FLOW_HIST_BINS))
    sql_refresh = sql_refresh.replace("{WINDOW_HOURS}", str(FLOW_HIST_WINDOW_HOURS))

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql_refresh)
        conn.commit()
    print("Flow histogram refreshed successfully.")
