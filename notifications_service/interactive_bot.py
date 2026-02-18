"""
Bot Telegram interattivo per comandi manuali
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
import telebot
import threading
import time
import schedule

from datetime import datetime
from services.database_service import DatabaseService
from services.telegram_service import TelegramService
from config.settings import TelegramConfig, LOCAL_TZ, SchedulerConfig

# Configurazione logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Verifica configurazione
TelegramConfig.validate()
bot = telebot.TeleBot(TelegramConfig.BOT_TOKEN)

# Servizi
db_service = DatabaseService()
telegram_service = TelegramService()

@bot.message_handler(content_types=['new_chat_members'])
def welcome_new_members(message):
    """Messaggio di benvenuto per nuovi membri del gruppo"""
    try:
        for new_member in message.new_chat_members:
            if new_member.is_bot:
                continue  # Ignora altri bot
            
            username = new_member.first_name or new_member.username or "Nuovo utente"
            
            welcome_message = f"""```
    ╔═══════════════════════════════════════╗
    ║           🏗️ HYDRA 3.0 BOT            ║
    ║      Sistema Monitoraggio Idrometrico ║
    ╚═══════════════════════════════════════╝
```

👋 **Benvenuto {username}!**

Sono il bot di monitoraggio per il sistema Hydra 3.0.
Fornisco rapporti automatici e comandi on-demand per il controllo dei misuratori idrometrici.

**JOB AUTOMATICI ATTIVI:**
• Rapporto giornaliero: `{SchedulerConfig.DAILY_REPORT_TIME}`
• Controllo offline: ogni `{SchedulerConfig.STALE_CHECK_INTERVAL}` minuti  
• Notifiche recovery: immediate quando dispositivi tornano online

**COMANDI PRINCIPALI:**
• `/status` - Rapporto completo tutti i misuratori
• `/offline` - Solo misuratori offline con dettagli
• `/online` - Solo misuratori online con medie flusso  
• `/list` - Lista completa ID e nomi misuratori
• `/stats [nome]` - Dettagli specifici misuratore
• `/help` - Lista completa comandi

**SISTEMA SEMPRE ATTIVO:**
✅ Monitoraggio automatico 24/7
✅ Notifiche immediate per problemi

Usa `/help` per vedere tutti i comandi disponibili.

"""

            bot.send_message(message.chat.id, welcome_message, parse_mode='Markdown')
            logger.info(f"Messaggio di benvenuto inviato a {username}")
    
    except Exception as e:
        logger.error(f"Errore invio messaggio benvenuto: {e}")

@bot.message_handler(commands=['start', 'help'])
def send_help(message):
    """Mostra i comandi disponibili"""
    help_text = """*HYDRA BOT - Comandi Disponibili*

/status - Rapporto completo misuratori
/offline - Solo misuratori offline  
/online - Solo misuratori online
/stats [nome] - Dettagli misuratore specifico
/time - Data/ora sistema
/chatid - ID di questa chat
/list - Lista di tutti i misuratori nel database
/help - Questo messaggio


*Sistema di monitoraggio Hydra*"""
    
    bot.reply_to(message, help_text, parse_mode='Markdown')

@bot.message_handler(commands=['status'])
def cmd_status(message):
    """Invia rapporto completo immediato"""
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        
        # Recupera dati
        stats_data, error = db_service.fetch_misuratori_stats()
        if error:
            bot.reply_to(message, f"❌ Errore database: {error}")
            return
        
        total_active, count_error = db_service.fetch_active_misuratori_count()
        if count_error:
            total_active = len(stats_data)
        
        # Genera rapporto
        report = telegram_service.format_daily_report(stats_data, total_active)
        telegram_service.bot = bot  # Usa questo bot per l'invio
        telegram_service.chat_id = message.chat.id
        
        success = telegram_service.send_long_message(report)
        if not success:
            bot.reply_to(message, "❌ Errore invio rapporto")
            
    except Exception as e:
        logger.error(f"Errore comando status: {e}")
        bot.reply_to(message, f"❌ Errore: {str(e)}")

@bot.message_handler(commands=['offline'])
def cmd_offline(message):
    """Mostra solo misuratori offline"""
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        
        stats_data, error = db_service.fetch_misuratori_stats()
        if error:
            bot.reply_to(message, f"❌ Errore database: {error}")
            return
        
        # Filtra solo offline
        offline_devices = []
        for row in stats_data:
            id_misuratore, name, location, is_active, total_measurements, first_measurement, last_measurement, avg_24h, avg_7d, avg_30d, updated_at = row
            if not telegram_service._is_recent_24h(last_measurement):
                offline_devices.append(row)
        
        if not offline_devices:
            bot.reply_to(message, "🟢 *Ottimo!*\n\nTutti i misuratori sono online!", parse_mode='Markdown')
            return
        
        # Genera rapporto offline
        report = f"""*MISURATORI OFFLINE ({len(offline_devices)})*
{datetime.now(LOCAL_TZ).strftime('%d/%m/%Y alle %H:%M')}

