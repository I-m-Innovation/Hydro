from db_manager.db.conn import get_conn
from db_manager.db.sql_loader import load_sql

def refresh_mv_flow_daily_avg():
    sql_refresh = load_sql("refresh_mv_flow_daily_avg.sql")
    
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql_refresh)
        conn.commit()
    
    print("Materialized view 'mv_flow_daily_avg' refreshed successfully.")
        
        
        