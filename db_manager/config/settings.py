import os
from dotenv import load_dotenv

load_dotenv()

# Database connection
DB_HOST = os.getenv("PGHOST", "localhost")
DB_PORT = int(os.getenv("PGPORT", "5432"))
DB_NAME = os.getenv("PGDBNAME", "messages_trebisacce")
DB_USER = os.getenv("PGUSER", "postgres")
DB_PASSWORD = os.getenv("PGPASSWORD", "")

# Ingestion pacing
HEARTBEAT_SECONDS = int(os.getenv("HEARTBEAT_SECONDS", "60"))
MIN_SECONDS_BETWEEN_EVENTS = 5  # 5 seconds

# Scheduler intervals (seconds)
SECONDS_BETWEEN_RAW_TO_MEASUREMENTS_TRANSFORM = 20  # 20 seconds
SECONDS_BETWEEN_CLEAN_MEASUREMENTS = 20  # 20 seconds
SECONDS_BETWEEN_REFRESH_STATS = 20  # 20 seconds
SECONDS_BETWEEN_REFRESH_MV = 20  # 20 seconds
SECONDS_BETWEEN_REFRESH_FLOW_HISTOGRAM = 20  # 20 seconds

# Tables
RAW_TABLE_NAME = "hydro.tab_measurements_raw"

# Hampel filter parameters
HAMPEL_WINDOW_SIZE = 100
HAMPEL_SIGMA_THRESHOLD = 3.5

# Flow histogram parameters
FLOW_HIST_BINS = 100
FLOW_HIST_WINDOW_HOURS = 24
