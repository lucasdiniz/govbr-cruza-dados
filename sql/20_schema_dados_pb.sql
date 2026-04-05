-- Tabelas dados.pb.gov.br - Dados estaduais da Paraiba
-- Fonte: https://dados.pb.gov.br/app/
-- API: https://dados.pb.gov.br:443/getcsv?nome={dataset}&exercicio={ano}&mes={mes}
-- 5 datasets: pagamento, empenho, contratos, saude, convenios (2018-2026)

DROP TABLE IF EXISTS pb_pagamento CASCADE;
DROP TABLE IF EXISTS pb_empenho CASCADE;
DROP TABLE IF EXISTS pb_contrato CASCADE;
DROP TABLE IF EXISTS pb_saude CASCADE;
DROP TABLE IF EXISTS pb_convenio CASCADE;
DROP TABLE IF EXISTS pb_pagamento_anulacao CASCADE;
DROP TABLE IF EXISTS pb_liquidacao_despesa CASCADE;
DROP TABLE IF EXISTS pb_liquidacao_desconto CASCADE;
DROP TABLE IF EXISTS pb_empenho_anulacao CASCADE;
DROP TABLE IF EXISTS pb_empenho_suplementacao CASCADE;
DROP TABLE IF EXISTS pb_dotacao CASCADE;
DROP TABLE IF EXISTS pb_liquidacao_cge CASCADE;
DROP TABLE IF EXISTS pb_aditivo_contrato CASCADE;
DROP TABLE IF EXISTS pb_aditivo_convenio CASCADE;
DROP TABLE IF EXISTS pb_diaria CASCADE;
DROP TABLE IF EXISTS pb_unidade_gestora CASCADE;

-- ── Pagamentos estaduais (autorizacoes de pagamento) ──────────
-- ~5M registros. CPF COMPLETO + CNPJ do credor.
CREATE TABLE pb_pagamento (
    id                          SERIAL PRIMARY KEY,
    exercicio                   SMALLINT,
    codigo_unidade_gestora      VARCHAR(10),
    numero_empenho              VARCHAR(20),
    numero_autorizacao_pagamento VARCHAR(20),
    tipo_despesa                VARCHAR(50),
    data_pagamento              DATE,
    valor_pagamento             DECIMAL(15,2),
    codigo_tipo_documento       VARCHAR(10),
    descricao_tipo_documento    VARCHAR(100),
    nome_credor                 TEXT,
    cpfcnpj_credor              VARCHAR(20),
    tipo_credor                 VARCHAR(30)
);

-- ── Empenhos originais (notas de empenho) ─────────────────────
-- ~2.3M registros. CNPJ completo (PJ), CPF mascarado (PF). 41 colunas.
CREATE TABLE pb_empenho (
    id                              SERIAL PRIMARY KEY,
    exercicio                       SMALLINT,
    codigo_unidade_gestora          VARCHAR(10),
    numero_empenho                  VARCHAR(10),
    numero_empenho_origem           VARCHAR(10),
    data_empenho                    DATE,
    historico_empenho               TEXT,
    codigo_situacao_empenho         VARCHAR(5),
    codigo_tipo_empenho             VARCHAR(5),
    descricao_tipo_empenho          VARCHAR(50),
    nome_situacao_empenho           VARCHAR(50),
    valor_empenho                   DECIMAL(15,2),
    codigo_modalidade_licitacao     VARCHAR(5),
    codigo_motivo_dispensa_licitacao VARCHAR(5),
    codigo_tipo_credito             VARCHAR(5),
    nome_tipo_credito               VARCHAR(20),
    destino_diarias                 TEXT,
    data_saida_diarias              DATE,
    data_chegada_diarias            DATE,
    nome_credor                     TEXT,
    cpfcnpj_credor                  VARCHAR(20),
    tipo_credor                     VARCHAR(20),
    codigo_municipio                VARCHAR(10),
    nome_municipio                  VARCHAR(40),
    numero_processo_pagamento       VARCHAR(30),
    numero_contrato                 VARCHAR(20),
    codigo_unidade_orcamentaria     VARCHAR(10),
    codigo_funcao                   VARCHAR(5),
    codigo_subfuncao                VARCHAR(5),
    codigo_programa                 VARCHAR(10),
    codigo_acao                     VARCHAR(10),
    codigo_fonte_recurso            VARCHAR(10),
    codigo_natureza_despesa         VARCHAR(10),
    codigo_categoria_economica_despesa VARCHAR(5),
    codigo_grupo_natureza_despesa   VARCHAR(5),
    codigo_modalidade_aplicacao_despesa VARCHAR(5),
    codigo_elemento_despesa         VARCHAR(5),
    codigo_item_despesa             VARCHAR(5),
    codigo_finalidade_fixacao       VARCHAR(20),
    nome_finalidade_fixacao         TEXT,
    codigo_licitacao                VARCHAR(30),
    orcamento_democratico           VARCHAR(5)
);

