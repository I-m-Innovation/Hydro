# 🏗️ Hydra 3.0 - Sistema di Monitoraggio Idrometrico

## Panoramica del Progetto

**Hydra 3.0** è una piattaforma di monitoraggio real-time per misurazioni idrologiche che combina due servizi distinti:

- **🔄 db_manager**: Servizio ETL per processamento dati real-time da Azure EventHub
- **🌐 portale_hydro_3_0**: Dashboard web Django per visualizzazione e analisi

### Funzionalità Principali
- **Pipeline ETL real-time** con processamento statistico avanzato (filtro Hampel)
- **Dashboard web** con grafici interattivi e zoom/pan
- **Analytics avanzate**: curve di durata, istogrammi di flusso, statistiche temporali
- **Monitoraggio stato**: LED status in tempo reale per ogni misuratore
- **Gestione outlier**: rilevamento automatico tramite algoritmi statistici

---

## 🗃️ Architettura Database

![Database Schema](docs/images/Database_Hydro_Diagram.jpeg)

*Schema delle tabelle principali del sistema Hydra 3.0 con relazioni e materialized views*

---

## 🔄 Servizio db_manager (ETL Pipeline)

### Architettura
Come nei manga dovete guardare il diagramma del database da destra verso sinistra per seguire il flusso di dati in entrata.
```
Azure EventHub → tab_measurements_raw → tab_measurements → tab_measurements_clean → Analytics
```

### Componenti Principali

#### 📁 Struttura Directory
```
db_manager/
├── config/
│   └── settings.py          # Configurazione centralizzata
├── db/
│   ├── conn.py              # Gestione connessioni database
│   ├── schema.py            # Setup schema e tabelle
│   └── sql_loader.py        # Caricamento script SQL
├── jobs/                    # Job ETL individuali
│   ├── ingest_eventhub.py   # Ingestion da Azure EventHub
│   ├── transform_raw.py     # Trasformazione dati raw
│   ├── clean_measurements.py # Applicazione filtro Hampel
│   └── refresh_*.py         # Refresh materialized views
├── scripts/                 # Script SQL
│   ├── ensure_*.sql         # Creazione tabelle/MV
│   └── refresh_*.sql        # Refresh logic SQL
└── run.py                   # Orchestratore principale
```

#### 🔧 Pipeline di Processamento

**Stage 1: Ingestion** (`ingest_eventhub.py`)
- Consuma eventi JSON da Azure EventHub
- Rate limiting: 280s tra eventi per device. Più precisamente, un dato arriva ogni 5 minuti. Un piccolo gap di 20 secondi è stato lasciato in modo da evitare collisioni con i dati che arrivano, per appunto, ogni 5 minuti (300s).
- Salvataggio in `hydro.tab_measurements_raw`

**Stage 2: Transform** (`transform_raw.py`)
- Pivot dei dati raw in formato wide. Ogni misurazione è formata da 10 righe per misuratore. Ogni riga rappresenta un dato specifico come la portata o la temperatura. La trasformazione pivot consente di avere una riga per misuratore con tutte le misurazioni come colonne, facilitando l'analisi e la pulizia successiva.
- Checkpoint tracking via `hydro.tab_etl_state`
- Output in `hydro.tab_measurements`

**Stage 3: Data Cleaning** (`clean_measurements.py`)
- **Filtro Hampel** (window=49, σ=3.5) per outlier detection
- Calcolo mediane mobili e soglie statistiche
- Output in `hydro.tab_measurements_clean`

**Stage 4: Analytics** (vari `refresh_*.py`)
- Statistiche temporali (24h, 7d, 30d, 360d, all-time)
- Curve di durata con percentili di superamento
- Istogrammi di distribuzione flusso
- Materialized views per performance

#### ⚙️ Configurazione (`config/settings.py`)
```python
# EventHub
EVENTHUB_CONNECTION_STRING = os.getenv("EVENTHUB_CONNECTION_STRING")
MIN_SECONDS_BETWEEN_EVENTS = 280  # Throttling

# Hampel Filter
HAMPEL_WINDOW_SIZE = 49
HAMPEL_SIGMA_THRESHOLD = 3.5

# Scheduling
SECONDS_BETWEEN_INGEST = 20
SECONDS_BETWEEN_TRANSFORM = 60
SECONDS_BETWEEN_CLEAN_MEASUREMENTS = 300
```

#### 🕐 Orchestrazione (`run.py`)
- **Thread separati** per ogni job ETL
- **Scheduling intelligente**: real-time (20s-5min) + nightly (2-4am)
- **Timezone aware**: Europe/Rome per operazioni notturne
- **Graceful startup**: verifica schema e dependencies

---

## 🌐 Servizio portale_hydro_3_0 (Web Dashboard)

### Architettura Django

#### 📁 Struttura Directory
```
portale_hydro_3_0/
├── portale/                 # App Django principale
│   ├── models.py           # Modelli (unmanaged, puntano al DB del db_manager)
│   ├── views.py            # API endpoints e view logiche
│   ├── urls.py             # URL routing
│   ├── static/portale/
│   │   ├── css/style.css   # Styling + LED status
│   │   └── js/
│   │       ├── charts.js   # Gestione grafici Chart.js (~1400 righe)
│   │       └── led_status.js # Polling status misuratori
│   └── templates/portale/   # Template HTML
├── portale_hydro_3_0/      # Settings Django
└── manage.py
```

