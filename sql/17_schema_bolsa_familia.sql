-- Tabela do Novo Bolsa Familia
-- Fonte: portaldatransparencia.gov.br/download-de-dados/novo-bolsa-familia

DROP TABLE IF EXISTS bolsa_familia CASCADE;

CREATE TABLE bolsa_familia (
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

-- Staging para COPY direto (valor como TEXT)
DROP TABLE IF EXISTS _stg_bolsa_familia;
CREATE UNLOGGED TABLE _stg_bolsa_familia (
    c0 TEXT, c1 TEXT, c2 TEXT, c3 TEXT,
    c4 TEXT, c5 TEXT, c6 TEXT, c7 TEXT, c8 TEXT
);
