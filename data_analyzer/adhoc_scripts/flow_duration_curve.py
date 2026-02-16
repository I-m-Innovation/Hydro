import matplotlib.pyplot as plt
import pandas as pd
import math 
import psycopg 
from datetime import datetime

import os 
from dotenv import load_dotenv

load_dotenv()
PGHOST = os.getenv("PGHOST")
PGUSER = os.getenv("PGUSER")
PGPASSWORD = os.getenv("PGPASSWORD")
PGDBNAME = os.getenv("PGDBNAME")
PGPORT = os.getenv("PGPORT")



# connection to postgres db
def get_conn():
    return psycopg.connect(
        dbname= PGDBNAME,
        user=PGUSER,
        password=PGPASSWORD,
        host=PGHOST,
        port=PGPORT,
    )




if __name__ == "__main__":
    start_ts = datetime.now()
    print(f"[START] {start_ts:%Y-%m-%d %H:%M:%S}")

    with get_conn() as conn:
        with conn.cursor() as cur:
            # Aggiorna la materialized view
            print("Refreshing materialized view hydro.mv_flow_duration_curve_daily...")
            cur.execute("REFRESH MATERIALIZED VIEW hydro.mv_flow_duration_curve_daily;")
            # Recupera la lista dei misuratori
            print("Done. Proceding to retrieve data and plot FDCs...")
            cur.execute("SELECT id_misuratore FROM hydro.tab_misuratori")
            misuratori = [r[0] for r in cur.fetchall()]
        # numero di misuratori e configurazione subplot
        n = len(misuratori)
        cols = 3
        rows = math.ceil(n / cols)

        fig, axes = plt.subplots(rows, cols, figsize=(cols * 6, rows * 4))
        axes = axes.flatten()

        for i, misuratore in enumerate(misuratori):
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT flow_avg_day, p_exceed
                    FROM hydro.mv_flow_duration_curve_daily
                    WHERE id_misuratore = %s
                    ORDER BY p_exceed
                    """,
                    (misuratore,),
                )
                df = pd.DataFrame(cur.fetchall(), columns=["flow_avg_day", "p_exceed"])

            ax = axes[i]
            if df.empty:
                ax.set_title(f"{misuratore} (no data)")
                ax.axis("off")
                continue

            ax.plot(df["p_exceed"], df["flow_avg_day"], linestyle="-")
            ax.set_title(misuratore)
            ax.set_xlabel("Exceedance Probability (%)")
            ax.set_ylabel("Flow (l/s)")
            ax.grid(True)
            ax.set_xlim(0, 100)
            ax.set_ylim(0, df["flow_avg_day"].max())

        # spegni eventuali assi vuoti
        for j in range(i + 1, len(axes)):
            axes[j].axis("off")

        fig.suptitle("Flow Duration Curves", fontsize=14)
        fig.tight_layout()
        
        end_ts = datetime.now()
        print(f"[END]   {end_ts:%Y-%m-%d %H:%M:%S}")
        print(f"Duration: {end_ts - start_ts}")    
        plt.show()

    
        
        


# REFRESH MATERIALIZED VIEW hydro.mv_flow_duration_curve_daily;

# region query to create the materialized view
"""
 WITH daily AS (
         SELECT m.id_misuratore,
            date_trunc('day'::text, c.data_misurazione)::date AS giorno,
            avg(c.flow_ls_smoothed)::double precision AS flow_avg_day
           FROM hydro.tab_misuratori m
             JOIN hydro.tab_measurements_clean c ON c.id_misuratore = m.id_misuratore
          WHERE c.flow_ls_smoothed IS NOT NULL
          GROUP BY m.id_misuratore, (date_trunc('day'::text, c.data_misurazione)::date)
        ), ranked AS (
         SELECT daily.id_misuratore,
            daily.giorno,
            daily.flow_avg_day,
            row_number() OVER (PARTITION BY daily.id_misuratore ORDER BY daily.flow_avg_day DESC) AS m,
            count(*) OVER (PARTITION BY daily.id_misuratore) AS n
           FROM daily
        )
 SELECT id_misuratore,
    giorno,
    flow_avg_day,
    m,
    n,
    m::double precision / (n + 1)::double precision * 100::double precision AS p_exceed
   FROM ranked;
"""
# endregion