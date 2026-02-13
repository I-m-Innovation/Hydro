DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_matviews
        WHERE schemaname = 'hydro'
          AND matviewname = 'mv_flow_duration_curve_hourly_raw_local'
    ) THEN
        EXECUTE $mv$
        CREATE MATERIALIZED VIEW hydro.mv_flow_duration_curve_hourly_raw_local AS
        WITH hourly AS (
          SELECT
            c.id_misuratore,
            date_trunc('hour', c.data_misurazione AT TIME ZONE 'Europe/Rome') AS ora_locale,
            avg(c.flow_ls_raw)::double precision AS flow_avg_hour_raw
          FROM hydro.tab_measurements_clean c
          WHERE c.flow_ls_raw IS NOT NULL
          GROUP BY
            c.id_misuratore,
            date_trunc('hour', c.data_misurazione AT TIME ZONE 'Europe/Rome')
        ),
        ranked AS (
          SELECT
            h.id_misuratore,
            h.ora_locale,
            h.flow_avg_hour_raw,
            SUM(1) OVER (
              PARTITION BY h.id_misuratore
              ORDER BY h.flow_avg_hour_raw DESC
              ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ) AS cum_ge,
            COUNT(*) OVER (PARTITION BY h.id_misuratore) AS total_n
          FROM hourly h
        )
        SELECT
          id_misuratore,
          ora_locale,
          flow_avg_hour_raw,
          (cum_ge::double precision / NULLIF(total_n, 0)::double precision) * 100.0 AS p_exceed
        FROM ranked;
        $mv$;

        EXECUTE $ix$
        CREATE UNIQUE INDEX mv_flow_duration_curve_hourly_raw_local_uq
          ON hydro.mv_flow_duration_curve_hourly_raw_local (id_misuratore, ora_locale);
        $ix$;
    END IF;
END
$$;