-- ── Contratos estaduais ───────────────────────────────────────
-- ~11k registros. CNPJ/CPF contratado, objeto, valor, processo licitatorio.
CREATE TABLE pb_contrato (
    id                              SERIAL PRIMARY KEY,
    codigo_contrato                 VARCHAR(20),
    numero_registro_cge             VARCHAR(30),
    numero_contrato                 VARCHAR(50),
    nome_contratante                TEXT,
    numero_processo_licitatorio     VARCHAR(50),
    objeto_contrato                 TEXT,
    complemento_objeto_contrato     TEXT,
    nome_contratado                 TEXT,
    cpfcnpj_contratado              VARCHAR(20),
    data_celebracao_contrato        DATE,
    data_publicacao                 DATE,
    data_inicio_vigencia            DATE,
    data_termino_vigencia           DATE,
    valor_original                  DECIMAL(15,2),
    nome_municipio                  VARCHAR(100),
    outros_municipios               TEXT,
    nome_gestor_contrato            TEXT,
    numero_portaria                 VARCHAR(50),
    data_publicacao_portaria        DATE,
    url_contrato                    TEXT
);

-- ── Pagamentos gestao pactuada saude ──────────────────────────
-- ~50k registros. CNPJ credor, nota fiscal, categoria despesa.
CREATE TABLE pb_saude (
    id                              SERIAL PRIMARY KEY,
    codigo_envio                    VARCHAR(20),
    competencia                     VARCHAR(20),
    codigo_organizacao_social       VARCHAR(10),
    nome_organizacao_social         TEXT,
    codigo_lancamento               VARCHAR(20),
    data_lancamento                 DATE,
    numero_documento                VARCHAR(100),
    tipo_documento                  VARCHAR(10),
    numero_processo                 VARCHAR(100),
    codigo_categoria_despesa        VARCHAR(10),
    nome_categoria_despesa          TEXT,
    cpfcnpj_credor                  VARCHAR(20),
    nome_credor                     TEXT,
    valor_lancamento                DECIMAL(15,2),
    observacao_lancamento           TEXT
);

-- ── Convenios estado-municipios ───────────────────────────────
-- ~9k registros. CNPJ convenente, objetivo, valores.
CREATE TABLE pb_convenio (
    id                              SERIAL PRIMARY KEY,
    codigo_convenio                 VARCHAR(20),
    numero_registro_cge             VARCHAR(30),
    numero_convenio                 VARCHAR(50),
    nome_concedente                 TEXT,
    nome_convenente                 TEXT,
    cnpj_convenente                 VARCHAR(20),
    nome_municipio                  VARCHAR(100),
    objetivo_convenio               TEXT,
    complemento_objeto_convenio     TEXT,
    data_celebracao_convenio        DATE,
    data_publicacao                 DATE,
    valor_concedente                DECIMAL(15,2),
    valor_contrapartida             DECIMAL(15,2),
    data_inicio_vigencia            DATE,
    data_termino_vigencia           DATE,
    url_convenio                    TEXT
);

-- Novos datasets mensais/anuais adicionados ao download de dados.pb.gov.br

