DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_matviews
        WHERE schemaname = 'hydro'
          AND matviewname = 'mv_flow_daily_avg'
    ) THEN
        EXECUTE $mv$
        CREATE MATERIALIZED VIEW hydro.mv_flow_daily_avg AS
        WITH base AS (
            SELECT
                id_misuratore,
                date_trunc('day', (data_misurazione AT TIME ZONE 'Europe/Rome'))::date AS day,
                flow_ls_raw,
                flow_ls_smoothed
            FROM hydro.tab_measurements_clean
        )
        SELECT
            id_misuratore,
            day,
            AVG(flow_ls_raw)        AS flow_ls_raw_avg,
            AVG(flow_ls_smoothed)   AS flow_ls_smoothed_avg,
            COUNT(flow_ls_raw)      AS samples_raw,
            COUNT(flow_ls_smoothed) AS samples_smoothed
        FROM base
        GROUP BY id_misuratore, day;
        $mv$;

        EXECUTE $ix$
        CREATE UNIQUE INDEX mv_flow_daily_avg_uq
        ON hydro.mv_flow_daily_avg (id_misuratore, day);
        $ix$;
    END IF;
END
$$;
