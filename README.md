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

## Possible Future Implementation: Safe Full Regeneration of `tab_measurements_clean`

This section documents a possible future design for the weekly full regeneration of `hydro.tab_measurements_clean`. It is not implemented yet, but it captures the current reasoning and the constraints to preserve.

### Goal
- Rebuild the full cleaned dataset without ever leaving the live table in a partially regenerated state.
- Keep the operational impact on the live database as low as possible.
- Avoid replacing a healthy live table with a broken or incomplete regenerated dataset.

### Proposed High-Level Workflow
1. The weekly scheduler reaches the configured execution time.
2. Pause the incremental cleaner with `clean_pause_event`.
3. Acquire `clean_run_lock` with a timeout.
4. If the lock cannot be acquired in time:
   - log the failure clearly
   - clear the pause event
   - retry with a bounded retry policy
   - do not wait forever
5. Once the lock is acquired, begin the regeneration flow.
6. `TRUNCATE` the staging table only.
7. Rebuild the full regenerated dataset into the staging table.
8. Run validation checks on staging.
9. Only if validation passes, publish staging into `hydro.tab_measurements_clean` in one short final transaction.
10. Release the lock and clear the pause event.

### Why Use a Staging Table
- The expensive recomputation happens outside the live table.
- The live table remains stable and readable while regeneration runs.
- The final publish step can be short and atomic.
- If the regeneration fails before publication, the live table remains untouched.

### Important Rule About `TRUNCATE`
At the beginning of the job, `TRUNCATE` should be applied to the staging table, not to `hydro.tab_measurements_clean`.

If the live table were truncated before validation and the job failed halfway through, the system could end up with an empty or partially rebuilt production table. By truncating only the staging table first, the process starts from a clean workspace without risking the current live dataset.

### Suggested Validation Before Publish
Before replacing the live table, the staging table should pass a set of checks.

Hard checks:
- staging row count must be greater than zero
- key columns must not be null
- there must be no duplicate logical keys such as `(id_misuratore, data_misurazione)`
- device coverage must match the expected dataset
- the min/max timestamp range must look plausible

Coverage checks against the live table:
- rows present in live but missing in staging must be treated as a failure by default
- rows present in staging but not in live may be acceptable only if they are explainable by valid source coverage

Practical rule:
- if staging is missing any logical row currently present in the live table, abort publication

This is stronger and safer than checking only total row counts.

### What to Do If Staging Has Fewer Rows Than Live
If the weekly job is intended to fully rebuild `tab_measurements_clean`, then a staging table with fewer rows than the live table should be treated as suspicious by default.

In that case:
- do not publish
- keep the live table unchanged
- inspect why those rows are missing

Only explicit business rules should allow publication with fewer rows, for example a known deduplication rule or an intentional source-data correction.

### Suggested Publish Sequence
If validation passes, the publish step should be short and atomic:
1. begin transaction
2. `TRUNCATE hydro.tab_measurements_clean`
3. `INSERT INTO hydro.tab_measurements_clean (...) SELECT ... FROM staging`
4. commit

This ensures that the live table moves from the old complete version to the new complete version in a single publish step, instead of exposing a device-by-device mixed state.

### Notes on Locking and Operational Impact
- Using a staging table reduces the amount of time the live table is being modified.
- It does not remove the need for `clean_run_lock`.
- It shortens the lock-sensitive publication window.
- A timeout on `clean_run_lock.acquire()` is still recommended to avoid indefinite blocking.

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

---

## 🤖 Servizio notifications_service (Sistema Notifiche Telegram)

### Panoramica
**notifications_service** è un servizio autonomo per il monitoraggio e alerting automatico tramite Telegram Bot. Opera indipendentemente dal portale web e dal db_manager, garantendo continuità delle notifiche anche in caso di malfunzionamenti degli altri servizi.

### Architettura
```
notifications_service/
├── config/
│   └── settings.py              # Configurazioni DB, Telegram, timezone
├── services/
│   ├── database_service.py      # Connessione PostgreSQL e query
│   └── telegram_service.py      # Gestione messaggi e formattazione
├── jobs/                        # Script per esecuzione manuale
│   ├── daily_report.py          # Rapporto completo misuratori
│   └── check_stale.py           # Controllo dispositivi offline
├── interactive_bot.py           # Bot interattivo con comandi
└── test_service.py              # Suite di test completa
```

