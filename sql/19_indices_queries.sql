-- Índices otimizados para as 42 queries de fraude
-- Executar APÓS carga completa e normalização (etl.15_normalizar)

-- =============================================
-- CRÍTICO: LEFT(cnpj, 8) — usado em 10+ queries para JOIN com empresa.cnpj_basico
-- =============================================
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pncp_contrato_forn_left8
    ON pncp_contrato (LEFT(ni_fornecedor, 8));

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_emfav_favorecido_left8
    ON emenda_favorecido (LEFT(codigo_favorecido, 8));

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cpgf_favorecido_left8
    ON cpgf_transacao (LEFT(cnpj_cpf_favorecido, 8));

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_bndes_cnpj_left8
    ON bndes_contrato (LEFT(cnpj, 8));

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pgfn_cpf_cnpj_left8
    ON pgfn_divida (LEFT(cpf_cnpj, 8));

-- =============================================
-- CRÍTICO: UPPER(TRIM(nome)) — usado nas queries de Bolsa Familia (Q38-Q42)
-- =============================================
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_bf_nome_upper
    ON bolsa_familia (UPPER(TRIM(nm_favorecido)));

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_socio_nome_upper
    ON socio (UPPER(TRIM(nome)));

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_siape_nome_upper
    ON siape_cadastro (UPPER(TRIM(nome)));

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cpgf_portador_nome_upper
    ON cpgf_transacao (UPPER(TRIM(nome_portador)));

-- =============================================
-- CRÍTICO: CPF dígitos — para JOINs entre BF/sócio/SIAPE/CPGF/sanções
-- REGEXP_REPLACE não pode ser indexado diretamente, usar colunas desnormalizadas
-- =============================================
-- bolsa_familia: extrair 6 dígitos centrais
ALTER TABLE bolsa_familia ADD COLUMN IF NOT EXISTS cpf_digitos TEXT;
UPDATE bolsa_familia SET cpf_digitos = REGEXP_REPLACE(cpf_favorecido, '[^0-9]', '', 'g')
WHERE cpf_digitos IS NULL AND cpf_favorecido IS NOT NULL AND cpf_favorecido != '';
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_bf_cpf_digitos
    ON bolsa_familia (cpf_digitos);

-- cpgf_transacao: extrair 6 dígitos centrais do cpf_portador
ALTER TABLE cpgf_transacao ADD COLUMN IF NOT EXISTS cpf_portador_digitos TEXT;
UPDATE cpgf_transacao SET cpf_portador_digitos = REGEXP_REPLACE(cpf_portador, '[^0-9]', '', 'g')
WHERE cpf_portador_digitos IS NULL AND cpf_portador IS NOT NULL AND cpf_portador != '';
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cpgf_portador_digitos
    ON cpgf_transacao (cpf_portador_digitos);

-- siape_cadastro: extrair 6 dígitos centrais do cpf
ALTER TABLE siape_cadastro ADD COLUMN IF NOT EXISTS cpf_digitos TEXT;
UPDATE siape_cadastro SET cpf_digitos = REGEXP_REPLACE(cpf, '[^0-9]', '', 'g')
WHERE cpf_digitos IS NULL AND cpf IS NOT NULL AND cpf != '';
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_siape_cpf_digitos
    ON siape_cadastro (cpf_digitos);

-- socio: já tem cpf_cnpj_norm do 15_normalizar, mas garantir índice
-- (15_normalizar já cria idx_socio_norm)

-- sanções: já tem cpf_cnpj_norm do 15_normalizar

-- =============================================
-- ALTO: Datas e filtros compostos
-- =============================================
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pncp_contrato_dt_assinatura
    ON pncp_contrato (dt_assinatura);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cpgf_dt_transacao
    ON cpgf_transacao (dt_transacao);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_viagem_dt_inicio
    ON viagem (dt_inicio);

-- Composite: estabelecimento matriz ativa (usado em Q39 e outras)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_estab_matriz_ativa
    ON estabelecimento (cnpj_basico) WHERE cnpj_ordem = '0001' AND situacao_cadastral = '2';
