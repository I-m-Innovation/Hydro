CREATE TABLE IF NOT EXISTS hydro.tab_flow_histogram (
    id_misuratore TEXT NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    bin_index INTEGER NOT NULL,
    range_start DOUBLE PRECISION NOT NULL,
    range_end DOUBLE PRECISION NOT NULL,
    count INTEGER NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id_misuratore, window_start, window_end, bin_index),
    CONSTRAINT fk_flow_histogram_misuratore
        FOREIGN KEY (id_misuratore)
        REFERENCES hydro.tab_misuratori (id_misuratore)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);
