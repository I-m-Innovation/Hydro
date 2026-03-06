-- Alignment script based on local `py manage.py inspectdb` output.
-- Goal: keep table/column names and types aligned with current DB introspection.
-- NOTE blocks mark differences vs previous draft/diagram that are not aligned at the moment.
-- Target schema: hydro.


-- 1) tab_impianti
-- NOTE: previous draft used `tab_impianti_idroelettrici`.
-- NOTE: `tipo_proprieta` and `stato_impianto` are included below to match requested target schema,
-- but they are not present in current inspectdb output.
CREATE TABLE IF NOT EXISTS hydro.tab_impianti (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(100) UNIQUE NOT NULL,
    indirizzo VARCHAR(100),
    descrizione TEXT,
    note TEXT,
    is_active BOOLEAN,
    created_at TIMESTAMPTZ,
    tipo_proprieta VARCHAR(50) CHECK (tipo_proprieta IN ('azienda', 'cliente')),
    stato_impianto VARCHAR(50) CHECK (stato_impianto IN ('in_costruzione', 'operativo', 'dismesso', 'in_chiusura'))
);


-- 2) tab_tipologia_turbina
-- NOTE: previous draft used plural name `tab_tipologie_turbina`.
CREATE TABLE IF NOT EXISTS hydro.tab_tipologia_turbina (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(50) UNIQUE NOT NULL,
    descrizione TEXT
);


-- 3) tab_turbine
-- NOTE: inspectdb includes `portata_max_ls`, missing in previous draft.
-- NOTE: inspectdb shows NUMERIC(10,3) for portata_nominale_ls and portata_min_ls.
CREATE TABLE IF NOT EXISTS hydro.tab_turbine (
    id SERIAL PRIMARY KEY,
    id_impianto INTEGER NOT NULL,
    id_tipologia_turbina INTEGER NOT NULL,
    nome VARCHAR(100) NOT NULL,
    salto_nominale_m NUMERIC(8,2),
    salto_netto_m NUMERIC(8,2),
    portata_nominale_ls NUMERIC(10,3),
    portata_min_ls NUMERIC(10,3),
    portata_max_ls NUMERIC(10,3),
    potenza_nominale_kw NUMERIC(10,2),
    rendimento_nominale NUMERIC(6,4),
    note TEXT,
    is_active BOOLEAN,
    created_at TIMESTAMPTZ,
    CONSTRAINT uq_tab_turbine_impianto_nome UNIQUE (id_impianto, nome),
    CONSTRAINT fk_tab_turbine_impianto FOREIGN KEY (id_impianto) REFERENCES hydro.tab_impianti(id),
    CONSTRAINT fk_tab_turbine_tipologia FOREIGN KEY (id_tipologia_turbina) REFERENCES hydro.tab_tipologia_turbina(id)
);


-- 4) tab_turbina_parametri
CREATE TABLE IF NOT EXISTS hydro.tab_turbina_parametri (
    id SERIAL PRIMARY KEY,
    id_turbina INTEGER NOT NULL UNIQUE,
    eta0 NUMERIC(8,6) NOT NULL,
    eta_max NUMERIC(8,6) NOT NULL,
    x0 NUMERIC(8,6) NOT NULL,
    al NUMERIC(12,6) NOT NULL,
    ar NUMERIC(12,6) NOT NULL,
    kl NUMERIC(6,3) NOT NULL,
    kr NUMERIC(6,3) NOT NULL,
    q_min_ls NUMERIC(10,3) NOT NULL,
    q_max_ls NUMERIC(10,3) NOT NULL,
    metodo VARCHAR(50),
    note TEXT,
    created_at TIMESTAMPTZ,
    is_active BOOLEAN,
    CONSTRAINT fk_tab_turbina_parametri_turbina FOREIGN KEY (id_turbina) REFERENCES hydro.tab_turbine(id)
);


-- 5) tab_turbina_curve_points
-- NOTE: inspectdb includes `q_ls` and unique_together(id_turbina, x).
CREATE TABLE IF NOT EXISTS hydro.tab_turbina_curve_points (
    id SERIAL PRIMARY KEY,
    id_turbina INTEGER NOT NULL,
    x NUMERIC(8,6) NOT NULL,
    eta NUMERIC(8,6) NOT NULL,
    created_at TIMESTAMPTZ,
    q_ls NUMERIC(10,3),
    CONSTRAINT uq_tab_turbina_curve_points_turbina_x UNIQUE (id_turbina, x),
    CONSTRAINT fk_tab_turbina_curve_points_turbina FOREIGN KEY (id_turbina) REFERENCES hydro.tab_turbine(id)
);


-- 6) tab_rendimento_medio_pelton
-- NOTE: this table was previously only documented in comments and not created.
-- NOTE: column names with special characters are preserved as quoted identifiers.
CREATE TABLE IF NOT EXISTS hydro.tab_rendimento_medio_pelton (
    portata_bin NUMERIC(5,2) PRIMARY KEY,
    rendimento_mean NUMERIC(8,5),
    n NUMERIC(10,0),
    rendimento_mean_is_outlier BOOLEAN,
    "Q_[m3/s]" NUMERIC(8,5),
    "Potenza_attesa_trebisacce [kW]" NUMERIC(8,5),
    rendimento_can NUMERIC(8,5),
    rendimento_par NUMERIC(8,5),
    rendimento_st NUMERIC(8,5)
);

-- 1.b) Align existing hydro.tab_impianti values/constraints (if table already exists)
ALTER TABLE IF EXISTS hydro.tab_impianti
    ADD COLUMN IF NOT EXISTS tipo_proprieta VARCHAR(50),
    ADD COLUMN IF NOT EXISTS stato_impianto VARCHAR(50);

