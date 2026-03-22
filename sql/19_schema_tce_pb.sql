-- Tabelas TCE-PB - Dados Consolidados
-- Fonte: https://dados-abertos.tce.pb.gov.br/dados-consolidados
-- Categorias: despesas, servidores, licitacoes, receitas (2018-2026)
-- Cobertura: 237 municipios da Paraiba

DROP TABLE IF EXISTS tce_pb_despesa CASCADE;
DROP TABLE IF EXISTS tce_pb_servidor CASCADE;
DROP TABLE IF EXISTS tce_pb_licitacao CASCADE;
DROP TABLE IF EXISTS tce_pb_receita CASCADE;

-- ── Despesas (empenhos/liquidacoes/pagamentos) ──────────────────
-- Max lengths from 2026 data: col1=65, col3=112, col4=94, col8=87, col13=55,
-- col19=77, col21=80, col22=69, col27=168, col29=70, col30=48, col31=84,
-- col32=57, col33=102, col34=60, col35=556, col36=530, col37=348, col38=276, col39=318, col40=302
CREATE TABLE tce_pb_despesa (
    id                          SERIAL PRIMARY KEY,
    municipio                   VARCHAR(100),
    codigo_ug                   VARCHAR(20),
    descricao_ug                TEXT,
    numero_empenho              VARCHAR(100),
    data_empenho                DATE,
    mes                         VARCHAR(20),
    cpf_cnpj                    VARCHAR(20),
    nome_credor                 TEXT,
    valor_empenhado             DECIMAL(15,2),
    valor_liquidado             DECIMAL(15,2),
    valor_pago                  DECIMAL(15,2),
    codigo_unidade_orcamentaria VARCHAR(20),
    descricao_unidade_orcamentaria TEXT,
    codigo_funcao               VARCHAR(50),
    funcao                      VARCHAR(100),
    codigo_subfuncao            VARCHAR(20),
    subfuncao                   VARCHAR(100),
    codigo_programa             VARCHAR(50),
    programa                    TEXT,
    codigo_acao                 VARCHAR(50),
    acao                        TEXT,
    codigo_categoria_economica  VARCHAR(100),
    categoria_economica         VARCHAR(100),
    codigo_natureza             VARCHAR(30),
    grupo_natureza_despesa      VARCHAR(100),
    codigo_modalidade_aplicacao VARCHAR(30),
    modalidade_aplicacao        TEXT,
    codigo_elemento_despesa     VARCHAR(30),
    elemento_despesa            VARCHAR(100),
    codigo_subelemento          VARCHAR(60),
    codigo_subelemento_exibicao VARCHAR(100),
    numero_licitacao            VARCHAR(100),
    modalidade_licitacao        TEXT,
    numero_obra                 VARCHAR(100),
    historico                   TEXT,
    codigo_fonte_recurso        TEXT,
    descricao_fonte_recurso     TEXT,
    ano_fonte                   TEXT,
    co                          TEXT,
    descricao_co                TEXT
);

-- ── Servidores municipais/estaduais PB ──────────────────────────
CREATE TABLE tce_pb_servidor (
    id                          SERIAL PRIMARY KEY,
    municipio                   VARCHAR(100),
    codigo_ug                   VARCHAR(20),
    descricao_ug                TEXT,
    cpf_cnpj                    VARCHAR(20),
    nome_servidor               VARCHAR(300),
    tipo_cargo                  VARCHAR(100),
    descricao_cargo             TEXT,
    valor_vantagem              DECIMAL(15,2),
    data_admissao               DATE,
    matricula                   VARCHAR(30),
    ano_mes                     VARCHAR(10)
);

-- ── Licitacoes ──────────────────────────────────────────────────
CREATE TABLE tce_pb_licitacao (
    id                          SERIAL PRIMARY KEY,
    municipio                   VARCHAR(100),
    codigo_ug                   VARCHAR(20),
    descricao_ug                TEXT,
    numero_licitacao            VARCHAR(100),
    numero_protocolo_tce        VARCHAR(100),
    ano_licitacao               SMALLINT,
    modalidade                  TEXT,
    objeto_licitacao            TEXT,
    data_homologacao            DATE,
    nome_proponente             VARCHAR(300),
    cpf_cnpj_proponente         VARCHAR(20),
    valor_ofertado              DECIMAL(15,2),
    situacao_proposta           VARCHAR(100)
);

-- ── Receitas ────────────────────────────────────────────────────
CREATE TABLE tce_pb_receita (
    id                          SERIAL PRIMARY KEY,
    municipio                   VARCHAR(100),
    codigo_ug                   VARCHAR(20),
    descricao_ug                TEXT,
    mes_ano                     VARCHAR(10),
    ano                         SMALLINT,
    codigo_receita              VARCHAR(30),
    descricao_receita           TEXT,
    tipo_atualizacao_receita    VARCHAR(100),
    valor                       DECIMAL(15,2),
    codigo_fonte_recurso        VARCHAR(30),
    descricao_fonte_recurso     TEXT,
    co                          VARCHAR(30),
    descricao_co                TEXT
);
