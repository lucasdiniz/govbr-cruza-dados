-- Tabelas de prestação de contas eleitorais (receitas e despesas de campanha)
-- Fonte: dadosabertos.tse.jus.br - prestacao_contas_candidatos_YYYY.zip

DROP TABLE IF EXISTS tse_despesa_candidato CASCADE;
DROP TABLE IF EXISTS tse_receita_candidato CASCADE;

CREATE TABLE tse_receita_candidato (
    id                      SERIAL PRIMARY KEY,
    ano_eleicao             SMALLINT,
    sg_uf                   TEXT,
    sq_prestador_contas     TEXT,
    nr_cnpj_prestador       TEXT,
    cd_cargo                TEXT,
    ds_cargo                TEXT,
    sq_candidato            TEXT,
    nr_candidato            TEXT,
    nm_candidato            TEXT,
    nr_cpf_candidato        TEXT,
    nr_partido              TEXT,
    sg_partido              TEXT,
    nm_partido              TEXT,
    ds_fonte_receita        TEXT,
    ds_origem_receita       TEXT,
    ds_natureza_receita     TEXT,
    ds_especie_receita      TEXT,
    cd_cnae_doador          TEXT,
    ds_cnae_doador          TEXT,
    cpf_cnpj_doador         TEXT,
    nm_doador               TEXT,
    nm_doador_rfb           TEXT,
    sg_uf_doador            TEXT,
    nm_municipio_doador     TEXT,
    sq_candidato_doador     TEXT,
    sg_partido_doador       TEXT,
    nr_recibo_doacao        TEXT,
    sq_receita              TEXT,
    dt_receita              DATE,
    ds_receita              TEXT,
    vr_receita              NUMERIC,
    ds_genero               TEXT,
    ds_cor_raca             TEXT
);

CREATE TABLE tse_despesa_candidato (
    id                      SERIAL PRIMARY KEY,
    ano_eleicao             SMALLINT,
    sg_uf                   TEXT,
    sq_prestador_contas     TEXT,
    ds_tipo_documento       TEXT,
    nr_documento            TEXT,
    ds_fonte_despesa        TEXT,
    ds_origem_despesa       TEXT,
    ds_natureza_despesa     TEXT,
    ds_especie_recurso      TEXT,
    sq_despesa              TEXT,
    sq_parcelamento         TEXT,
    dt_pagto_despesa        DATE,
    ds_despesa              TEXT,
    vr_pagto_despesa        NUMERIC
);