### Tecnologie Utilizzate
- **Python 3.14+** con virtual environment
- **pyTelegramBotAPI** per interazione con Telegram Bot API
- **psycopg2** per connessione diretta a PostgreSQL
- **python-dotenv** per gestione variabili d'ambiente
- **schedule** per job periodici automatici

### Workflow del Sistema

#### 🚀 Sistema Integrato (RACCOMANDATO)
```bash
python interactive_bot.py
```
**Servizio unificato** che combina:
- **Job automatici**: Rapporti giornalieri e controlli offline schedulati
- **Bot interattivo**: Comandi on-demand per consulti immediati
- **Configurazione unificata**: Timing configurabile via variabili d'ambiente

**Job automatici integrati:**
- **Rapporto giornaliero**: Alle ore configurate (default: 08:30)
- **Controllo offline**: Ogni X minuti configurabili (default: 30 min)
- **Notifiche recovery**: Immediate quando dispositivi tornano online
- **Sistema anti-spam**: Alert solo per nuovi problemi, stato salvato in `alert_state.json`

#### ⚙️ Configurazione Scheduler
Variabili opzionali in `.env`:
```env
SCHEDULER_DAILY_REPORT_TIME=08:30        # Orario rapporto giornaliero (HH:MM)
SCHEDULER_STALE_CHECK_MINUTES=30         # Intervallo controllo offline (minuti)
SCHEDULER_CHECK_SECONDS=60               # Frequenza controllo scheduler (secondi)
```

#### 🔧 Esecuzione Manuale (ALTERNATIVA)
Per test o esecuzioni singole:

1. **Rapporto Completo**:
   ```bash
   python jobs/daily_report.py
   ```

2. **Controllo Dispositivi Offline**:
   ```bash
   python jobs/check_stale.py
   ```

#### 🤖 Solo Bot Interattivo
Per avere solo comandi senza job automatici, modificare `interactive_bot.py` commentando la sezione scheduler.
```bash
python interactive_bot.py
```
Bot attivo che risponde a comandi immediati per consulti on-demand.

### Comandi Bot Disponibili

| Comando | Descrizione |
|---------|-------------|
| `/status` | Rapporto completo di tutti i misuratori (equivalente al rapporto giornaliero) |
| `/offline` | Lista solo misuratori offline con dettagli ultima connessione |
| `/online` | Lista solo misuratori online con medie flusso |
| `/list` | Lista completa di tutti i misuratori nel database (ID + Nome) |
| `/stats [nome]` | Dettagli completi di un misuratore specifico |
| `/time` | Data/ora corrente del sistema |
| `/chatid` | ID della chat corrente (utile per configurazione) |
| `/help` | Lista di tutti i comandi disponibili |

### Configurazione Timing e Soglie

#### ⚠️ Soglie Timeout
- **Soglia dispositivi offline**: `.env` → `TELEGRAM_STALE_THRESHOLD_HOURS=24`
- **Timezone**: `config/settings.py` → `LOCAL_TZ = ZoneInfo("Europe/Rome")`

#### 📧 Configurazione Telegram
Variabili richieste in `.env`:
```env
TOKEN_TELEGRAM_BOT=your_bot_token_here
TELEGRAM_CHAT_ID=-1234567890
TELEGRAM_STALE_THRESHOLD_HOURS=24
```

### Utilizzo e Testing

#### 🚀 Avvio Produzione
```bash
cd notifications_service
python interactive_bot.py
```
**Sistema completo attivo con:**
- Job automatici schedulati
- Bot interattivo per comandi on-demand
- Logging completo su console e file

#### 🧪 Test Completo del Sistema
```bash
cd notifications_service
python test_service.py
```

#### 📊 Esecuzione Manuale Job (per test)
```bash
# Rapporto completo stato misuratori (singolo)
python jobs/daily_report.py

# Controllo dispositivi offline (singolo)
python jobs/check_stale.py
```

