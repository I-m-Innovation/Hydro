DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_matviews
        WHERE schemaname = 'hydro'
          AND matviewname = 'mv_led_status'
    ) THEN
        EXECUTE $mv$
        CREATE MATERIALIZED VIEW hydro.mv_led_status AS
        SELECT
            m.id_misuratore,
            m.name,
            MAX(t.data_misurazione) AS latest_measurement
        FROM hydro.tab_misuratori m
        LEFT JOIN hydro.tab_measurements_clean t
            ON t.id_misuratore = m.id_misuratore
        GROUP BY m.id_misuratore, m.name;
        $mv$;

        EXECUTE $ix$
        CREATE UNIQUE INDEX mv_led_status_uq
        ON hydro.mv_led_status (id_misuratore);
        $ix$;
    END IF;
END
$$;
