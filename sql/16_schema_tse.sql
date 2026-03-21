-- Tabelas do TSE (Tribunal Superior Eleitoral)
-- Fonte: dadosabertos.tse.jus.br

DROP TABLE IF EXISTS tse_despesa_candidato CASCADE;
DROP TABLE IF EXISTS tse_receita_candidato CASCADE;
DROP TABLE IF EXISTS tse_bem_candidato CASCADE;
DROP TABLE IF EXISTS tse_candidato CASCADE;

CREATE TABLE tse_candidato (
    id                  SERIAL PRIMARY KEY,
    ano_eleicao         SMALLINT,
    sg_uf               TEXT,
    nm_ue               TEXT,
    cd_cargo            TEXT,
    ds_cargo            TEXT,
    sq_candidato        TEXT,
    nr_candidato        TEXT,
    nm_candidato        TEXT,
    nm_urna_candidato   TEXT,
    nm_social_candidato TEXT,
    cpf                 TEXT,
    nr_partido          TEXT,
    sg_partido          TEXT,
    nm_partido          TEXT,
    sg_uf_nascimento    TEXT,
    dt_nascimento       DATE,
    cd_genero           TEXT,
    ds_genero           TEXT,
    cd_grau_instrucao   TEXT,
    ds_grau_instrucao   TEXT,
    cd_cor_raca         TEXT,
    ds_cor_raca         TEXT,
    cd_ocupacao         TEXT,
    ds_ocupacao         TEXT,
    cd_sit_tot_turno    TEXT,
    ds_sit_tot_turno    TEXT,
    nr_cnpj_campanha    TEXT,
    ds_situacao_candidatura TEXT
);

CREATE TABLE tse_bem_candidato (
    id                  SERIAL PRIMARY KEY,
    ano_eleicao         SMALLINT,
    sg_uf               TEXT,
    sq_candidato        TEXT,
    nr_ordem_bem        TEXT,
    cd_tipo_bem         TEXT,
    ds_tipo_bem         TEXT,
    ds_bem              TEXT,
    valor_bem           NUMERIC
);
