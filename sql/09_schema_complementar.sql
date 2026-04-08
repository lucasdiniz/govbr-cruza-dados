-- Tabelas complementares: BNDES, Holdings, ComprasNet
-- Fonte: bndes.csv, holding.csv, comprasnet.csv

DROP TABLE IF EXISTS bndes_contrato CASCADE;
DROP TABLE IF EXISTS holding_vinculo CASCADE;
DROP TABLE IF EXISTS comprasnet_contrato CASCADE;

CREATE TABLE bndes_contrato (
    id                      SERIAL PRIMARY KEY,
    cliente                 TEXT,
    cnpj                    VARCHAR(20),
    descricao_projeto       TEXT,
    uf                      VARCHAR(20),
    municipio               TEXT,
    municipio_codigo        VARCHAR(20),
    numero_contrato         VARCHAR(50),
    dt_contratacao          DATE,
    valor_contratado        DECIMAL(20,2),
    valor_desembolsado      DECIMAL(20,2),
    fonte_recurso           TEXT,
    custo_financeiro        TEXT,
    juros                   TEXT,
    prazo_carencia_meses    INT,
    prazo_amortizacao_meses INT,
    modalidade_apoio        TEXT,
    forma_apoio             TEXT,
    produto                 TEXT,
    instrumento_financeiro  TEXT,
    inovacao                TEXT,
    area_operacional        TEXT,
    setor_cnae              TEXT,
    subsetor_cnae           TEXT,
    subsetor_cnae_codigo    VARCHAR(20),
    setor_bndes             TEXT,
    subsetor_bndes          TEXT,
    porte_cliente           TEXT,
    natureza_cliente        TEXT,
    instituicao_credenciada TEXT,
    cnpj_instituicao        VARCHAR(20),
    tipo_garantia           TEXT,
    tipo_excepcionalidade   TEXT,
    situacao_contrato       TEXT
);

CREATE TABLE holding_vinculo (
    id                       SERIAL PRIMARY KEY,
    holding_cnpj             VARCHAR(14) NOT NULL,
    holding_razao_social     VARCHAR(200),
    cnpj_subsidiaria         VARCHAR(14) NOT NULL,
    razao_social_subsidiaria VARCHAR(200),
    codigo_qualificacao      VARCHAR(5),
    qualificacao             VARCHAR(100)
);

CREATE TABLE comprasnet_contrato (
    id_comprasnet           INT,
    receita_despesa         VARCHAR(10),
    numero                  VARCHAR(30),
    orgao_codigo            VARCHAR(20),
    orgao_nome              VARCHAR(200),
    unidade_codigo          VARCHAR(20),
    esfera                  VARCHAR(20),
    poder                   VARCHAR(20),
    sisg                    VARCHAR(5),
    gestao                  VARCHAR(20),
    unidade_nome_resumido   VARCHAR(200),
    unidade_nome            VARCHAR(200),
    unidade_origem_codigo   VARCHAR(20),
    unidade_origem_nome     VARCHAR(200),
    fornecedor_tipo         VARCHAR(20),
    fornecedor_cnpj_cpf     VARCHAR(20),
    fornecedor_nome         VARCHAR(200),
    codigo_tipo             VARCHAR(10),
    tipo                    VARCHAR(100),
    categoria               VARCHAR(100),
    processo                VARCHAR(50),
    objeto                  TEXT,
    fundamento_legal        TEXT,
    informacao_complementar TEXT,
    codigo_modalidade       VARCHAR(10),
    modalidade              VARCHAR(100),
    unidade_compra          VARCHAR(20),
    licitacao_numero        VARCHAR(30),
    dt_assinatura           DATE,
    dt_publicacao           DATE,
    vigencia_inicio         DATE,
    vigencia_fim            DATE,
    valor_inicial           DECIMAL(15,2),
    valor_global            DECIMAL(15,2),
    num_parcelas            INT,
    valor_parcela           DECIMAL(15,2),
    valor_acumulado         DECIMAL(15,2),
    situacao                VARCHAR(50)
);
