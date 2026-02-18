"""
Script di test per verificare il funzionamento del servizio notifiche
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import logging
from services.database_service import DatabaseService
from services.telegram_service import TelegramService

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_database_connection():
    """Test connessione database"""
    print("🔍 Test connessione database...")
    db_service = DatabaseService()
    
    stats, error = db_service.fetch_misuratori_stats(limit=5)
    if error:
        print(f"❌ Errore database: {error}")
        return False
    
    print(f"✅ Database OK - Recuperati {len(stats)} record")
    return True

def test_telegram_service():
    """Test servizio Telegram"""
    print("🔍 Test servizio Telegram...")
    
    try:
        telegram_service = TelegramService()
        test_message = "🧪 *Test Servizio Notifiche*\\n\\nQuesto è un messaggio di test dal servizio notifiche Hydra.\\n\\n#Test"
        
        success = telegram_service.send_message(test_message)
        if success:
            print("✅ Telegram OK - Messaggio test inviato")
            return True
        else:
            print("❌ Errore invio messaggio Telegram")
            return False
    except Exception as e:
        print(f"❌ Errore servizio Telegram: {e}")
        return False

def test_daily_report():
    """Test generazione rapporto giornaliero"""
    print("🔍 Test rapporto giornaliero...")
    
    try:
        db_service = DatabaseService()
        telegram_service = TelegramService()
        
        stats, error = db_service.fetch_misuratori_stats(limit=100)
        if error:
            print(f"❌ Errore recupero dati: {error}")
            return False
        
        total_active, count_error = db_service.fetch_active_misuratori_count()
        if count_error:
            total_active = len(stats)
        
        report = telegram_service.format_daily_report(stats, total_active)
        print("📄 Anteprima rapporto:")
        print("-" * 50)
        print(report[:500] + "..." if len(report) > 500 else report)
        print("-" * 50)
        print("✅ Rapporto generato correttamente")
        return True
        
    except Exception as e:
        print(f"❌ Errore generazione rapporto: {e}")
        return False

def main():
    """Esegue tutti i test"""
    print("=" * 60)
    print("🧪 TEST SERVIZIO NOTIFICHE HYDRA")
    print("=" * 60)
    
    tests = [
        ("Database", test_database_connection),
        ("Telegram", test_telegram_service), 
        ("Rapporto", test_daily_report)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
            print()
        except Exception as e:
            print(f"❌ Errore critico nel test {test_name}: {e}")
            results.append((test_name, False))
            print()
    
    # Riepilogo
    print("=" * 60)
    print("📊 RIEPILOGO TEST:")
    all_passed = True
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {test_name:<15} {status}")
        if not success:
            all_passed = False
    
    print("=" * 60)
    if all_passed:
        print("🎉 TUTTI I TEST SONO PASSATI!")
        print("Il servizio notifiche è pronto per l'uso.")
    else:
        print("⚠️  ALCUNI TEST SONO FALLITI!")
        print("Controlla i log sopra per i dettagli degli errori.")
    print("=" * 60)

if __name__ == "__main__":
    main()