#### 🤖 Avvio Sistema Completo (RACCOMANDATO)
```bash
# Sistema integrato: Bot + Job automatici
python interactive_bot.py
```
All'avvio vedrai:
- ✅ Scheduler avviato con job programmati
- 📅 Timing configurato (rapporto giornaliero + controlli offline)
- 🤖 Bot attivo per comandi immediati
- Log dettagliato di tutte le operazioni
# Bot attivo per comandi on-demand
python interactive_bot.py
```

### Monitoring e Log

#### 🔍 Log Sistema Integrato
- **Console log**: Output real-time di tutte le operazioni
- **Scheduler log**: Job automatici con timing e risultati
- **Bot log**: Comandi utente e risposte del bot
- **Error log**: Errori dettagliati con stack trace

#### 📁 File di Stato
- **Stato alert**: `alert_state.json` - Dispositivi offline tracciati per anti-spam
- **Log rapporti manuali**: `daily_report.log` - Solo per esecuzioni singole
- **Log controlli manuali**: `stale_check.log` - Solo per esecuzioni singole

#### 🧪 Diagnostica
```bash
# Test completo connettività e funzionalità
python test_service.py

# Verifica configurazione
python -c "from config.settings import *; print('Config OK')"
```

#### 📊 Esempio Output Sistema Integrato
```
🤖 Avvio Hydra Bot con scheduler integrato...
📅 Job programmati:
  - Rapporto giornaliero: 08:30
  - Controllo offline: ogni 30 minuti
✅ Scheduler avviato
🔍 Controllo dispositivi offline automatico
📊 Esecuzione rapporto giornaliero automatico
```

### Resilienza e Affidabilità
- **Servizio autonomo**: Funziona indipendentemente da portale web e db_manager
- **Sistema anti-spam**: Evita notifiche ripetitive per stessi problemi
- **Retry automatico**: Gestione errori di rete Telegram con backoff
- **Chunking messaggi**: Supporto messaggi lunghi con divisione automatica
- **Gestione errori**: Alert automatici per problemi di sistema via Telegram
- **Esecuzione on-demand**: Job eseguibili manualmente per testing e verifica

---

---

## Pelton Turbine Data & Yield Curves (data_pelton_yield)

This section documents the JSON structure used to configure Pelton datasets. If you switch to JSON, use this schema.

```json
{
  "DBCAN": {
    "name": "Canaletta",
    "path": "csv_all\\raw\\DBCAN.csv",
    "path_filtered": "csv_all\\h_fixed\\DBCAN_filtered_H_fixed.csv",
    "head": 117,
    "flow": [],
    "yield": []
  },
  "DBPAR": {
    "name": "Partitore",
    "path": "csv_all\\raw\\DBPAR.csv",
    "path_filtered": "csv_all\\h_fixed\\DBPAR_filtered_H_fixed.csv",
    "head": 346.24,
    "flow": [],
    "yield": []
  },
  "DBST": {
    "name": "San Teodoro",
    "path": "csv_all\\raw\\DBST.csv",
    "path_filtered": "csv_all\\h_fixed\\DBST_filtered_H_fixed.csv",
    "head": 347.24,
    "flow": [],
    "yield": []
  }
}
```

Field meanings:
- `DBCAN`, `DBPAR`, `DBST`: plant identifiers. Each key maps to a plant configuration object.
- `name`: human-readable plant name.
- `path`: relative path to the raw input CSV for that plant.
- `path_filtered`: legacy output path for H_fixed processing (currently not used in the H_calculated flow).
- `head`: fixed head value in meters (historical reference; H_calculated uses pressure instead).
- `flow`: reserved list for flow values (currently unused).
- `yield`: reserved list for efficiency values (currently unused).

---

## Curva di Rendimento: Problema Reale e Funzione di Fit

### Problema che stiamo risolvendo
I dati reali di rendimento (η) in funzione della portata (Q) sono rumorosi e non seguono una forma perfettamente simmetrica:
- a basse portate la curva cresce rapidamente
- vicino al picco si stabilizza
- a portate alte scende piu lentamente

Per il portale serve una **funzione continua e stabile** che approssimi i dati reali e permetta:
- simulazioni rapide (dato Q, ottengo η)
- confronti tra impianti
- grafici puliti e interpretabili

### Funzione originale (simmetrica)
```
?(x) = ?_max * (1 - a (x - 1)^2)
```
dove:
- `x = Q / Q_max`
- `?_max` = rendimento massimo
- `a` = coefficiente di curvatura

Questa formula e' semplice ma troppo rigida: impone simmetria e tende a partire da valori troppo alti.

### Funzione aggiornata (asimmetrica, picco a x=1)
Per seguire meglio i dati reali, usiamo una versione **asimmetrica** a sinistra/destra del picco:
```
Left (x<=1):
? = ?0 + (?_max - ?0) * (1 - aL * |x - 1|^kL)

