Ultimo update - 29/01/2026


# Problemi principali ancora presenti (non affrontati) 29/01/2026

- Gestione connessioni DB per evento: ad ogni evento apri/chiudi una nuova connessione. Su carichi continui può saturare il DB o creare latenza inutile. Serve un pool o una connessione riutilizzata. main_00.py
- Retry minimo e senza backoff reale: hai solo 1 retry con sleep(1). Se il DB resta giù per più tempo, perdi eventi (return) e non fai checkpoint. main_00.py
- Checkpoint solo dopo insert riuscito: se un evento fallisce l’insert, il checkpoint non viene aggiornato e quell’evento verrà riprocessato all’infinito (potenziale loop). main_00.py
- Throttle per device con stato in RAM: LAST_EVENT_TS_BY_ID cresce senza limite se i device sono tanti e non ha scadenza. Con mesi di runtime può consumare RAM. main_00.py
- Threading senza shutdown pulito: i consumer sono in thread daemon, quindi in stop forzato non hai garanzie su flush/checkpoint/close. main_00.py
- Nessun controllo su payload invalido parziale: se values è dict ma contiene misure non conformi, salti semplicemente senza logging strutturato; è difficile capire quali device generano dati sporchi. main_00.py
- Se vuoi, posso affrontarli in ordine di impatto con cambi minimi (pool connessioni + retry/backoff + cleanup state).


## Ultimo update - 30/01/2026

### DB Manager
- Aggiunta tabella `hydro.tab_flow_histogram` (schema “lungo”) con FK su `tab_misuratori`.
- Job `refresh_flow_histogram` con SQL dedicato e scheduler in `run.py`.
- Istogramma calcolato su **tutto lo storico** (`FLOW_HIST_WINDOW_HOURS = 0`).
- Pianificazione istogramma: **1 volta al giorno** (`SECONDS_BETWEEN_REFRESH_FLOW_HISTOGRAM = 86400`).
- Endpoint Django per istogramma: `/portale/api/flow-histogram/?id_misuratore=...`.
- Output API include `percent` oltre a `count`.

### Frontend (charts)
- Grafico istogramma collegato all’endpoint e visualizzato su “chart-fluid-velocity”.
- Asse Y in percentuale con tick interi.
- Tooltip con **range del bin**, **percentuale** e **numero punti**.
- Asse X visibile con tick della portata.

## Ultimo update - 02/02/2026

### Frontend (status LED)
- Aggiunto LED di stato vicino al titolo del misuratore in `portale_hydro_3_0/portale/templates/portale/includes/main.html`.
- Stili LED con animazione pulse e classi stato (`status-green`, `status-orange`, `status-red`, `status-gray`) in `portale_hydro_3_0/portale/static/portale/css/style.css`.
- Script `portale_hydro_3_0/portale/static/portale/js/led_status.js` con polling ogni 60s e log di debug.

### Backend (status LED)
- Nuovo endpoint `api/led-status/` che restituisce l'ultima misurazione per misuratore in `portale_hydro_3_0/portale/views.py` e `portale_hydro_3_0/portale/urls.py`.
- Regole stato: >2h giallo, >6h rosso, assenza dati grigio, altrimenti verde.

### Workflow LED (come diventa "attivo")
- Il template renderizza il LED con `data-misuratore-id` per il misuratore corrente.
- `led_status.js` fa polling ogni 60s su `/portale/api/led-status/`.
- L'API ritorna `latest_measurement` per ogni misuratore (timestamp ISO).
- Il JS calcola le ore trascorse dall'ultima misura e assegna la classe:
  - `status-green` se <= 2h
  - `status-orange` se > 2h
  - `status-red` se > 6h
  - `status-gray` se manca il dato o la data è invalida.

### Decimazione dati (LTTB)
- Il grafico `chart-flow-rate` usa la decimazione di Chart.js quando `useApi` è true, `type` è `line` e l'asse X è `linear`.
- L'algoritmo LTTB (Largest Triangle Three Buckets) riduce i punti mantenendo la forma del segnale.
- Funzionamento: mantiene primo/ultimo punto, divide i dati in bucket e per ogni bucket sceglie il punto che massimizza l'area del triangolo rispetto al punto scelto prima e alla media del bucket successivo.
- Risultato: preserva trend e picchi più importanti rispetto a un semplice sampling uniforme.

### Sistema di Visualizzazione Grafici (charts.js)

