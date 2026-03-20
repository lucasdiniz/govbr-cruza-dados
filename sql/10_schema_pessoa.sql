-- Entity Resolution: tabelas para deduplicação de pessoas físicas
-- Populated na Fase 7 do ETL, após carga de sócios, CPGF e emendas

DROP TABLE IF EXISTS pessoa_merge CASCADE;
DROP TABLE IF EXISTS pessoa_observacao CASCADE;
DROP TABLE IF EXISTS pessoa CASCADE;

CREATE TABLE pessoa (
    id               SERIAL PRIMARY KEY,
    nome_normalizado VARCHAR(200) NOT NULL,
    cpf_masked       CHAR(6),
    cpf_completo     CHAR(11),
    criado_em        TIMESTAMP DEFAULT NOW(),
    atualizado_em    TIMESTAMP DEFAULT NOW()
);

CREATE TABLE pessoa_observacao (
    id           SERIAL PRIMARY KEY,
    pessoa_id    INT NOT NULL REFERENCES pessoa(id),
    fonte        VARCHAR(50) NOT NULL,
    fonte_id     VARCHAR(100),
    nome_original VARCHAR(200),
    cpf_raw      VARCHAR(14),
    dados_extra  JSONB,
    importado_em TIMESTAMP DEFAULT NOW()
);

CREATE TABLE pessoa_merge (
    id          SERIAL PRIMARY KEY,
    pessoa_a_id INT NOT NULL REFERENCES pessoa(id),
    pessoa_b_id INT NOT NULL REFERENCES pessoa(id),
    score       DECIMAL(5,4) NOT NULL,
    metodo      VARCHAR(50),
    status      VARCHAR(20) DEFAULT 'pendente',
    decidido_por VARCHAR(50),
    decidido_em TIMESTAMP,
    CHECK (pessoa_a_id < pessoa_b_id)
);