#### 🗃️ Modelli Dati (`models.py`)
```python
# Tabelle principali (managed=False - create dal db_manager)
class tab_measurements_clean     # Dati processati con Hampel
class tab_misuratori            # Anagrafica misuratori 
class tab_statistiche_misuratori # Statistiche aggregate
```

#### 🔌 API Endpoints (`views.py`)
```python
/api/measurements/     # Time series dati per grafici
/api/duration-curve/   # Curve di durata (percentili)
/api/flow-histogram/   # Istogrammi distribuzione
/api/led-status/       # Status real-time misuratori
```

#### 📊 Frontend JavaScript (`static/portale/js/`)

**charts.js** - Sistema grafici avanzato:
- **Chart.js** con plugin zoom e decimazione LTTB
- **3 tipologie**: Flow rate, Duration curves, Histograms
- **Gap detection**: interruzione linee + ombreggiatura rossa
- **Performance**: decimazione automatica oltre 1250 punti
- **Real-time**: polling 60s per range 24h
- **UX**: zoom, pan, reset, range buttons (24h→all)

**led_status.js** - Monitoraggio real-time:
- **Polling 60s** su `/api/led-status/`
- **Regole colore**: Verde ≤2h, Arancione >2h, Rosso >6h, Grigio no-data
- **Retry logic** con backoff esponenziale

#### 🔐 Sicurezza
- **Login required** su tutte le view (`@login_required`)
- **Input validation** robusta con whitelist e regex
- **SQL injection protection** via ORM e parametri
- **CSRF protection** Django standard

#### Riattivare il login (se rimosso)
Per ripristinare l'autenticazione:
- Ripristina i decorator `@login_required` nelle view in `portale_hydro_3_0/portale/views.py`.
- Ripristina l'import `from django.contrib.auth.decorators import login_required` nello stesso file.
- Riattiva la route auth in `portale_hydro_3_0/portale_hydro_3_0/urls.py`:
  `path("accounts/", include("django.contrib.auth.urls")),`
- Riattiva `LOGIN_URL` (e facoltativamente `LOGOUT_REDIRECT_URL`) in `portale_hydro_3_0/portale_hydro_3_0/settings.py`.

#### 🎨 User Experience
- **Responsive design** con sidebar navigazione
- **Live status indicators** per ogni misuratore
- **Interactive charts** con tooltip dettagliati  
- **Range selection** adattivo (24h→all con ottimizzazioni)

---

## 🔗 Integrazione tra i Servizi

### Flusso Dati
```
Azure EventHub → db_manager → PostgreSQL → Django ORM → Chart.js → Browser
```

### Sincronizzazione
- **Database condiviso**: Stesso schema PostgreSQL `hydro.*`
- **Modelli unmanaged**: Django non gestisce DDL, solo queries
- **Real-time updates**: Frontend polling + materialized views refresh

### Performance Strategy
- **Materialized views** per range lunghi (6m+) con medie giornaliere
- **Direct queries** per range brevi (24h-1m) con tutti i punti
- **Caching HTTP** (20h) su endpoint statici (curve di durata)
- **Decimazione client-side** con LTTB algorithm

---

## 🚀 Deployment

### Requirements
- **Python 3.11+** con virtual environment
- **PostgreSQL 13+** con schema `hydro`
- **Azure EventHub** connection string
- **Sistema operativo**: Linux/Windows con systemd/services

### Quick Start
```bash
# Setup database service
cd db_manager
pip install -r requirements.txt
python run.py

# Setup web service  
cd portale_hydro_3_0
pip install -r requirements.txt
python manage.py runserver 0.0.0.0:8000
```

### Production Deploy
- **Single machine** recommended per uso interno
- **Nginx reverse proxy** per static files e SSL
- **Systemd services** per auto-restart
- **PostgreSQL locale** (no cluster needed per 3-4 utenti)

---

## ✅ Status del Progetto secondo Claude 4

### Valutazione per Uso Aziendale (3-4 utenti)
**🎯 ECCELLENTE - 9/10** 

**Punti di Forza:**
- Architettura microservizi ben separata e manutenibile
- Processamento statistico scientificamente corretto  
- Frontend moderno con UX patterns solidi
- Over-engineered in modo positivo per robustezza

**Da Completare (5 minuti):**
- [x] Rimuovere credenziali hardcoded in `regenerate_clean_measurements_single.py`
- [x] Configurazione via environment variables

**Opzionali per Uso Interno:**
- Script restart automatico (risolve memory leak con cron)
- Health check endpoints per monitoring

---

## 🔌 Utilità Operative

### Disattivare/Riattivare CI/CD (Azure + GitHub)

**Azure App Service (Deployment Center)**
```bash
# Disattivare: Azure Portal → App Service → Deployment Center → Disconnect
# Riattivare: Azure Portal → App Service → Deployment Center → Connect (GitHub + branch release)
```

**GitHub Actions**
```bash  
# Disattivare: GitHub repo → Actions → Select workflow → Disable workflow
# Riattivare: GitHub repo → Actions → Select workflow → Enable workflow
```

### Network troubleshooting (LAN)
Se il sito funziona sul PC server ma non è raggiungibile da altri PC:
- **Profilo rete**: Imposta come "Privato" in Windows
- **Firewall**: Regola in ingresso TCP port 8000 per profilo Privato
- **Test connettività**: `Test-NetConnection <IP> -Port 8000` dal client
