"""
Job per il controllo di misuratori con dati obsoleti (stale)
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
import json
from datetime import datetime, timedelta
from typing import Set
from services.database_service import DatabaseService
from services.telegram_service import TelegramService
from config.settings import LOCAL_TZ, NotificationConfig, TelegramConfig

# Configurazione logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('stale_check.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# File per tenere traccia degli alert già inviati
ALERT_STATE_FILE = "alert_state.json"

def load_alert_state() -> dict:
    """Carica lo stato degli alert dal file JSON"""
    try:
        if os.path.exists(ALERT_STATE_FILE):
            with open(ALERT_STATE_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Errore caricamento stato alert: {e}")
    return {}

def save_alert_state(state: dict):
    """Salva lo stato degli alert nel file JSON"""
    try:
        with open(ALERT_STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2, default=str)
    except Exception as e:
        logger.error(f"Errore salvataggio stato alert: {e}")

def main():
    """Controlla misuratori con dati obsoleti e invia alert"""
    logger.info("=== AVVIO CONTROLLO DATI STALE ===")
    
    if not NotificationConfig.ENABLE_STALE_ALERTS:
        logger.info("Alert dati stale disabilitati in configurazione")
        return
    
    try:
        # Inizializza servizi
        db_service = DatabaseService()
        telegram_service = TelegramService()
        
        # Carica stato alert precedente
        alert_state = load_alert_state()
        previously_stale = set(alert_state.get('stale_devices', []))
        
        # Recupera dati dal database
        logger.info("Controllo stato misuratori...")
        stats_data, error = db_service.fetch_misuratori_stats()
        if error:
            logger.error(f"Errore recupero statistiche: {error}")
            return
        
        if not stats_data:
            logger.warning("Nessun dato statistiche trovato")
            return
        
        # Analizza misuratori stale
        currently_stale = set()
        stale_devices = []
        recovered_devices = []
        
        for row in stats_data:
            id_misuratore, name, location, is_active, total_measurements, first_measurement, last_measurement, avg_24h, avg_7d, avg_30d, updated_at = row
            
            if not telegram_service._is_recent_24h(last_measurement):
                currently_stale.add(id_misuratore)
                stale_devices.append({
                    'id': id_misuratore,
                    'name': name or id_misuratore,
                    'last': last_measurement,
                    'location': location
                })
            elif id_misuratore in previously_stale:
                # Misuratore si è ripreso
                recovered_devices.append({
                    'id': id_misuratore,
                    'name': name or id_misuratore,
                    'last': last_measurement,
                    'location': location
                })
        
        # Trova nuovi misuratori diventati stale
        newly_stale = currently_stale - previously_stale
        newly_stale_devices = [d for d in stale_devices if d['id'] in newly_stale]
        
        logger.info(f"Stato: {len(currently_stale)} stale, {len(newly_stale)} nuovi, {len(recovered_devices)} recuperati")
        
        # Invia alert per nuovi misuratori stale
        if newly_stale_devices:
            logger.info(f"Invio alert per {len(newly_stale_devices)} nuovi misuratori stale")
            alert_message = telegram_service.format_stale_alert(newly_stale_devices)
            
            if telegram_service.send_long_message(alert_message):
                logger.info("✅ Alert stale inviato con successo")
            else:
                logger.error("❌ Errore invio alert stale")
        
        # Invia notifica di recupero per qualsiasi misuratore che torna online
        if recovered_devices:
            logger.info(f"Invio notifica recupero per {len(recovered_devices)} misuratori")
            recovery_message = f"""✅ *RECUPERO MISURATORI*

🟢 {len(recovered_devices)} misuratore{'i' if len(recovered_devices) > 1 else ''} tornat{'i' if len(recovered_devices) > 1 else 'o'} online:

"""
            for device in recovered_devices[:10]:  # Mostra fino a 10 dispositivi
                recovery_message += f"• *{device['name']}* ({device['location']})\n"
            
            if len(recovered_devices) > 10:
                recovery_message += f"• ... e altri {len(recovered_devices) - 10}\n"
            
            recovery_message += f"\n⏱{datetime.now(LOCAL_TZ).strftime('%d/%m/%Y %H:%M')}\n#Hydra #Recupero"
            
            telegram_service.send_message(recovery_message)
        
        # Aggiorna stato alert
        new_alert_state = {
            'stale_devices': list(currently_stale),
            'last_check': datetime.now().isoformat(),
            'total_stale': len(currently_stale),
            'total_active': len(stats_data)
        }
        save_alert_state(new_alert_state)
        
        logger.info(f"Controllo completato: {len(currently_stale)}/{len(stats_data)} misuratori stale")
        
    except Exception as e:
        logger.error(f"Errore non gestito nel controllo stale: {e}")
        try:
            telegram_service = TelegramService()
            telegram_service.send_message(f"❌ *Errore Controllo Stale*\\n\\n```{str(e)}```")
        except:
            pass
    
    logger.info("=== FINE CONTROLLO DATI STALE ===")

if __name__ == "__main__":
    main()