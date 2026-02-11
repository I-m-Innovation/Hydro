from db_manager.db.conn import get_conn
from db_manager.db.sql_loader import load_sql

def refresh_mv_flow_daily_avg():
    sql_refresh = load_sql("refresh_mv_flow_daily_avg.sql")
    
    with get_conn() as conn:
        conn.autocommit = True  # Ensure the refresh runs outside of a transaction block
        with conn.cursor() as cursor:
            cursor.execute(sql_refresh)
    
    print("Materialized view 'mv_flow_daily_avg' refreshed successfully.")
        
# a transaction block is not needed for refreshing a materialized view, and in fact can cause issues if the refresh takes a long time. Setting autocommit to True ensures that the refresh runs in its own transaction, which is important for performance and to avoid locking issues.
        
        