-- Tabela de Dívida Ativa da União (PGFN)
-- Fonte: pgfn_0..5.csv

DROP TABLE IF EXISTS pgfn_divida CASCADE;

CREATE TABLE pgfn_divida (
    id                      SERIAL PRIMARY KEY,
    cpf_cnpj                VARCHAR(14) NOT NULL,
    tipo_pessoa             VARCHAR(30),
    tipo_devedor            VARCHAR(30),
    nome_devedor            VARCHAR(200),
    uf_devedor              CHAR(2),
    unidade_responsavel     VARCHAR(200),
    numero_inscricao        VARCHAR(30),
    tipo_situacao_inscricao VARCHAR(100),
    situacao_inscricao      VARCHAR(100),
    receita_principal       VARCHAR(200),
    dt_inscricao            DATE,
    indicador_ajuizado      VARCHAR(5),
    valor_consolidado       DECIMAL(15,2)
);
