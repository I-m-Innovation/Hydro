"""
Servizio per l'invio di notifiche via Telegram
"""
import telebot
import logging
import time
from datetime import datetime, timezone
from typing import List, Optional
from config.settings import TelegramConfig, LOCAL_TZ

logger = logging.getLogger(__name__)

class TelegramService:
    def __init__(self):
        TelegramConfig.validate()
        self.bot = telebot.TeleBot(TelegramConfig.BOT_TOKEN)
        self.chat_id = TelegramConfig.CHAT_ID
        self.max_message_length = 3500
    
    def send_message(self, text: str, parse_mode: str = 'Markdown') -> bool:
        """
        Invia un messaggio Telegram con retry automatico
        """
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.bot.send_message(
                    chat_id=self.chat_id,
                    text=text,
                    parse_mode=parse_mode
                )
                logger.info("Messaggio Telegram inviato con successo")
                return True
            except Exception as e:
                logger.warning(f"Tentativo {attempt + 1} fallito: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Backoff esponenziale
                else:
                    logger.error(f"Impossibile inviare messaggio dopo {max_retries} tentativi: {e}")
        return False
    
    def send_long_message(self, text: str, parse_mode: str = 'Markdown'):
        """
        Invia messaggi lunghi dividendoli in chunk
        """
        if len(text) <= self.max_message_length:
            return self.send_message(text, parse_mode)
        
        # Dividi il messaggio in chunk
        chunks = []
        current_chunk = ""
        
        for line in text.split('\\n'):
            if len(current_chunk) + len(line) + 1 <= self.max_message_length:
                current_chunk += line + '\\n'
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = line + '\\n'
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        # Invia ogni chunk
        success = True
        for i, chunk in enumerate(chunks):
            if i > 0:
                time.sleep(1)  # Pausa tra messaggi per evitare rate limiting
            if not self.send_message(chunk, parse_mode):
                success = False
        
        return success
    
    def format_daily_report(self, stats_data: List, total_active: int) -> str:
        """
        Formatta il rapporto giornaliero semplificato
        """
        now = datetime.now(LOCAL_TZ)
        
        # Conta misuratori OK vs problematici
        ok_count = 0
        stale_count = 0
        total_count = len(stats_data)  # Numero reale di misuratori
        
        for row in stats_data:
            id_misuratore, name, location, is_active, total_measurements, first_measurement, last_measurement, avg_24h, avg_7d, avg_30d, updated_at = row
            
            if self._is_recent_24h(last_measurement):
                ok_count += 1
            else:
                stale_count += 1
        
        # Header semplificato con newline corretti
        header = f"""*RAPPORTO GIORNALIERO HYDRA*
{now.strftime('%d/%m/%Y alle %H:%M')}

*RIEPILOGO:*
🟢 Online: {ok_count}/{total_count}
🔴 Offline: {stale_count}/{total_count}

*STATO TUTTI I MISURATORI:*
```
St Nome              Ultimo dato     24h    7d   
── ──────────────── ─────────────── ────── ──────"""
        
        # Lista di tutti i misuratori con il loro stato in formato tabellare
        for row in stats_data:
            id_misuratore, name, location, is_active, total_measurements, first_measurement, last_measurement, avg_24h, avg_7d, avg_30d, updated_at = row
            
            # Determina stato
            status_emoji = "🟢" if self._is_recent_24h(last_measurement) else "🔴"
            display_name = name or id_misuratore
            
            # Accorcia nome se troppo lungo
            if len(display_name) > 17:
                display_name = display_name[:14] + "..."
            
            # Formatta ultimo dato più corto
            last_str = self._format_local(last_measurement) if last_measurement else "Mai ricevuto"
            if last_str != "Mai ricevuto":
                # Formato più corto: giorno/mese/anno
                last_parts = last_str.split(" ")
                if len(last_parts) >= 2:
                    date_part = last_parts[0].split("/")
                    if len(date_part) >= 3:
                        # Formato: gg/mm/yy hh:mm
                        year_short = date_part[2][2:] if len(date_part[2]) == 4 else date_part[2]
                        last_str = f"{date_part[0]}/{date_part[1]}/{year_short} {last_parts[1][:5]}"
            else:
                last_str = "Mai"
            
            # Formatta le medie più corte
            avg_24h_str = f"{avg_24h:.1f}" if avg_24h is not None else "N/A"
            avg_7d_str = f"{avg_7d:.1f}" if avg_7d is not None else "N/A"
            
            # Allineamento delle colonne
            header += f"\n{status_emoji} {display_name:<17} {last_str:<15} {avg_24h_str:<6} {avg_7d_str:<6}"
        
        header += "\n```"
        
        # Footer semplice
        header += f"\n\n#Hydra"
        
        return header
    
    def format_stale_alert(self, stale_devices: List) -> str:
        """
        Formatta un alert per dispositivi stale in formato tabellare
        """
        if not stale_devices:
            return ""
        
        now = datetime.now(LOCAL_TZ)
        
        if len(stale_devices) == 1:
            device = stale_devices[0]
            days_ago = self._days_since(device['last']) if device['last'] else "∞"
            last_str = self._format_local(device['last']) if device['last'] else "Mai ricevuto"
            location_info = f" - {device['location']}" if device['location'] else ""
            
            return f"""*ALERT HYDRA - MISURATORE OFFLINE*
{now.strftime('%d/%m/%Y alle %H:%M')}

🔴 *{device['name']}*{location_info}
Ultimo dato: {last_str}
Offline da: {days_ago}

#Alert #Hydra"""
        else:
            # Alert multipli in formato tabellare
            header = f"""*ALERT HYDRA - {len(stale_devices)} MISURATORI OFFLINE*
{now.strftime('%d/%m/%Y alle %H:%M')}

```
Nome              Ultimo dato      Offline da
────────────────  ───────────────  ──────────"""
            
            for device in stale_devices:
                display_name = device['name'] or device['id']
                
                # Accorcia nome se troppo lungo
                if len(display_name) > 16:
                    display_name = display_name[:13] + "..."
                
                # Formatta ultimo dato
                last_str = self._format_local(device['last']) if device['last'] else "Mai ricevuto"
                if last_str != "Mai ricevuto":
                    # Formato compatto: gg/mm/yy hh:mm
                    last_parts = last_str.split(" ")
                    if len(last_parts) >= 2:
                        date_part = last_parts[0].split("/")
                        if len(date_part) >= 3:
                            year_short = date_part[2][2:] if len(date_part[2]) == 4 else date_part[2]
                            last_str = f"{date_part[0]}/{date_part[1]}/{year_short} {last_parts[1][:5]}"
                else:
                    last_str = "Mai"
                
                # Giorni offline
                days_ago = self._days_since(device['last']) if device['last'] else "∞"
                
                # Accorcia se troppo lungo
                if len(days_ago) > 10:
                    days_ago = days_ago[:10]
                
                header += f"\n{display_name:<16}  {last_str:<15}  {days_ago:<10}"
            
            header += f"\n```\n\n#Alert #Hydra #Multiplo"
            return header
    
    def _is_recent_24h(self, dt) -> bool:
        """Verifica se un datetime è nelle ultime 24 ore"""
        if dt is None:
            return False
        
        dt_obj = self._to_datetime(dt)
        now_utc = datetime.now(timezone.utc)
        hours_diff = (now_utc - dt_obj.astimezone(timezone.utc)).total_seconds() / 3600
        return hours_diff <= TelegramConfig.STALE_THRESHOLD_HOURS
    
    def _to_datetime(self, dt):
        """Converte string/datetime in datetime con timezone"""
        if isinstance(dt, str):
            s = dt.strip()
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    
    def _format_local(self, dt) -> str:
        """Formatta datetime in timezone locale"""
        if dt is None:
            return "-"
        dt_obj = self._to_datetime(dt)
        return dt_obj.astimezone(LOCAL_TZ).strftime("%d/%m/%Y %H:%M")
    
    def _days_since(self, dt) -> str:
        """Calcola giorni trascorsi da un datetime"""
        if dt is None:
            return "∞"
        
        dt_obj = self._to_datetime(dt)
        now = datetime.now(timezone.utc)
        diff = now - dt_obj.astimezone(timezone.utc)
        
        days = diff.days
        hours = diff.seconds // 3600
        
        if days > 0:
            return f"{days}g {hours}h "
        elif hours > 0:
            return f"{hours}h "
        else:
            return "< 1h "