#### Architettura Core
- **File principale**: `portale_hydro_3_0/portale/static/portale/js/charts.js` (~1200 righe)
- **Libreria**: Chart.js con plugin zoom e decimazione LTTB
- **Gestione stato**: Map-based per istanze grafici e polling intervals
- **Aggiornamento**: API polling ogni 60s solo per range 24h

#### Tipologie di Grafici
1. **Flow Rate (`chart-flow-rate`)**:
   - Doppio dataset: raw e smoothed data
   - Asse X temporale (timestamp in ms), Y portata (l/s)
   - Decimazione automatica sopra 1250 punti
   - Gap detection con interruzione linee e ombreggiatura
   - Media mobile configurabile per range

2. **Flow Histogram (`chart-fluid-velocity`)**:
   - Grafico a barre per distribuzione portate
   - Bins pre-calcolati dal backend con range start/end
   - Tooltip con intervallo, percentuale e count punti
   - Asse Y in percentuale, X in l/s

3. **Duration Curve (`chart-curva-di-durata`)**:
   - Curva durate/superamenti (0-100% tempo)
   - Linea verticale fissa a 80% con calcolo Y dinamico
   - Filtro valori < -50 l/s, tick solo su 0/80/100%
   - Asse Y auto-scalato su min/max dataset

#### Sistema di Gap Detection
```javascript
// Soglie temporali differenziate
const GAP_THRESHOLD_SHORT_MS = 2 * 60 * 60 * 1000; // 2h per 24h/7d/1m
const GAP_THRESHOLD_LONG_MS = 3 * 24 * 60 * 60 * 1000; // 3 giorni per 6m/1y/all

// Due strategie per gestione gap
buildFlowPointsWithGaps()      // Decimazione attiva: usa null/midpoint
buildFlowPointsWithGapsShort() // Decimazione off: usa NaN per interrompere linee
```

#### Plugin Sistema
- **hoverLinePlugin**: Linea verticale al passaggio mouse
- **gapShadingPlugin**: Ombreggiatura rossa su gap temporali
- **staticVLinePlugin**: Linee di riferimento con ticks personalizzati

#### Gestione Performance
- **Decimazione LTTB**: Algoritmo "Largest Triangle Three Buckets"
  - Threshold: 1250 punti per flow-rate
  - Preserva forma segnale riducendo dataset
  - Info button mostrato solo quando attiva
- **Parsing condizionale**: `parsing: false` solo con decimazione
- **Update ottimizzato**: `chart.update("none")` per performance

#### Sistema Range/Controlli
- **Range buttons**: 24h, 7d, 1m, 6m, 1y, all
- **Zoom**: Area drag, wheel zoom, pan su asse X
- **Reset**: Ripristino zoom per grafico specifico
- **Auto-refresh**: Solo range 24h, intervallo 60s

#### Configurazione Dinamica
- **API endpoints**: Differenziati per tipo grafico
- **Labels range**: Solo flow-rate mostra date inizio/fine  
- **Tooltip format**: Personalizzato per tipo dato
- **Scale management**: Auto-fit con suggestedMin/Max

#### Error Handling & Robustezza
- Graceful fallback su errori API
- Validazione dati con `Number.isFinite()`
- Cleanup automatico istanze/polling
- Gestione resize responsive

### Update grafici (flow-chart e gap detection)
- Risolto problema rendering per range brevi (24h/7d/1m): ora punti e gap vengono visualizzati correttamente
- Implementata gestione differenziata gap: `NaN` per Chart.js senza decimazione, `null` con decimazione attiva
- Eliminata label date dal grafico flow-rate per ridurre clutter visivo
- Gap detection funziona su distanze temporali reali (non solo valori null nel dataset)

### Update grafici (flow-chart e curva di durata)
- `chart-flow-rate` ora usa asse X lineare (timestamp in ms), tick solo su inizio/fine e tooltip in formato `DD/MM/YYYY HH:MM:ss`.
- Logica gap: se tra due misure il salto supera 2h (24h/7d/1m) o 3 giorni (6m/1y/all), la linea si interrompe e viene mostrata una banda rossa semitrasparente.
- Soglia decimazione per flow-chart configurabile (attualmente 1250 punti) e bottone info visibile solo quando attiva.
- Curva di durata: linea verticale a 80%, linea orizzontale su y=0 e tick solo su 0/80/100 sull'asse X.
