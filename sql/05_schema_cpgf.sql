-- Tabela do Cartão de Pagamento do Governo Federal (CPGF)
-- Fonte: cpgf_0..60.csv

DROP TABLE IF EXISTS cpgf_transacao CASCADE;

CREATE TABLE cpgf_transacao (
    id                     SERIAL PRIMARY KEY,
    codigo_orgao_superior  VARCHAR(20),
    nome_orgao_superior    VARCHAR(200),
    codigo_orgao           VARCHAR(20),
    nome_orgao             VARCHAR(200),
    codigo_unidade_gestora VARCHAR(20),
    nome_unidade_gestora   VARCHAR(200),
    ano_extrato            SMALLINT,
    mes_extrato            SMALLINT,
    cpf_portador           VARCHAR(14),
    nome_portador          VARCHAR(200),
    cnpj_cpf_favorecido    VARCHAR(14),
    nome_favorecido        VARCHAR(200),
    tipo_transacao         VARCHAR(100),
    dt_transacao           DATE,
    valor_transacao        DECIMAL(15,2)
);