CREATE TABLE pb_pagamento_anulacao (
    id                              SERIAL PRIMARY KEY,
    exercicio                       SMALLINT,
    codigo_unidade_gestora          VARCHAR(10),
    numero_empenho                  VARCHAR(20),
    numero_guia_devolucao           VARCHAR(20),
    numero_autorizacao_pagamento    VARCHAR(20),
    data_documento                  DATE,
    valor_documento                 DECIMAL(15,2),
    codigo_tipo_documento           VARCHAR(10),
    descricao_tipo_documento        TEXT
);

CREATE TABLE pb_liquidacao_despesa (
    id                              SERIAL PRIMARY KEY,
    exercicio                       SMALLINT,
    data_movimentacao               DATE,
    codigo_orgao                    VARCHAR(10),
    numero_empenho                  VARCHAR(20),
    documento                       VARCHAR(20),
    documento_origem                VARCHAR(20),
    ano_documento_origem            SMALLINT,
    tipo_liquidacao                 VARCHAR(10),
    codigo_credor                   VARCHAR(20),
    cpfcnpj_credor                  VARCHAR(20),
    tipo_documento_fiscal           VARCHAR(10),
    numero_nota_fiscal              VARCHAR(50),
    data_nota_fiscal                DATE,
    codigo_inscricao_rp             VARCHAR(20),
    ano_inscricao_rp                SMALLINT,
    codigo_orgao_extinto            VARCHAR(10),
    valor_liquidacao                DECIMAL(15,2)
);

CREATE TABLE pb_liquidacao_desconto (
    id                              SERIAL PRIMARY KEY,
    exercicio                       SMALLINT,
    codigo_orgao                    VARCHAR(10),
    numero_empenho                  VARCHAR(20),
    numero_documento                VARCHAR(20),
    data_pagamento                  DATE,
    tipo_pagamento                  VARCHAR(10),
    codigo_desconto                 VARCHAR(10),
    descricao_desconto              TEXT,
    codigo_orgao_pagamento          VARCHAR(10),
    valor_desconto                  DECIMAL(15,2)
);

CREATE TABLE pb_empenho_anulacao (
    id                              SERIAL PRIMARY KEY,
    exercicio                       SMALLINT,
    codigo_unidade_gestora          VARCHAR(10),
    numero_empenho                  VARCHAR(20),
    numero_empenho_origem           VARCHAR(20),
    data_empenho                    DATE,
    historico_empenho               TEXT,
    codigo_situacao_empenho         VARCHAR(5),
    codigo_tipo_empenho             VARCHAR(5),
    descricao_tipo_empenho          VARCHAR(50),
    nome_situacao_empenho           VARCHAR(80),
    valor_empenho                   DECIMAL(15,2),
    codigo_modalidade_licitacao     VARCHAR(5),
    codigo_motivo_dispensa_licitacao VARCHAR(5),
    codigo_tipo_credito             VARCHAR(5),
    nome_tipo_credito               VARCHAR(30),
    destino_diarias                 TEXT,
    data_saida_diarias              DATE,
    data_chegada_diarias            DATE,
    nome_credor                     TEXT,
    cpfcnpj_credor                  VARCHAR(20),
    tipo_credor                     VARCHAR(20),
    codigo_municipio                VARCHAR(10),
    nome_municipio                  VARCHAR(100),
    numero_processo_pagamento       VARCHAR(30),
    numero_contrato                 VARCHAR(20),
    codigo_unidade_orcamentaria     VARCHAR(10),
    codigo_funcao                   VARCHAR(5),
    codigo_subfuncao                VARCHAR(5),
    codigo_programa                 VARCHAR(10),
    codigo_acao                     VARCHAR(10),
    codigo_fonte_recurso            VARCHAR(10),
    codigo_natureza_despesa         VARCHAR(10),
    codigo_categoria_economica_despesa VARCHAR(5),
    codigo_grupo_natureza_despesa   VARCHAR(5),
    codigo_modalidade_aplicacao_despesa VARCHAR(5),
    codigo_elemento_despesa         VARCHAR(5),
    codigo_item_despesa             VARCHAR(5)
);

