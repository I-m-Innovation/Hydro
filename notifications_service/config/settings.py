"""
Configurazione per il servizio di notifiche Telegram
"""
import os
from dotenv import load_dotenv
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# Carica variabili d'ambiente
load_dotenv()

# Configurazione Database PostgreSQL
class DatabaseConfig:
    HOST = os.getenv("PGHOST")
    USER = os.getenv("PGUSER") 
    PASSWORD = os.getenv("PGPASSWORD")
    DBNAME = os.getenv("PGDBNAME")
    PORT = os.getenv("PGPORT")
    SCHEMA = os.getenv("SCHEMA", "hydro")

# Configurazione Bot Telegram
class TelegramConfig:
    BOT_TOKEN = os.getenv("TOKEN_TELEGRAM_BOT")
    CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # ID del gruppo dove inviare notifiche
    STALE_THRESHOLD_HOURS = int(os.getenv("TELEGRAM_STALE_THRESHOLD_HOURS", "24"))
    
    @classmethod
    def validate(cls):
        if not cls.BOT_TOKEN:
            raise RuntimeError("Missing TOKEN_TELEGRAM_BOT in environment.")
        if not cls.CHAT_ID:
            raise RuntimeError("Missing TELEGRAM_CHAT_ID in environment.")

# Configurazione Timezone
LOCAL_TZ = ZoneInfo("Europe/Rome")

# Configurazione Notifiche
class NotificationConfig:
    DAILY_REPORT_HOUR = 8
    DAILY_REPORT_MINUTE = 30
    MAX_MESSAGE_LENGTH = 3500
    ENABLE_STALE_ALERTS = True
    ENABLE_DAILY_REPORTS = True