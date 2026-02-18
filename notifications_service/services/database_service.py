"""
Servizio per la gestione della connessione al database
"""
import psycopg2
import logging
from typing import Optional, List, Tuple
from config.settings import DatabaseConfig

logger = logging.getLogger(__name__)

class DatabaseService:
    def __init__(self):
        self.config = DatabaseConfig()
    
    def connect(self):
        """Crea una connessione al database PostgreSQL"""
        try:
            conn = psycopg2.connect(
                host=self.config.HOST,
                user=self.config.USER,
                password=self.config.PASSWORD,
                dbname=self.config.DBNAME,
                port=self.config.PORT
            )
            logger.info("Connesso al database PostgreSQL")
            return conn
        except Exception as e:
            logger.error(f"Errore connessione database: {e}")
            return None
    
    def fetch_misuratori_stats(self, limit: int = 100) -> Tuple[Optional[List], Optional[str]]:
        """
        Recupera le statistiche dei misuratori
        Ritorna: (righe, errore)
        """
        conn = self.connect()
        if not conn:
            return None, "Connessione al database fallita"
        
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT
                        tm.id_misuratore,
                        tm.name,
                        tm.location,
                        tm.is_active,
                        ts.total_measurements,
                        ts.first_measurement,
                        ts.last_measurement,
                        ts.avg_24h,
                        ts.avg_7d,
                        ts.avg_30d,
                        ts.updated_at
                    FROM {self.config.SCHEMA}.tab_misuratori tm
                    LEFT JOIN {self.config.SCHEMA}.tab_statistiche_misuratori ts 
                        ON tm.id_misuratore = ts.id_misuratore
                    ORDER BY tm.is_active DESC, tm.id_misuratore
                    LIMIT %s
                    """,
                    (limit,)
                )
                rows = cur.fetchall()
                logger.info(f"Recuperate {len(rows)} statistiche misuratori")
                return rows, None
        except Exception as e:
            error_msg = f"Errore query statistiche: {e}"
            logger.error(error_msg)
            return None, error_msg
        finally:
            conn.close()
    
    def fetch_active_misuratori_count(self) -> Tuple[Optional[int], Optional[str]]:
        """Conta i misuratori attivi"""
        conn = self.connect()
        if not conn:
            return None, "Connessione al database fallita"
        
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT COUNT(*) FROM {self.config.SCHEMA}.tab_misuratori WHERE is_active = true"
                )
                count = cur.fetchone()[0]
                return count, None
        except Exception as e:
            error_msg = f"Errore conteggio misuratori: {e}"
            logger.error(error_msg)
            return None, error_msg
        finally:
            conn.close()