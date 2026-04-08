-- Tabela do Cartão de Pagamento do Governo Federal (CPGF)
-- Fonte: cpgf_0..60.csv

DROP TABLE IF EXISTS cpgf_transacao CASCADE;

CREATE TABLE cpgf_transacao (
    id                     SERIAL PRIMARY KEY,
    codigo_orgao_superior  VARCHAR(20),
    nome_orgao_superior    TEXT,
    codigo_orgao           VARCHAR(20),
    nome_orgao             TEXT,
    codigo_unidade_gestora VARCHAR(20),
    nome_unidade_gestora   TEXT,
    ano_extrato            SMALLINT,
    mes_extrato            SMALLINT,
    cpf_portador           VARCHAR(14),
    nome_portador          TEXT,
    cnpj_cpf_favorecido    VARCHAR(14),
    nome_favorecido        TEXT,
    tipo_transacao         TEXT,
    dt_transacao           DATE,
    valor_transacao        DECIMAL(15,2)
);
