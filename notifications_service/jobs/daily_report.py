"""
Job per l'invio del rapporto giornaliero alle 08:30
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from datetime import datetime
from services.database_service import DatabaseService
from services.telegram_service import TelegramService
from config.settings import LOCAL_TZ, NotificationConfig

# Configurazione logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('daily_report.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def main():
    """Esegue il rapporto giornaliero"""
    logger.info("=== AVVIO RAPPORTO GIORNALIERO ===")
    
    if not NotificationConfig.ENABLE_DAILY_REPORTS:
        logger.info("Rapporti giornalieri disabilitati in configurazione")
        return
    
    try:
        # Inizializza servizi
        db_service = DatabaseService()
        telegram_service = TelegramService()
        
        # Recupera dati dal database
        logger.info("Recupero statistiche misuratori...")
        stats_data, error = db_service.fetch_misuratori_stats()
        if error:
            logger.error(f"Errore recupero statistiche: {error}")
            telegram_service.send_message(f"❌ *Errore Rapporto Giornaliero*\\n\\nImpossibile recuperare dati dal database:\\n{error}")
            return
        
        # Conta misuratori attivi
        total_active, count_error = db_service.fetch_active_misuratori_count()
        if count_error:
            logger.error(f"Errore conteggio misuratori: {count_error}")
            total_active = len(stats_data) if stats_data else 0
        
        if not stats_data:
            logger.warning("Nessun dato statistiche trovato")
            telegram_service.send_message("⚠️ *Rapporto Giornaliero*\\n\\nNessun dato statistiche disponibile nel database.")
            return
        
        # Genera e invia rapporto
        logger.info(f"Generazione rapporto per {len(stats_data)} misuratori...")
        report = telegram_service.format_daily_report(stats_data, total_active)
        
        success = telegram_service.send_long_message(report)
        
        if success:
            logger.info("✅ Rapporto giornaliero inviato con successo")
        else:
            logger.error("❌ Errore invio rapporto giornaliero")
            
    except Exception as e:
        logger.error(f"Errore non gestito nel rapporto giornaliero: {e}")
        try:
            telegram_service = TelegramService()
            telegram_service.send_message(f"❌ *Errore Critico Rapporto*\\n\\n```{str(e)}```")
        except:
            pass  # Se non riesce nemmeno a inviare l'errore, logga e basta
    
    logger.info("=== FINE RAPPORTO GIORNALIERO ===")

if __name__ == "__main__":
    main()