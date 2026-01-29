# region LOAD ENV VARIABLES
import os
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("PGHOST", "localhost")
DB_PORT = int(os.getenv("PGPORT", "5432"))
DB_NAME = os.getenv("PGDBNAME", "messages_trebisacce")
DB_USER = os.getenv("PGUSER", "postgres")
DB_PASSWORD = os.getenv("PGPASSWORD", "")
HEARTBEAT_SECONDS = int(os.getenv("HEARTBEAT_SECONDS", "60"))
# endregion

MIN_SECONDS_BETWEEN_EVENTS = 900  # 15 minutes
SECONDS_BETWEEN_RAW_TO_MEASUREMENTS_TRANSFORM = 900  # 15 minutes
SECONDS_BETWEEN_REFRESH_STATS = 86400  # 24 ore
RAW_TABLE_NAME = "hydro.tab_measurements_raw"
