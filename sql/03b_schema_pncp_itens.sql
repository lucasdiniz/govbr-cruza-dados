-- Tabela de itens das contratacoes PNCP
-- Fonte: API /api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{seq}/itens
-- Cada item tem descricao, quantidade, valor unitario estimado, unidade de medida

DROP TABLE IF EXISTS pncp_item CASCADE;

CREATE TABLE pncp_item (
    numero_controle_pncp     VARCHAR(50),        -- FK para pncp_contratacao
    numero_item              INTEGER,
    descricao                TEXT,
    material_ou_servico      CHAR(1),             -- M=Material, S=Servico
    valor_unitario_estimado  DECIMAL(15,2),
    valor_total              DECIMAL(15,2),
    quantidade               DECIMAL(15,4),
    unidade_medida           VARCHAR(500),
    orcamento_sigiloso       BOOLEAN,
    criterio_julgamento_nome VARCHAR(100),
    situacao_item_nome       VARCHAR(100),        -- Homologado, Em andamento, etc
    tem_resultado            BOOLEAN,
    ncm_nbs_codigo           VARCHAR(20),         -- NCM/NBS quando disponivel
    ncm_nbs_descricao        VARCHAR(500),
    catalogo                 VARCHAR(100),
    catalogo_codigo_item     VARCHAR(100),
    dt_inclusao              TIMESTAMP,
    dt_atualizacao           TIMESTAMP,
    -- Campos de referencia (enriquecidos no download)
    cnpj_orgao               CHAR(14),
    ano_compra               INTEGER,
    sequencial_compra        INT,
    PRIMARY KEY (numero_controle_pncp, numero_item)
);

-- Indices sao criados apos carga de dados em etl/04b_pncp_itens.py
