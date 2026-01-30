# DB Manager

Questo modulo raccoglie tutto il codice dedicato alla gestione del database.
L'obiettivo e' tenere la logica DB separata dal progetto Django, in modo che
le operazioni di ingestione, trasformazione e manutenzione siano chiare,
riutilizzabili e facili da automatizzare.

Nota: nel progetto usiamo il termine ETL (Extract, Transform, Load) per indicare
i job che trasformano i dati raw e li caricano nelle tabelle finali.

### Avvio
Per evitare problemi di import, esegui il modulo dal root del progetto:

```
py -m db_manager.run
```

Questo comando va lanciato da `C:\...\Hydra_3_0`.

### Requisiti
Il modulo legge la connessione al database dalle variabili d'ambiente:
`PGHOST`, `PGPORT`, `PGDBNAME`, `PGUSER`, `PGPASSWORD`.

### Struttura
- `config/`: configurazione e variabili d'ambiente
- `db/`: connessione DB, loader SQL, schema e helper
- `jobs/`: job Python (ingest, refresh_stats, ecc.)
- `scripts/`: query SQL riutilizzabili, separate dal codice

In pratica: i job richiamano i file SQL quando serve, mentre `run.py` fa da
entrypoint principale.

### Workflow DB (alto livello)
1) **Ingestione**: i dati arrivano da Azure Event Hub in `tab_measurements_raw`.
2) **Transform**: i raw vengono trasformati in `tab_measurements` (formato wide).
3) **Clean (Hampel)**: si applica il filtro Hampel e si scrive in `tab_measurements_clean`.
4) **Stats**: si aggiornano le statistiche in `tab_statistiche_misuratori`.
5) **Flow histogram**: si calcola l'istogramma di portata in `tab_flow_histogram`.
6) **Materialized View**: si aggiorna `mv_flow_duration_curve_daily`.

### ETL incrementale (raw -> measurements)
Il job di trasformazione usa una tabella di stato (`hydro.tab_etl_state`) per
processare solo i nuovi dati raw. In questo modo evita di ricalcolare tutto
ad ogni ciclo e rimane leggero anche con molti dati.

### Clean (Hampel) -> tab_measurements_clean
Abbiamo un job Python che legge da `tab_measurements`, applica il filtro Hampel
per ogni `device_id` (sulla colonna `instant_flow_rate_2`) e fa upsert su
`tab_measurements_clean`. Il job e' incrementale e usa `tab_etl_state` per
ricordare l'ultimo timestamp processato.

### Scheduler interno
`run.py` avvia l'ingestione Event Hub e, in parallelo, un job periodico di
trasformazione. L'intervallo si regola in `config/settings.py` tramite
`SECONDS_BETWEEN_RAW_TO_MEASUREMENTS_TRANSFORM`, `SECONDS_BETWEEN_CLEAN_MEASUREMENTS`
`SECONDS_BETWEEN_REFRESH_STATS`, `SECONDS_BETWEEN_REFRESH_FLOW_HISTOGRAM`
e `SECONDS_BETWEEN_REFRESH_MV`.
