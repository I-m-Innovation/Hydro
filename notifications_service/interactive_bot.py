"""
Bot Telegram interattivo per comandi manuali
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
import telebot
from datetime import datetime
from services.database_service import DatabaseService
from services.telegram_service import TelegramService
from config.settings import TelegramConfig, LOCAL_TZ

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

@bot.message_handler(func=lambda message: True)
def handle_unknown(message):
    """Gestisce messaggi non riconosciuti"""
    bot.reply_to(message, "❓ Comando non riconosciuto.\n\nUsa /help per vedere i comandi disponibili.")

def main():
    """Avvia il bot interattivo"""
    logger.info("🤖 Avvio bot interattivo Hydra...")
    logger.info("Premi Ctrl+C per fermare il bot")
    
    try:
        bot.infinity_polling()
    except KeyboardInterrupt:
        logger.info("🛑 Bot fermato dall'utente")
    except Exception as e:
        logger.error(f"❌ Errore bot: {e}")

if __name__ == "__main__":
    main()