```
Nome              Ultimo dato      Offline da
────────────────  ───────────────  ──────────"""
        
        for row in offline_devices:
            id_misuratore, name, location, is_active, total_measurements, first_measurement, last_measurement, avg_24h, avg_7d, avg_30d, updated_at = row
            
            display_name = name or id_misuratore
            if len(display_name) > 16:
                display_name = display_name[:13] + "..."
            
            last_str = telegram_service._format_local(last_measurement) if last_measurement else "Mai"
            if last_str != "Mai":
                last_parts = last_str.split(" ")
                if len(last_parts) >= 2:
                    date_part = last_parts[0].split("/")
                    if len(date_part) >= 3:
                        year_short = date_part[2][2:] if len(date_part[2]) == 4 else date_part[2]
                        last_str = f"{date_part[0]}/{date_part[1]}/{year_short} {last_parts[1][:5]}"
            
            days_ago = telegram_service._days_since(last_measurement) if last_measurement else "∞"
            if len(days_ago) > 10:
                days_ago = days_ago[:10]
            
            report += f"\n{display_name:<16}  {last_str:<15}  {days_ago:<10}"
        
        report += "\n```"
        bot.reply_to(message, report, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Errore comando offline: {e}")
        bot.reply_to(message, f"❌ Errore: {str(e)}")

@bot.message_handler(commands=['online'])
def cmd_online(message):
    """Mostra solo misuratori online"""
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        
        stats_data, error = db_service.fetch_misuratori_stats()
        if error:
            bot.reply_to(message, f"❌ Errore database: {error}")
            return
        
        # Filtra solo online
        online_devices = []
        for row in stats_data:
            id_misuratore, name, location, is_active, total_measurements, first_measurement, last_measurement, avg_24h, avg_7d, avg_30d, updated_at = row
            if telegram_service._is_recent_24h(last_measurement):
                online_devices.append(row)
        
        if not online_devices:
            bot.reply_to(message, "🔴 *Attenzione!*\n\nNessun misuratore online al momento.", parse_mode='Markdown')
            return
        
        # Genera rapporto online
        report = f"""*MISURATORI ONLINE ({len(online_devices)})*
{datetime.now(LOCAL_TZ).strftime('%d/%m/%Y alle %H:%M')}

```
Nome              Ultimo dato     24h    7d   
────────────────  ─────────────── ────── ──────"""
        
        for row in online_devices:
            id_misuratore, name, location, is_active, total_measurements, first_measurement, last_measurement, avg_24h, avg_7d, avg_30d, updated_at = row
            
            display_name = name or id_misuratore
            if len(display_name) > 16:
                display_name = display_name[:13] + "..."
            
            last_str = telegram_service._format_local(last_measurement) if last_measurement else "Mai"
            if last_str != "Mai":
                last_parts = last_str.split(" ")
                if len(last_parts) >= 2:
                    date_part = last_parts[0].split("/")
                    if len(date_part) >= 3:
                        year_short = date_part[2][2:] if len(date_part[2]) == 4 else date_part[2]
                        last_str = f"{date_part[0]}/{date_part[1]}/{year_short} {last_parts[1][:5]}"
            
            avg_24h_str = f"{avg_24h:.1f}" if avg_24h is not None else "N/A"
            avg_7d_str = f"{avg_7d:.1f}" if avg_7d is not None else "N/A"
            
            report += f"\n{display_name:<16}  {last_str:<15}  {avg_24h_str:<6} {avg_7d_str:<6}"
        
        report += "\n```"
        bot.reply_to(message, report, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Errore comando online: {e}")
        bot.reply_to(message, f"❌ Errore: {str(e)}")

@bot.message_handler(commands=['stats'])
def cmd_stats(message):
    """Dettagli di un misuratore specifico"""
    try:
        # Estrai nome misuratore dal comando
        command_parts = message.text.split(' ', 1)
        if len(command_parts) < 2:
            bot.reply_to(message, "❓ Utilizzo: `/stats Nome_Misuratore`\n\nEsempio: `/stats Trebisacce`", parse_mode='Markdown')
            return
        
        search_name = command_parts[1].strip().lower()
        bot.send_chat_action(message.chat.id, 'typing')
        
        stats_data, error = db_service.fetch_misuratori_stats()
        if error:
            bot.reply_to(message, f"❌ Errore database: {error}")
            return
        
        # Cerca misuratore
        found_device = None
        for row in stats_data:
            id_misuratore, name, location, is_active, total_measurements, first_measurement, last_measurement, avg_24h, avg_7d, avg_30d, updated_at = row
            device_name = name or id_misuratore
            if search_name in device_name.lower() or search_name in id_misuratore.lower():
                found_device = row
                break
        
        if not found_device:
            bot.reply_to(message, f"❌ Misuratore '{command_parts[1]}' non trovato.\n\nUsa `/online` o `/offline` per vedere i nomi disponibili.")
            return
        
        # Genera dettagli
        id_misuratore, name, location, is_active, total_measurements, first_measurement, last_measurement, avg_24h, avg_7d, avg_30d, updated_at = found_device
        
        status_emoji = "🟢" if telegram_service._is_recent_24h(last_measurement) else "🔴"
        status_text = "Online" if telegram_service._is_recent_24h(last_measurement) else "Offline"
        
        report = f"""*DETTAGLI MISURATORE*

{status_emoji} *{name or id_misuratore}*
```
ID:              {id_misuratore}
Posizione:       {location or 'N/A'}
Status:          {status_text}
Attivo:          {'Sì' if is_active else 'No'}

DATI:
Totale misure:   {total_measurements or 'N/A'}
Prima misura:    {telegram_service._format_local(first_measurement) if first_measurement else 'N/A'}
Ultima misura:   {telegram_service._format_local(last_measurement) if last_measurement else 'N/A'}
Ultimo aggiornam:{telegram_service._format_local(updated_at) if updated_at else 'N/A'}

MEDIE FLUSSO:
24 ore:          {f"{avg_24h:.2f} L/s" if avg_24h is not None else "N/A"}
7 giorni:        {f"{avg_7d:.2f} L/s" if avg_7d is not None else "N/A"}
30 giorni:       {f"{avg_30d:.2f} L/s" if avg_30d is not None else "N/A"}
```"""
        
        bot.reply_to(message, report, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Errore comando stats: {e}")
        bot.reply_to(message, f"❌ Errore: {str(e)}")

@bot.message_handler(commands=['time'])
def cmd_time(message):
    """Mostra data/ora sistema"""
    now = datetime.now(LOCAL_TZ)
    time_info = f"""⏰ *Ora Sistema*

Data/Ora: {now.strftime('%d/%m/%Y alle %H:%M:%S')}
Timezone: Europe/Rome
Timestamp: {int(now.timestamp())}"""
    
    bot.reply_to(message, time_info, parse_mode='Markdown')

@bot.message_handler(commands=['chatid'])
def cmd_chatid(message):
    """Mostra ID di questa chat"""
    chat_info = f"""🆔 *Informazioni Chat*

Chat ID: `{message.chat.id}`
Tipo: {message.chat.type}
Nome: {getattr(message.chat, 'title', getattr(message.chat, 'first_name', 'N/A'))}

Per .env: TELEGRAM_CHAT_ID={message.chat.id}"""
    
    bot.reply_to(message, chat_info, parse_mode='Markdown')
@bot.message_handler(commands=['list'])
def cmd_list(message):
    """comando per restituire la lista di misuratori presenti nel database"""
    try:
        data, error = db_service.fetch_misuratori_list()
        if data is None:
            bot.reply_to(message, f"❌ Errore database: {error}")
            return
        
        # Formato tabellare con allineamento preciso
        response = f"""*LISTA MISURATORI HYDRA*
{datetime.now(LOCAL_TZ).strftime('%d/%m/%Y alle %H:%M')}

```
{"ID":<15} {"Nome Misuratore":<20}
{"─" * 15} {"─" * 20}"""
        
        for row in data:
            id_misuratore, name = row
            display_name = name or "Senza nome"

            # Accorcia nome se troppo lungo
            if len(id_misuratore) > 15:
                id_misuratore = id_misuratore[:7] + "..."

            response += f"\n{id_misuratore:<15} {display_name:<20}"

        response += f"\n```\n\nTotale: {len(data)} misuratori"
        bot.reply_to(message, response, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Errore comando list: {e}")
        bot.reply_to(message, f"❌ Errore: {str(e)}")
    
@bot.message_handler(func=lambda message: True)
def handle_unknown(message):
    """Gestisce messaggi non riconosciuti"""
    bot.reply_to(message, "❓ Comando non riconosciuto.\n\nUsa /help per vedere i comandi disponibili.")


# ============================================================================
# JOB PERIODICI
# ============================================================================

def job_daily_report():
    """Job per rapporto giornaliero"""
    try:
        logger.info("📊 Esecuzione rapporto giornaliero automatico")
        stats_data, error = db_service.fetch_misuratori_stats(limit=1000)
        if stats_data is None:
            logger.error(f"❌ Errore query rapporto giornaliero: {error}")
            telegram_service.send_message(f"❌ *Errore Rapporto Giornaliero*\\n\\n```{error}```")
            return
        
        total_active, _ = db_service.fetch_active_misuratori_count()
        report_message = telegram_service.format_daily_report(stats_data, total_active or len(stats_data))
        
        if telegram_service.send_long_message(report_message):
            logger.info("✅ Rapporto giornaliero inviato")
        else:
            logger.error("❌ Errore invio rapporto giornaliero")
    except Exception as e:
        logger.error(f"❌ Errore job rapporto giornaliero: {e}")
        try:
            telegram_service.send_message(f"❌ *Errore Job Daily Report*\\n\\n```{str(e)}```")
        except:
            pass

def job_check_stale():
    """Job per controllo dispositivi offline"""
    try:
        logger.info("🔍 Controllo dispositivi offline automatico")
        
        # Importo la logica da check_stale.py
        import json
        from pathlib import Path
        
        # Carica stato precedente
        state_file = Path("alert_state.json")
        previously_stale = set()
        if state_file.exists():
            try:
                with open(state_file, 'r') as f:
                    alert_state = json.load(f)
                    previously_stale = set(alert_state.get('stale_devices', []))
            except Exception as e:
                logger.warning(f"Errore lettura stato alert: {e}")
        
        # Query dati attuali
        stats_data, error = db_service.fetch_misuratori_stats(limit=1000)
        if stats_data is None:
            logger.error(f"❌ Errore query controllo stale: {error}")
            return
        
        # Processa dati
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
                # Misuratore recuperato
                recovered_devices.append({
                    'id': id_misuratore,
                    'name': name or id_misuratore,
                    'last': last_measurement,
                    'location': location
                })
        
        # Nuovi dispositivi offline
        newly_stale = currently_stale - previously_stale
        newly_stale_devices = [d for d in stale_devices if d['id'] in newly_stale]
        
        logger.info(f"Stato: {len(currently_stale)} stale, {len(newly_stale)} nuovi, {len(recovered_devices)} recuperati")
        
        # Invia alert per nuovi offline
        if newly_stale_devices:
            logger.info(f"Invio alert per {len(newly_stale_devices)} nuovi misuratori offline")
            alert_message = telegram_service.format_stale_alert(newly_stale_devices)
            telegram_service.send_long_message(alert_message)
        
        # Invia notifiche recovery
        if recovered_devices:
            logger.info(f"Invio notifica recupero per {len(recovered_devices)} misuratori")
            recovery_message = f"""✅ *RECUPERO MISURATORI*

🟢 {len(recovered_devices)} misuratore{'i' if len(recovered_devices) > 1 else ''} tornat{'i' if len(recovered_devices) > 1 else 'o'} online:

"""
            for device in recovered_devices[:10]:
                recovery_message += f"• *{device['name']}* ({device['location']})\n"
            
            if len(recovered_devices) > 10:
                recovery_message += f"• ... e altri {len(recovered_devices) - 10}\n"
            
            recovery_message += f"\n{datetime.now(LOCAL_TZ).strftime('%d/%m/%Y %H:%M')}\n#Hydra #Recupero"
            telegram_service.send_message(recovery_message)
        
        # Salva nuovo stato
        new_alert_state = {
            'stale_devices': list(currently_stale),
            'last_check': datetime.now().isoformat(),
            'total_stale': len(currently_stale),
            'total_active': len(stats_data)
        }
        with open(state_file, 'w') as f:
            json.dump(new_alert_state, f, indent=2)
        
        logger.info(f"Controllo completato: {len(currently_stale)}/{len(stats_data)} misuratori offline")
        
    except Exception as e:
        logger.error(f"❌ Errore job controllo stale: {e}")
        try:
            telegram_service.send_message(f"❌ *Errore Controllo Stale*\\n\\n```{str(e)}```")
        except:
            pass

def run_scheduler():
    """Thread per eseguire job schedulati"""
    logger.info("Avvio scheduler job periodici")
    logger.info(f"Configurazione da variabili d'ambiente:")
    logger.info(f"Rapporto giornaliero: {SchedulerConfig.DAILY_REPORT_TIME}")
    logger.info(f"Controllo offline: ogni {SchedulerConfig.STALE_CHECK_INTERVAL} minuti")
    logger.info(f"Check scheduler: ogni {SchedulerConfig.SCHEDULER_CHECK_INTERVAL} secondi")
    
    # Programma job con configurazioni da .env
    schedule.every().day.at(SchedulerConfig.DAILY_REPORT_TIME).do(job_daily_report)
    schedule.every(SchedulerConfig.STALE_CHECK_INTERVAL).minutes.do(job_check_stale)
    
    # Loop scheduler
    while True:
        try:
            schedule.run_pending()
            time.sleep(SchedulerConfig.SCHEDULER_CHECK_INTERVAL)
        except Exception as e:
            logger.error(f"❌ Errore scheduler: {e}")
            time.sleep(SchedulerConfig.SCHEDULER_CHECK_INTERVAL)

def main():
    """Avvia il bot con job periodici"""
    logger.info("🤖 Avvio Hydra Bot con scheduler integrato...")
    logger.info("📅 Job programmati:")
    logger.info(f"  - Rapporto giornaliero: {SchedulerConfig.DAILY_REPORT_TIME}")
    logger.info(f"  - Controllo offline: ogni {SchedulerConfig.STALE_CHECK_INTERVAL} minuti")
    logger.info("Premi Ctrl+C per fermare il bot")
    
    try:
        # Avvia thread scheduler
        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()
        logger.info("✅ Scheduler avviato")
        
        # Avvia bot (blocking)
        bot.infinity_polling()
    except KeyboardInterrupt:
        logger.info("🛑 Bot e scheduler fermati dall'utente")
    except Exception as e:
        logger.error(f"❌ Errore sistema: {e}")

if __name__ == "__main__":
    main()