WITH params AS (
    SELECT
        date_trunc('hour', now()) AS window_end,
        date_trunc('hour', now()) - interval '{WINDOW_HOURS} hours' AS window_start
),
data AS (
    SELECT
        id_misuratore,
        flow_ls_smoothed AS value
    FROM hydro.tab_measurements_clean
    WHERE data_misurazione >= (SELECT window_start FROM params)
        AND data_misurazione < (SELECT window_end FROM params)
        AND flow_ls_smoothed IS NOT NULL
),
ranges AS (
    SELECT
        id_misuratore,
        MIN(value) AS min_v,
        MAX(value) AS max_v
    FROM data
    GROUP BY id_misuratore
),
buckets AS (
    SELECT
        d.id_misuratore,
        CASE
            WHEN r.max_v = r.min_v THEN 1
            ELSE width_bucket(d.value, r.min_v, r.max_v, {BINS})
        END AS bin_index,
        r.min_v,
        r.max_v
    FROM data d
    JOIN ranges r USING (id_misuratore)
),
agg AS (
    SELECT
        id_misuratore,
        bin_index,
        min_v,
        max_v,
        COUNT(*) AS count
    FROM buckets
    WHERE bin_index BETWEEN 1 AND {BINS}
    GROUP BY id_misuratore, bin_index, min_v, max_v
),
bins AS (
    SELECT
        r.id_misuratore,
        gs AS bin_index,
        r.min_v,
        r.max_v
    FROM ranges r,
        generate_series(1, {BINS}) AS gs
),
final AS (
    SELECT
        b.id_misuratore,
        b.bin_index,
        b.min_v,
        b.max_v,
        COALESCE(a.count, 0) AS count
    FROM bins b
    LEFT JOIN agg a
        ON a.id_misuratore = b.id_misuratore
        AND a.bin_index = b.bin_index
)
INSERT INTO hydro.tab_flow_histogram (
    id_misuratore,
    window_start,
    window_end,
    bin_index,
    range_start,
    range_end,
    count,
    updated_at
)
SELECT
    f.id_misuratore,
    p.window_start,
    p.window_end,
    f.bin_index,
    CASE
        WHEN f.max_v = f.min_v THEN f.min_v
        ELSE f.min_v + (f.bin_index - 1) * ((f.max_v - f.min_v) / {BINS})
    END AS range_start,
    CASE
        WHEN f.max_v = f.min_v THEN f.max_v
        ELSE f.min_v + (f.bin_index) * ((f.max_v - f.min_v) / {BINS})
    END AS range_end,
    f.count,
    now()
FROM final f
CROSS JOIN params p
ON CONFLICT (id_misuratore, window_start, window_end, bin_index)
DO UPDATE SET
    range_start = EXCLUDED.range_start,
    range_end = EXCLUDED.range_end,
    count = EXCLUDED.count,
    updated_at = now();
