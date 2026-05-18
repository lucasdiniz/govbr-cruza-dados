-- Tabela do Novo Bolsa Familia
-- Fonte: portaldatransparencia.gov.br/download-de-dados/novo-bolsa-familia
--
-- IDEMPOTENTE: Bolsa Familia migrou para o framework ETL incremental
-- (ver ADR-0010). Schema canonico nunca mais e re-criado destrutivamente —
-- migration sql/41_bolsa_familia_incremental.sql adiciona o que falta
-- (UNIQUE INDEX, inserted_at, etc).
--
-- Aplicado em:
--   * Fase 1 do ETL classico (etl/01_schema.py) — bootstrap inicial.
--   * Step "ETL: Incremental" do deploy.yml (defensivo, idempotente).

CREATE TABLE IF NOT EXISTS bolsa_familia (
    id                  SERIAL PRIMARY KEY,
    mes_competencia     TEXT,
    mes_referencia      TEXT,
    uf                  TEXT,
    cd_municipio_siafi  TEXT,
    nm_municipio        TEXT,
    cpf_favorecido      TEXT,
    nis_favorecido      TEXT,
    nm_favorecido       TEXT,
    valor_parcela       NUMERIC
);

-- Staging para COPY direto (valor como TEXT) — UNLOGGED, recriada a cada carga.
-- Mantida apenas por compatibilidade com codigo legado de import manual; o
-- framework incremental usa sua propria staging gerenciada por
-- etl/incremental/staging.py.
CREATE UNLOGGED TABLE IF NOT EXISTS _stg_bolsa_familia (
    c0 TEXT, c1 TEXT, c2 TEXT, c3 TEXT,
    c4 TEXT, c5 TEXT, c6 TEXT, c7 TEXT, c8 TEXT
);

-- Indices clasicos (idempotentes). Indice UNIQUE para upsert do framework
-- incremental e criado por sql/41_bolsa_familia_incremental.sql (CONCURRENTLY).
CREATE INDEX IF NOT EXISTS idx_bf_cpf ON bolsa_familia(cpf_favorecido);
CREATE INDEX IF NOT EXISTS idx_bf_nis ON bolsa_familia(nis_favorecido);
CREATE INDEX IF NOT EXISTS idx_bf_nome ON bolsa_familia USING gin(nm_favorecido gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_bf_municipio ON bolsa_familia(cd_municipio_siafi);
CREATE INDEX IF NOT EXISTS idx_bf_uf ON bolsa_familia(uf);
