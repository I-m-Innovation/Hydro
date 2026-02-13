DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_matviews
        WHERE schemaname = 'hydro'
          AND matviewname = 'mv_flow_exceedance_raw_vs_smoothed_2d'
    ) THEN
        EXECUTE $mv$
        CREATE MATERIALIZED VIEW hydro.mv_flow_exceedance_raw_vs_smoothed_2d AS
        WITH raw_base AS (
          SELECT
            c.id_misuratore,
            round(c.flow_ls_raw::numeric, 2) AS flow_2d
          FROM hydro.tab_measurements_clean c
          WHERE c.flow_ls_raw IS NOT NULL
        ),
        raw_freq AS (
          SELECT
            raw_base.id_misuratore,
            raw_base.flow_2d,
            count(*) AS cnt_raw
          FROM raw_base
          GROUP BY raw_base.id_misuratore, raw_base.flow_2d
        ),
        raw_ranked AS (
          SELECT
            rf.id_misuratore,
            rf.flow_2d,
            rf.cnt_raw,
            sum(rf.cnt_raw) OVER (
              PARTITION BY rf.id_misuratore
              ORDER BY rf.flow_2d DESC
              ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ) AS cum_ge_raw,
            sum(rf.cnt_raw) OVER (PARTITION BY rf.id_misuratore) AS total_raw
          FROM raw_freq rf
        ),
        raw_out AS (
          SELECT
            raw_ranked.id_misuratore,
            raw_ranked.flow_2d,
            raw_ranked.cnt_raw,
            raw_ranked.cum_ge_raw::double precision
              / NULLIF(raw_ranked.total_raw, 0::numeric)::double precision
              * 100.0::double precision AS p_exceed_raw
          FROM raw_ranked
        ),
        sm_base AS (
          SELECT
            c.id_misuratore,
            round(c.flow_ls_smoothed::numeric, 2) AS flow_2d
          FROM hydro.tab_measurements_clean c
          WHERE c.flow_ls_smoothed IS NOT NULL
        ),
        sm_freq AS (
          SELECT
            sm_base.id_misuratore,
            sm_base.flow_2d,
            count(*) AS cnt_smoothed
          FROM sm_base
          GROUP BY sm_base.id_misuratore, sm_base.flow_2d
        ),
        sm_ranked AS (
          SELECT
            sf.id_misuratore,
            sf.flow_2d,
            sf.cnt_smoothed,
            sum(sf.cnt_smoothed) OVER (
              PARTITION BY sf.id_misuratore
              ORDER BY sf.flow_2d DESC
              ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ) AS cum_ge_smoothed,
            sum(sf.cnt_smoothed) OVER (PARTITION BY sf.id_misuratore) AS total_smoothed
          FROM sm_freq sf
        ),
        sm_out AS (
          SELECT
            sm_ranked.id_misuratore,
            sm_ranked.flow_2d,
            sm_ranked.cnt_smoothed,
            sm_ranked.cum_ge_smoothed::double precision
              / NULLIF(sm_ranked.total_smoothed, 0::numeric)::double precision
              * 100.0::double precision AS p_exceed_smoothed
          FROM sm_ranked
        ),
        joined AS (
          SELECT
            COALESCE(r.id_misuratore, s.id_misuratore) AS id_misuratore,
            COALESCE(r.flow_2d, s.flow_2d) AS flow_2d,
            r.cnt_raw,
            r.p_exceed_raw,
            s.cnt_smoothed,
            s.p_exceed_smoothed
          FROM raw_out r
          FULL JOIN sm_out s
            ON s.id_misuratore = r.id_misuratore
           AND s.flow_2d = r.flow_2d
        )
        SELECT
          id_misuratore,
          flow_2d,
          cnt_raw,
          p_exceed_raw,
          cnt_smoothed,
          p_exceed_smoothed
        FROM joined
        ORDER BY id_misuratore, flow_2d DESC;
        $mv$;

        EXECUTE $ix$
        CREATE UNIQUE INDEX mv_flow_exceedance_raw_vs_smoothed_2d_uq
          ON hydro.mv_flow_exceedance_raw_vs_smoothed_2d (id_misuratore, flow_2d);
        $ix$;
    END IF;
END
$$;
