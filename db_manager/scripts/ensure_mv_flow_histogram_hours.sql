DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_matviews
        WHERE schemaname = 'hydro'
            AND matviewname = 'mv_flow_histogram_hours'
    ) THEN
        EXECUTE $mv$
        CREATE MATERIALIZED VIEW hydro.mv_flow_histogram_hours AS
        WITH hourly AS (
            SELECT
                t.id_misuratore,
                date_trunc(
                    'hour',
                    t.data_misurazione AT TIME ZONE 'Europe/Rome'
                ) AS hour_local,
                AVG(
                    CASE
                        WHEN t.flow_ls_raw::text = 'NaN' THEN NULL
                        ELSE t.flow_ls_raw
                    END
                ) AS flow_ls_raw_hourly_avg,
                AVG(
                    CASE
                        WHEN t.flow_ls_smoothed::text = 'NaN' THEN NULL
                        ELSE t.flow_ls_smoothed
                    END
                ) AS flow_ls_smoothed_hourly_avg
            FROM hydro.tab_measurements_clean t
            GROUP BY
                t.id_misuratore,
                date_trunc('hour', t.data_misurazione AT TIME ZONE 'Europe/Rome')
        ),
        raw_bins AS (
            SELECT
                h.id_misuratore,
                FLOOR(h.flow_ls_raw_hourly_avg / 10.0)::integer AS bin_index,
                COUNT(*)::integer AS hours_raw
            FROM hourly h
            WHERE h.flow_ls_raw_hourly_avg IS NOT NULL
                AND h.flow_ls_raw_hourly_avg >= -50
            GROUP BY
                h.id_misuratore,
                FLOOR(h.flow_ls_raw_hourly_avg / 10.0)::integer
        ),
        smoothed_bins AS (
            SELECT
                h.id_misuratore,
                FLOOR(h.flow_ls_smoothed_hourly_avg / 10.0)::integer AS bin_index,
                COUNT(*)::integer AS hours_smoothed
            FROM hourly h
            WHERE h.flow_ls_smoothed_hourly_avg IS NOT NULL
                AND h.flow_ls_smoothed_hourly_avg >= -50
            GROUP BY
                h.id_misuratore,
                FLOOR(h.flow_ls_smoothed_hourly_avg / 10.0)::integer
        ),
        all_bins AS (
            SELECT id_misuratore, bin_index FROM raw_bins
            UNION
            SELECT id_misuratore, bin_index FROM smoothed_bins
        )
        SELECT
            b.id_misuratore,
            b.bin_index,
            (b.bin_index * 10)::double precision AS range_start,
            ((b.bin_index + 1) * 10)::double precision AS range_end,
            COALESCE(r.hours_raw, 0) AS hours_raw,
            COALESCE(s.hours_smoothed, 0) AS hours_smoothed,
            now() AS updated_at
        FROM all_bins b
        LEFT JOIN raw_bins r
            ON r.id_misuratore = b.id_misuratore
            AND r.bin_index = b.bin_index
        LEFT JOIN smoothed_bins s
            ON s.id_misuratore = b.id_misuratore
            AND s.bin_index = b.bin_index
        ORDER BY
            b.id_misuratore,
            b.bin_index;
        $mv$;

        EXECUTE $ix$
        CREATE UNIQUE INDEX mv_flow_histogram_hours_uq
        ON hydro.mv_flow_histogram_hours (id_misuratore, bin_index);
        $ix$;

        EXECUTE $ix$
        CREATE INDEX mv_flow_histogram_hours_misuratore_idx
        ON hydro.mv_flow_histogram_hours (id_misuratore);
        $ix$;
    END IF;
END
$$;

CREATE UNIQUE INDEX IF NOT EXISTS mv_flow_histogram_hours_uq
ON hydro.mv_flow_histogram_hours (id_misuratore, bin_index);

CREATE INDEX IF NOT EXISTS mv_flow_histogram_hours_misuratore_idx
ON hydro.mv_flow_histogram_hours (id_misuratore);
