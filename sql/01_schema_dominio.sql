-- Tabelas de domínio (lookup tables) da Receita Federal
-- Fonte: arquivos Cnaes.csv, Municipios.csv, Naturezas.csv, Paises.csv, Qualificacoes.csv, Motivos.csv

DROP TABLE IF EXISTS dom_cnae CASCADE;
CREATE TABLE dom_cnae (
    codigo    VARCHAR(7) PRIMARY KEY,
    descricao VARCHAR(200)
);

DROP TABLE IF EXISTS dom_municipio CASCADE;
CREATE TABLE dom_municipio (
    codigo    VARCHAR(4) PRIMARY KEY,
    descricao VARCHAR(200)
);

DROP TABLE IF EXISTS dom_natureza_juridica CASCADE;
CREATE TABLE dom_natureza_juridica (
    codigo    VARCHAR(4) PRIMARY KEY,
    descricao VARCHAR(200)
);

DROP TABLE IF EXISTS dom_pais CASCADE;
CREATE TABLE dom_pais (
    codigo    VARCHAR(3) PRIMARY KEY,
    descricao VARCHAR(200)
);

DROP TABLE IF EXISTS dom_qualificacao CASCADE;
CREATE TABLE dom_qualificacao (
    codigo    VARCHAR(10) PRIMARY KEY,
    descricao VARCHAR(200)
);

DROP TABLE IF EXISTS dom_motivo CASCADE;
CREATE TABLE dom_motivo (
    codigo    VARCHAR(10) PRIMARY KEY,
    descricao VARCHAR(200)
);