CREATE TABLE pb_empenho_suplementacao (
    id                              SERIAL PRIMARY KEY,
    exercicio                       SMALLINT,
    codigo_unidade_gestora          VARCHAR(10),
    numero_empenho                  VARCHAR(20),
    numero_empenho_origem           VARCHAR(20),
    data_empenho                    DATE,
    historico_empenho               TEXT,
    codigo_situacao_empenho         VARCHAR(5),
    codigo_tipo_empenho             VARCHAR(5),
    descricao_tipo_empenho          VARCHAR(50),
    nome_situacao_empenho           VARCHAR(80),
    valor_empenho                   DECIMAL(15,2),
    codigo_modalidade_licitacao     VARCHAR(5),
    codigo_motivo_dispensa_licitacao VARCHAR(5),
    codigo_tipo_credito             VARCHAR(5),
    nome_tipo_credito               VARCHAR(30),
    destino_diarias                 TEXT,
    data_saida_diarias              DATE,
    data_chegada_diarias            DATE,
    nome_credor                     TEXT,
    cpfcnpj_credor                  VARCHAR(20),
    tipo_credor                     VARCHAR(20),
    codigo_municipio                VARCHAR(10),
    nome_municipio                  VARCHAR(100),
    numero_processo_pagamento       VARCHAR(30),
    numero_contrato                 VARCHAR(20),
    codigo_unidade_orcamentaria     VARCHAR(10),
    codigo_funcao                   VARCHAR(5),
    codigo_subfuncao                VARCHAR(5),
    codigo_programa                 VARCHAR(10),
    codigo_acao                     VARCHAR(10),
    codigo_fonte_recurso            VARCHAR(10),
    codigo_natureza_despesa         VARCHAR(10),
    codigo_categoria_economica_despesa VARCHAR(5),
    codigo_grupo_natureza_despesa   VARCHAR(5),
    codigo_modalidade_aplicacao_despesa VARCHAR(5),
    codigo_elemento_despesa         VARCHAR(5),
    codigo_item_despesa             VARCHAR(5)
);

CREATE TABLE pb_dotacao (
    id                              SERIAL PRIMARY KEY,
    codigo_unidade_gestora          VARCHAR(10),
    exercicio                       SMALLINT,
    codigo_unidade_orcamentaria     VARCHAR(10),
    codigo_funcao                   VARCHAR(5),
    codigo_subfuncao                VARCHAR(5),
    codigo_programa                 VARCHAR(10),
    codigo_acao                     VARCHAR(10),
    meta                            VARCHAR(20),
    localidade                      VARCHAR(20),
    categoria                       VARCHAR(5),
    grupo_despesa                   VARCHAR(5),
    modalidade                      VARCHAR(5),
    elemento_despesa                VARCHAR(5),
    fonte_recurso                   VARCHAR(10),
    valor_orcado                    DECIMAL(15,2)
);

CREATE TABLE pb_liquidacao_cge (
    id                              SERIAL PRIMARY KEY,
    exercicio                       SMALLINT,
    codigo_orgao                    VARCHAR(10),
    numero_classificacao            VARCHAR(20),
    codigo_unidade                  VARCHAR(10),
    codigo_funcao                   VARCHAR(5),
    codigo_subfuncao                VARCHAR(5),
    codigo_programa                 VARCHAR(10),
    codigo_projeto_atividade        VARCHAR(10),
    meta                            VARCHAR(20),
    localidade                      VARCHAR(20),
    codigo_natureza                 VARCHAR(10),
    codigo_fonte                    VARCHAR(10),
    valor                           DECIMAL(15,2),
    numero_empenho                  VARCHAR(20),
    documento                       VARCHAR(20),
    tipo_liquidacao                 VARCHAR(10),
    tipo_documento_fiscal           VARCHAR(10),
    numero_nota_fiscal              VARCHAR(50),
    data_nota_fiscal                DATE,
    data_movimentacao               DATE,
    data_processo                   DATE,
    data_atualizacao                DATE,
    usuario_atualizacao             VARCHAR(50),
    documento_origem                VARCHAR(20),
    codigo_inscricao_rp             VARCHAR(20),
    ano_inscricao_rp                SMALLINT,
    ano_documento_origem            SMALLINT
);