Right (x>1):
? = ?0 + (?_max - ?0) * (1 - aR * |x - 1|^kR)
```

Interpretazione dei parametri:
- `?0`: rendimento di base (stimato dal 5? percentile)
- `?_max`: media del top 5% dei rendimenti (robusta al rumore)
- `Q_max`: portata corrispondente al picco di rendimento osservato
- `aL`, `aR`: curvatura a sinistra e destra del picco
- `kL`, `kR`: esponenti che controllano quanto rapidamente la curva scende

### Funzione aggiornata (asimmetrica, x normalizzato 0..1 con picco interno)
Per avere un asse x normalizzato tra 0 e 1, usiamo:
```
x = (Q - Q_min) / (Q_max - Q_min)
```
Il picco non e' in x=1, ma in un valore interno `x0`:
```
x0 = argmax(?) nella scala normalizzata
```
La formula diventa:
```
Left (x<=x0):
eta = eta_0 + (eta_max - eta_0) * (1 - aL * |x - x0|^kL)

Right (x>x0):
eta = eta_0 + (eta_max - eta_0) * (1 - aR * |x - x0|^kR)
```

Questa versione permette:
- range 0..1 sull'asse x
- picco nella posizione reale dei dati
- confronto diretto tra impianti con scale normalizzate

### Calcolo dettagliato delle curve di fit

**Dati in ingresso**
- Si usa la curva media: `Portata_bin` (Q) e `Rendimento_mean` (?) dal CSV `rendimento_medio_per_turbine_pelton.csv`.
- Vengono esclusi gli outlier (`Rendimento_mean_is_outlier == True`) e i valori non fisici (? < 0 o ? > 1).

**Normalizzazione dell'asse x (0..1)**
```
Q_min = min(Q)
Q_max = max(Q)
x = (Q - Q_min) / (Q_max - Q_min)
x0 = argmax(?) nella scala normalizzata
```

**Stima di ?_max e ?0**
- `?_max` = media del **top 5%** dei rendimenti (piu' robusto del max assoluto)
- `?0` = **5? percentile** dei rendimenti (base della curva)

**Curva simmetrica**
Si impone una forma simmetrica attorno al picco `x0`:
```
? = ?0 + (?_max - ?0) * (1 - a (x - x0)^2)
```
Il coefficiente `a` si calcola con una formula chiusa:
```
z = (x - x0)
b = ? [ z^2 * (?_max - ?) ] / ? [ z^4 ]
a = b / (?_max - ?0)
```

**Curva asimmetrica (sinistra/destra)**
La versione asimmetrica permette due curvature diverse:
```
Left (x<=x0):
? = ?0 + (?_max - ?0) * (1 - aL * |x - x0|^kL)

Right (x>x0):
? = ?0 + (?_max - ?0) * (1 - aR * |x - x0|^kR)
```
I parametri `kL`, `kR` vengono scelti con una **grid search** nel range [2..7] con step 0.25.
Per ogni coppia (kL, kR) si calcolano `aL` e `aR` con formula chiusa:
```
zL = |x - x0|^kL   (solo x<=x0)
zR = |x - x0|^kR   (solo x>x0)

bL = ? [ zL * (?_max - ?) ] / ? [ zL^2 ]
bR = ? [ zR * (?_max - ?) ] / ? [ zR^2 ]

