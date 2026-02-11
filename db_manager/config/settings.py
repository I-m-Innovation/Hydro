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
MIN_SECONDS_BETWEEN_EVENTS = 280  # 280 seconds (4 min 40s)

# Scheduler intervals (seconds)
SECONDS_BETWEEN_RAW_TO_MEASUREMENTS_TRANSFORM = 20  # 20 seconds
SECONDS_BETWEEN_CLEAN_MEASUREMENTS = 20  # 20 seconds
SECONDS_BETWEEN_REFRESH_STATS = 20  # 20 seconds
SECONDS_BETWEEN_REFRESH_MV = 20  # 20 seconds
SECONDS_BETWEEN_REFRESH_FLOW_HISTOGRAM = 86400  # 24 hours

# Refresh MV Flow Daily Avg schedule (nightly at 2:00 AM Rome time)
MV_FLOW_DAILY_AVG_REFRESH_HOUR = 2 # 2 AM
MV_FLOW_DAILY_AVG_REFRESH_MINUTE = 0
MV_FLOW_DAILY_AVG_REFRESH_TZ = "Europe/Rome"

# Tables
RAW_TABLE_NAME = "hydro.tab_measurements_raw"

# Hampel filter parameters
HAMPEL_WINDOW_SIZE = 49  # Must be odd
HAMPEL_SIGMA_THRESHOLD = 3.5

# Flow histogram parameters
FLOW_HIST_BINS = 100
# 0 means "all-time" (no time window filter)
FLOW_HIST_WINDOW_HOURS = 0
