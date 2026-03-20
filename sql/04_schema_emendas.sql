-- Tabelas de Emendas Parlamentares
-- Fonte: emendas_tesouro.csv, transferegov_convenios.csv, transferegov_favorecidos.csv

DROP TABLE IF EXISTS emenda_tesouro CASCADE;
DROP TABLE IF EXISTS emenda_convenio CASCADE;
DROP TABLE IF EXISTS emenda_favorecido CASCADE;

CREATE TABLE emenda_tesouro (
    id                     SERIAL PRIMARY KEY,
    nome_ente              VARCHAR(200),
    uf                     CHAR(2),
    codigo_siafi           VARCHAR(20),
    codigo_ibge            VARCHAR(20),
    dt_transacao           DATE,
    ano                    SMALLINT,
    mes                    SMALLINT,
    tipo_ente              VARCHAR(50),
    ob                     VARCHAR(30),
    cnpj_favorecido        VARCHAR(14),
    nome_favorecido        VARCHAR(200),
    nome_emenda            VARCHAR(500),
    transferencia_especial VARCHAR(10),
    categoria_economica    VARCHAR(100),
    valor                  DECIMAL(15,2)
);

CREATE TABLE emenda_convenio (
    id               SERIAL PRIMARY KEY,
    codigo_emenda    VARCHAR(20),
    codigo_funcao    VARCHAR(10),
    nome_funcao      VARCHAR(100),
    codigo_subfuncao VARCHAR(10),
    nome_subfuncao   VARCHAR(100),
    localidade_gasto VARCHAR(200),
    tipo_emenda      VARCHAR(100),
    dt_publicacao    DATE,
    convenente       VARCHAR(200),
    objeto           TEXT,
    numero_convenio  VARCHAR(30),
    valor_convenio   DECIMAL(15,2)
);

CREATE TABLE emenda_favorecido (
    id                   SERIAL PRIMARY KEY,
    codigo_emenda        VARCHAR(20),
    codigo_autor         VARCHAR(20),
    nome_autor           VARCHAR(200),
    numero_emenda        VARCHAR(20),
    tipo_emenda          VARCHAR(100),
    ano_mes              VARCHAR(7),
    codigo_favorecido    VARCHAR(14),
    nome_favorecido      VARCHAR(200),
    natureza_juridica    VARCHAR(100),
    tipo_favorecido      VARCHAR(50),
    uf_favorecido        CHAR(2),
    municipio_favorecido VARCHAR(100),
    valor_recebido       DECIMAL(15,2)
);