aL = bL / (?_max - ?0)
aR = bR / (?_max - ?0)
```
La coppia (kL, kR) che minimizza l'errore quadratico totale viene selezionata.

---

## Flusso Dati Rendimento/Potenza (Portale)

Questa sezione descrive come le varie parti (frontend, backend, DB) interagiscono per mostrare rendimento e potenza nel portale.

### 1) Frontend
- La pagina del misuratore carica `charts.js` e `rendimento.js`.
- `rendimento.js` legge `id_misuratore` dal canvas (attributo `data-misuratore`).
- Fa una chiamata HTTP:
  ```
  /portale/api/rendimento-potenza/?id_misuratore=...
  ```

### 2) Backend (Django)
- `urls.py` mappa l'endpoint su `rendimento_potenza_api`.
- La view:
  - valida `id_misuratore`
  - calcola **media portata ultimi 30 min**
  - legge **parametri di fit** della turbina
  - calcola `η` e `P`
  - ritorna JSON con valori numerici

Esempio risposta:
```
{
  "flow_ls_avg_30m": 12.3,
  "eta": 0.74,
  "power_kw": 26.6,
  "head_m": 183,
  "x": 0.31
}
```

### 3) Database
Il backend legge da:
- `tab_measurements_clean` (portata ultimi 30 min)
- `tab_misuratori` (nome impianto)
- `tab_impianti`, `tab_turbine`, `tab_turbina_parametri` (parametri fit)

### 4) Frontend aggiorna UI
- `rendimento.js` aggiorna i campi della tabella:
  - Rendimento medio 30 min
  - Potenza attesa 30 min
  - Salto H (default DB, modificabile)
- Se l'utente cambia H, la potenza viene ricalcolata lato client.

### Perche serve nel portale
Con questa funzione l'utente puo:
- inserire una portata Q e ottenere un rendimento stimato
- calcolare la potenza attesa (P = ρ * g * H * Q * η)
- confrontare curve di impianti diversi con una logica coerente


---

## Linea Potenza Attesa nei Grafici (flow chart)

Questa nota documenta la logica attuale della serie `Potenza attesa (kW)` mostrata nel grafico di portata.

### Dove viene calcolata
- Backend: `portale_hydro_3_0/portale/views.py` dentro `measurements_api`.
- Frontend: `portale_hydro_3_0/portale/static/portale/js/charts.js` come dataset `expected_power_kw` su asse destro (`yPower`).

### Range supportati
- La serie viene calcolata/mostrata per tutti i range disponibili:
  - `24h`
  - `7d`
  - `1m`
  - `6m`
  - `1y`
  - `all`

### Formula usata
- `P[kW] = rho * g * Q[m3/s] * H[m] * eta / 1000`
- con:
  - `rho = 1000 kg/m3`
  - `g = 9.81 m/s2`
  - `Q = flow_ls / 1000`
  - `flow_ls = COALESCE(flow_ls_smoothed, flow_ls_raw)`
- `eta(Q)` e ottenuta con interpolazione lineare sui punti `(q_ls, eta)` di `hydro.tab_turbina_curve_points` con clamp ai bordi.

### Nessun hard-code del salto H
- `H` non ha default hard-coded.
- Viene letto da configurazione turbina (`salto_netto_m`, fallback `salto_nominale_m`).
- Se `H` manca o non e valido, la serie viene disabilitata (valori `null`).

### Perche su alcuni misuratori non si vede la linea
La linea non appare quando manca almeno uno di questi prerequisiti:
1. mapping `id_misuratore -> impianto -> turbina`
2. `head_m` valido (`> 0`)
3. punti curva presenti in `tab_turbina_curve_points` per la turbina risolta

In questi casi il backend risponde comunque con `expected_power_kw`, ma con valori `null` (linea non visibile).

### Nota legenda
- La voce in legenda puo comparire anche quando la linea non e disegnata.
- Motivo: il dataset e definito nel grafico, ma puo risultare senza punti quando il backend restituisce `expected_power_kw` con valori `null` (tipicamente per configurazione mancante/non valida).

---

## Bottone Info Avanzato (Popover HTML + KaTeX)

Questa sezione descrive il nuovo bottone `i+` nel grafico portata, usato per mostrare informazioni combinate (range lunghi + potenza attesa) con formattazione ricca e formula matematica renderizzata.

### Perche non usare solo `data-tooltip`
Il tooltip CSS classico (`.chart-info::after` con `data-tooltip`) e rapido ma limitato:
- testo piatto
- layout poco leggibile per contenuti lunghi
- nessun supporto reale per formule matematiche

Per questo, il bottone `i+` usa un popover HTML dedicato.

### File coinvolti
- Template: `portale_hydro_3_0/portale/templates/portale/includes/misuratore_panel.html`
- Stili: `portale_hydro_3_0/portale/static/portale/css/style.css`
- Logica JS: `portale_hydro_3_0/portale/static/portale/js/chart_info_popover.js`

### Strumenti usati
- **HTML**: struttura del bottone e del popover
- **CSS**: styling del popover (tipografia, spaziature, box, colori)
- **JavaScript vanilla**: apertura/chiusura/posizionamento
- **KaTeX** (CDN): rendering formula `P = \rho \cdot g \cdot Q \cdot H \cdot \eta(Q)`

Include caricati nel template:
- `katex.min.css`
- `katex.min.js` (defer)

### Come funziona (flusso)
1. Il bottone `i+` ha attributo `data-popover-target="expected-power-popover"`.
2. Esiste un contenitore HTML nascosto con `id="expected-power-popover"` e classe `chart-popover is-hidden`.
3. A `DOMContentLoaded`, `chart_info_popover.js`:
   - trova i trigger con `[data-popover-target]`
   - associa trigger e popover
   - renderizza eventuali nodi con `data-katex="..."`
4. Al click del trigger:
   - chiude eventuali popover aperti
   - apre il popover target
   - lo posiziona vicino al bottone (con limiti viewport)
5. Il popover si chiude con:
   - click esterno
   - tasto `Escape`
   - resize finestra
   - scroll

### Accessibilita e UX
- `aria-label` su trigger e popover
- chiusura da tastiera (`Esc`)
- contenuto strutturato con titolo, sezioni, lista e formula
- miglior leggibilita rispetto al tooltip testuale standard

### Nota implementativa
Per il bottone `i` e disattivato il vecchio pseudo-tooltip CSS:
- classe `chart-info-rich`
- regola: `.chart-info.chart-info-rich::after { display: none; }`












# Come inserire dati di log raw 

E' molto probabile che in futuro ci si trovi nella situazione di inserire dati in formato di log all'interno del database e per fare ciò ci sarà bisogno di usare uno script di creazione di un file csv con i dati dei log da importare in una tabella di staging del database per poi essere inseriti nella tabella finale. 

Tale script e codice si trovano al momento solo nel mio pc (Luca) e non sono stati ancora inseriti nel repository. La sequenza di passaggi utili ad inserire i dati viene descritta di seguito ed è presa dal readme presente nella repository dello script stesso.

## Inserimento dati di log raw

Quando stefano ti da lo zip con i dati per i salti di merone, devi estrarre i file `print.txt` ed referenziarli all'interno 
del file `Script_for_missing_datas.py` nella variabile `MISURATORI` (sostituendo i path esistenti che sono riferiti a file non più presenti).

una volta fatto cio, ti basterà avviare lo script con il comando 
```bash
python Script_for_missing_datas.py
```
che si occuperà di estrarre i dati dai file `print.txt` e di inserire questi nel file csv di output. Al momento il file di output appende i dati 
al file csv già esistente, quindi nel caso eliminalo prima di avviare lo script, in modo da avere un file csv pulito con solo i dati nuovi. 

Una volta creato il file contenente i dati di tutti i misuratori, dovrai inserire questi all'interno del database postgres di riferimento. 
Quindi apri pgAdmin, e come prima operazione elimina i dati presenti nella tabella "tab_measurments_clean_staging" (ossia la tabella di staging) 
usando il comando 
```sql
TRUNCATE hydro.tab_measurements_clean_staging;
``` 

Dopodiche, utilizzando la funzione GUI di importazione dati di pgadmin, importa i dati del file csv all'interno della tabella "tab_measurments_clean_staging".
Infine, usando questa tabella, bisogna importare i dati all'interno della tabella "tab_measurments_clean" (ossia la tabella finale) usando una query SQL di insert-select.
Di seguito la query utilizzata fino ad ora: 
```sql
INSERT INTO hydro.tab_measurements_clean (
  id_misuratore,
  data_misurazione,
  flow_ls_raw,
  flow_ls_smoothed,
  is_outlier,
  window_median,
  thresholds,
  updated_at
)
SELECT
  id_misuratore,
  data_misurazione,
  flow_ls_raw,
  flow_ls_smoothed,
  is_outlier,
  window_median,
  thresholds,
  COALESCE(updated_at, now())
FROM hydro.tab_measurements_clean_staging
ON CONFLICT (id_misuratore, data_misurazione) DO NOTHING;
```

Fatto questo, i dati saranno finalmente presenti all'interno della tabella finale e potranno essere utilizzati per le analisi sul portale.