CREATE TABLE pb_aditivo_contrato (
    id                              SERIAL PRIMARY KEY,
    codigo_aditivo_contrato         VARCHAR(20),
    codigo_contrato                 VARCHAR(20),
    motivo_aditivacao               TEXT,
    numero_aditivo_contrato         VARCHAR(20),
    data_inicio_vigencia            DATE,
    data_termino_vigencia           DATE,
    valor_aditivo                   DECIMAL(15,2),
    objeto_aditivo                  TEXT,
    data_celebracao_aditivo         DATE,
    data_publicacao                 DATE,
    data_republicacao               DATE,
    url_aditivo_contrato            TEXT
);

CREATE TABLE pb_aditivo_convenio (
    id                              SERIAL PRIMARY KEY,
    codigo_aditivo_convenio         VARCHAR(20),
    codigo_convenio                 VARCHAR(20),
    motivo_aditivacao               TEXT,
    numero_aditivo_convenio         VARCHAR(20),
    data_inicio_vigencia            DATE,
    data_termino_vigencia           DATE,
    valor_concedente                DECIMAL(15,2),
    valor_convenente                DECIMAL(15,2),
    objeto_aditivo                  TEXT,
    data_celebracao_aditivo         DATE,
    data_publicacao                 DATE,
    data_republicacao               DATE,
    url_aditivo_convenio            TEXT
);

CREATE TABLE pb_diaria (
    id                              SERIAL PRIMARY KEY,
    exercicio                       SMALLINT,
    codigo_unidade_gestora          VARCHAR(10),
    numero_empenho                  VARCHAR(20),
    numero_empenho_origem           VARCHAR(20),
    data_empenho                    DATE,
    historico_empenho               TEXT,
    codigo_situacao_empenho         VARCHAR(5),
    codigo_tipo_empenho             VARCHAR(5),
    descricao_tipo_empenho          VARCHAR(50),
    nome_situacao_empenho           VARCHAR(80),
    valor_empenho                   DECIMAL(15,2),
    codigo_modalidade_licitacao     VARCHAR(5),
    codigo_motivo_dispensa_licitacao VARCHAR(5),
    codigo_tipo_credito             VARCHAR(5),
    nome_tipo_credito               VARCHAR(30),
    destino_diarias                 TEXT,
    data_saida_diarias              DATE,
    data_chegada_diarias            DATE,
    nome_credor                     TEXT,
    cpfcnpj_credor                  VARCHAR(20),
    tipo_credor                     VARCHAR(20),
    codigo_municipio                VARCHAR(10),
    nome_municipio                  VARCHAR(100),
    numero_processo_pagamento       VARCHAR(30),
    numero_contrato                 VARCHAR(20),
    codigo_unidade_orcamentaria     VARCHAR(10),
    codigo_funcao                   VARCHAR(5),
    codigo_subfuncao                VARCHAR(5),
    codigo_programa                 VARCHAR(10),
    codigo_acao                     VARCHAR(10),
    codigo_fonte_recurso            VARCHAR(10),
    codigo_natureza_despesa         VARCHAR(10),
    codigo_categoria_economica_despesa VARCHAR(5),
    codigo_grupo_natureza_despesa   VARCHAR(5),
    codigo_modalidade_aplicacao_despesa VARCHAR(5),
    codigo_elemento_despesa         VARCHAR(5),
    codigo_item_despesa             VARCHAR(5)
);

CREATE TABLE pb_unidade_gestora (
    id                              SERIAL PRIMARY KEY,
    exercicio                       SMALLINT,
    codigo_unidade_gestora          VARCHAR(10),
    sigla_unidade_gestora           VARCHAR(40),
    nome_unidade_gestora            TEXT,
    tipo_administracao              VARCHAR(5)
);
