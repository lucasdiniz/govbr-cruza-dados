-- Tabelas da Receita Federal do Brasil (CNPJ)
-- Fonte: Empresas*.csv, Estabelecimentos*.csv, Socios*.csv, Simples.csv
-- Tamanhos VARCHAR generosos para acomodar dados inconsistentes da RFB

DROP TABLE IF EXISTS simples CASCADE;
DROP TABLE IF EXISTS socio CASCADE;
DROP TABLE IF EXISTS estabelecimento CASCADE;
DROP TABLE IF EXISTS empresa CASCADE;

CREATE TABLE empresa (
    cnpj_basico          CHAR(8) PRIMARY KEY,
    razao_social         VARCHAR(500) NOT NULL,
    natureza_juridica    VARCHAR(50),
    qualif_responsavel   VARCHAR(50),
    capital_social       DECIMAL(15,2),
    porte                SMALLINT,
    ente_federativo      VARCHAR(200)
);

CREATE TABLE estabelecimento (
    cnpj_basico          CHAR(8) NOT NULL,
    cnpj_ordem           CHAR(4) NOT NULL,
    cnpj_dv              CHAR(2) NOT NULL,
    cnpj_completo        CHAR(14) GENERATED ALWAYS AS
        (cnpj_basico || cnpj_ordem || cnpj_dv) STORED,
    matriz_filial        SMALLINT,
    nome_fantasia        VARCHAR(500),
    situacao_cadastral   SMALLINT,
    dt_situacao          DATE,
    motivo_situacao      VARCHAR(50),
    nome_cidade_exterior VARCHAR(200),
    pais                 VARCHAR(50),
    dt_inicio_atividade  DATE,
    cnae_principal       VARCHAR(7),
    cnae_secundaria      TEXT,
    tipo_logradouro      VARCHAR(50),
    logradouro           VARCHAR(500),
    numero               VARCHAR(20),
    complemento          VARCHAR(500),
    bairro               VARCHAR(200),
    cep                  CHAR(8),
    uf                   CHAR(2),
    municipio            VARCHAR(10),
    ddd1                 VARCHAR(5),
    telefone1            VARCHAR(20),
    ddd2                 VARCHAR(5),
    telefone2            VARCHAR(20),
    ddd_fax              VARCHAR(5),
    fax                  VARCHAR(20),
    email                VARCHAR(500),
    situacao_especial    VARCHAR(500),
    dt_situacao_especial DATE,
    PRIMARY KEY (cnpj_basico, cnpj_ordem, cnpj_dv)
);

CREATE TABLE socio (
    id                   SERIAL PRIMARY KEY,
    cnpj_basico          CHAR(8) NOT NULL,
    tipo_socio           SMALLINT,
    nome                 VARCHAR(500),
    cpf_cnpj_socio       VARCHAR(50),
    qualificacao         VARCHAR(50),
    dt_entrada           DATE,
    pais                 VARCHAR(50),
    cpf_representante    VARCHAR(50),
    nome_representante   VARCHAR(500),
    qualif_representante VARCHAR(50),
    faixa_etaria         SMALLINT
);

CREATE TABLE simples (
    cnpj_basico          CHAR(8) PRIMARY KEY,
    opcao_simples        CHAR(1),
    dt_opcao_simples     DATE,
    dt_exclusao_simples  DATE,
    opcao_mei            CHAR(1),
    dt_opcao_mei         DATE,
    dt_exclusao_mei      DATE
);
