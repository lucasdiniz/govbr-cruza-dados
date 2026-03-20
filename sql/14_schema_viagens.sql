-- Tabelas de Viagens a Servico do Governo Federal
-- Fonte: portaldatransparencia.gov.br/download-de-dados/viagens

DROP TABLE IF EXISTS viagem_trecho CASCADE;
DROP TABLE IF EXISTS viagem_passagem CASCADE;
DROP TABLE IF EXISTS viagem_pagamento CASCADE;
DROP TABLE IF EXISTS viagem CASCADE;

CREATE TABLE viagem (
    id                      SERIAL PRIMARY KEY,
    id_processo_viagem      TEXT,
    numero_proposta         TEXT,
    situacao                TEXT,
    viagem_urgente          TEXT,
    justificativa_urgencia  TEXT,
    cod_orgao_superior      TEXT,
    nome_orgao_superior     TEXT,
    cod_orgao_solicitante   TEXT,
    nome_orgao_solicitante  TEXT,
    cpf_viajante            TEXT,
    nome_viajante           TEXT,
    cargo                   TEXT,
    funcao                  TEXT,
    descricao_funcao        TEXT,
    dt_inicio               DATE,
    dt_fim                  DATE,
    destinos                TEXT,
    motivo                  TEXT,
    valor_diarias           NUMERIC,
    valor_passagens         NUMERIC
);

CREATE TABLE viagem_pagamento (
    id                      SERIAL PRIMARY KEY,
    id_processo_viagem      TEXT,
    numero_proposta         TEXT,
    cod_orgao_superior      TEXT,
    nome_orgao_superior     TEXT,
    cod_orgao_pagador       TEXT,
    nome_orgao_pagador      TEXT,
    cod_unidade_gestora     TEXT,
    nome_unidade_gestora    TEXT,
    tipo_pagamento          TEXT,
    valor                   NUMERIC
);
