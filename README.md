Ultimo update - 29/01/2026

Prima di leggere è bene sapere che comunque questo è il mio primo progetto django. Chiaramente ci saranno errori o logiche implementate dalla dubbia logica. Tuttavia, ho cercato di fare tutto in modo abbastanza pulito, usando nomi intuitivi e seguendo delle "buone" (opinabile) pratiche di progettazione. In ogni caso questo documento è più una guida e non è detto che tutto sia corretto. Quindi non prendetela come la Bibbia e chiedetevi sempre se quello che sto leggendo sia vero. Dubitate sempre insomma, non si sa mai. 




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
