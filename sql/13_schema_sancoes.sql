-- Tabelas de Sancoes (CEIS, CNEP, CEAF, Acordos de Leniencia)
-- Fonte: portaldatransparencia.gov.br/download-de-dados/

DROP TABLE IF EXISTS ceis_sancao CASCADE;
DROP TABLE IF EXISTS cnep_sancao CASCADE;
DROP TABLE IF EXISTS ceaf_expulsao CASCADE;
DROP TABLE IF EXISTS acordo_leniencia CASCADE;
DROP TABLE IF EXISTS acordo_efeito CASCADE;

-- CEIS: Cadastro Nacional de Empresas Inidoneas e Suspensas
CREATE TABLE ceis_sancao (
    id                          SERIAL PRIMARY KEY,
    cadastro                    TEXT,
    codigo_sancao               TEXT,
    tipo_pessoa                 TEXT,
    cpf_cnpj_sancionado         TEXT,
    nome_sancionado             TEXT,
    nome_informado_orgao        TEXT,
    razao_social_rfb            TEXT,
    nome_fantasia_rfb           TEXT,
    numero_processo             TEXT,
    categoria_sancao            TEXT,
    dt_inicio_sancao            DATE,
    dt_final_sancao             DATE,
    dt_publicacao               DATE,
    publicacao                  TEXT,
    detalhamento_publicacao     TEXT,
    dt_transito_julgado         DATE,
    abrangencia_sancao          TEXT,
    orgao_sancionador           TEXT,
    uf_orgao_sancionador        TEXT,
    esfera_orgao_sancionador    TEXT,
    fundamentacao_legal         TEXT,
    dt_origem_informacao        DATE,
    origem_informacoes          TEXT,
    observacoes                 TEXT
);

-- CNEP: Cadastro Nacional de Empresas Punidas (Lei Anticorrupcao)
CREATE TABLE cnep_sancao (
    id                          SERIAL PRIMARY KEY,
    cadastro                    TEXT,
    codigo_sancao               TEXT,
    tipo_pessoa                 TEXT,
    cpf_cnpj_sancionado         TEXT,
    nome_sancionado             TEXT,
    nome_informado_orgao        TEXT,
    razao_social_rfb            TEXT,
    nome_fantasia_rfb           TEXT,
    numero_processo             TEXT,
    categoria_sancao            TEXT,
    valor_multa                 NUMERIC,
    dt_inicio_sancao            DATE,
    dt_final_sancao             DATE,
    dt_publicacao               DATE,
    publicacao                  TEXT,
    detalhamento_publicacao     TEXT,
    dt_transito_julgado         DATE,
    abrangencia_sancao          TEXT,
    orgao_sancionador           TEXT,
    uf_orgao_sancionador        TEXT,
    esfera_orgao_sancionador    TEXT,
    fundamentacao_legal         TEXT,
    dt_origem_informacao        DATE,
    origem_informacoes          TEXT,
    observacoes                 TEXT
);

-- CEAF: Cadastro de Expulsoes da Administracao Federal
CREATE TABLE ceaf_expulsao (
    id                          SERIAL PRIMARY KEY,
    cadastro                    TEXT,
    codigo_sancao               TEXT,
    tipo_pessoa                 TEXT,
    cpf_cnpj_sancionado         TEXT,
    nome_sancionado             TEXT,
    categoria_sancao            TEXT,
    numero_documento            TEXT,
    numero_processo             TEXT,
    dt_inicio_sancao            DATE,
    dt_final_sancao             DATE,
    dt_publicacao               DATE,
    publicacao                  TEXT,
    detalhamento_publicacao     TEXT,
    dt_transito_julgado         DATE,
    abrangencia_sancao          TEXT,
    cargo_efetivo               TEXT,
    funcao_confianca            TEXT,
    orgao_lotacao               TEXT,
    orgao_sancionador           TEXT,
    uf_orgao_sancionador        TEXT,
    esfera_orgao_sancionador    TEXT,
    fundamentacao_legal         TEXT,
    dt_origem_informacao        DATE,
    origem_informacoes          TEXT,
    observacoes                 TEXT
);

-- Acordos de Leniencia
CREATE TABLE acordo_leniencia (
    id                          SERIAL PRIMARY KEY,
    id_acordo                   TEXT,
    cnpj_sancionado             TEXT,
    razao_social_rfb            TEXT,
    nome_fantasia_rfb           TEXT,
    dt_inicio_acordo            DATE,
    dt_fim_acordo               DATE,
    situacao_acordo             TEXT,
    dt_informacao               DATE,
    numero_processo             TEXT,
    termos_acordo               TEXT,
    orgao_sancionador           TEXT
);

-- Efeitos dos Acordos de Leniencia
CREATE TABLE acordo_efeito (
    id                          SERIAL PRIMARY KEY,
    id_acordo                   TEXT,
    efeito                      TEXT,
    complemento                 TEXT
);
