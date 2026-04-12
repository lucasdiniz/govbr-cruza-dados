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
    ncm_nbs_descricao        TEXT,
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

-- Indices para queries de superfaturamento
CREATE INDEX idx_pncp_item_cnpj_orgao ON pncp_item(cnpj_orgao);
CREATE INDEX idx_pncp_item_controle ON pncp_item(numero_controle_pncp);  -- JOIN com pncp_contratacao (UF, municipio, modalidade)
CREATE INDEX idx_pncp_item_ncm ON pncp_item(ncm_nbs_codigo) WHERE ncm_nbs_codigo IS NOT NULL;
CREATE INDEX idx_pncp_item_descricao_trgm ON pncp_item USING gin (descricao gin_trgm_ops);  -- busca por similaridade textual
CREATE INDEX idx_pncp_item_valor ON pncp_item(valor_unitario_estimado);
CREATE INDEX idx_pncp_item_material ON pncp_item(material_ou_servico);
CREATE INDEX idx_pncp_item_situacao ON pncp_item(situacao_item_nome);  -- filtrar por Homologado vs Em andamento
