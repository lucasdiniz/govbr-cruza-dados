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

-- =============================================
-- Q58: empresas com mesmo endereco na mesma contratacao PNCP
-- Gargalos observados no EXPLAIN:
-- 1) self-join de pncp_contrato por numero_controle_contratacao
-- 2) join de est1 por cnpj_basico + matriz
-- 3) lookup de est2 por UF + endereco normalizado
-- =============================================

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pncp_contrato_contratacao_cnpj_basico
    ON pncp_contrato (numero_controle_contratacao, cnpj_basico_fornecedor)
    WHERE cnpj_basico_fornecedor IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_estab_matriz_cnpj_endereco
    ON estabelecimento (cnpj_basico)
    INCLUDE (cnpj_completo, municipio, uf, logradouro, numero)
    WHERE cnpj_ordem = '0001'
      AND logradouro IS NOT NULL AND logradouro <> ''
      AND numero IS NOT NULL AND numero <> '';

-- Q58 usa JOIN de cnpj_basico::text (RFB = bpchar, PNCP = text).
-- Sem indice por expressao, o planner cai em Seq Scan em estabelecimento/empresa.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_estab_matriz_cnpj_text_endereco
    ON estabelecimento ((cnpj_basico::text))
    INCLUDE (cnpj_completo, municipio, uf, logradouro, numero)
    WHERE cnpj_ordem = '0001'
      AND logradouro IS NOT NULL AND logradouro <> ''
      AND numero IS NOT NULL AND numero <> '';

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_estab_matriz_endereco_norm
    ON estabelecimento (uf, UPPER(TRIM(logradouro)), TRIM(numero), cnpj_basico)
    INCLUDE (cnpj_completo, municipio)
    WHERE cnpj_ordem = '0001'
      AND logradouro IS NOT NULL AND logradouro <> ''
      AND numero IS NOT NULL AND numero <> '';

-- Q58 compara cnpj + endereco normalizado no Merge Join.
-- Ter cnpj e endereco em indices separados ainda deixa o planner fazer Seq Scan
-- completo em estabelecimento; este indice cobre a chave composta real.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_estab_matriz_cnpj_text_endereco_norm
    ON estabelecimento ((cnpj_basico::text), UPPER(TRIM(logradouro)), TRIM(numero), uf)
    INCLUDE (cnpj_completo, municipio)
    WHERE cnpj_ordem = '0001'
      AND logradouro IS NOT NULL AND logradouro <> ''
      AND numero IS NOT NULL AND numero <> '';

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_empresa_cnpj_text_razao
    ON empresa ((cnpj_basico::text))
    INCLUDE (razao_social);

-- Quando a análise restringe Q58 por UF, o planner precisa conseguir começar
-- pelo subconjunto de contratacoes já ordenado por valor e com a chave de join.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pncp_contratacao_uf_valor_numero
    ON pncp_contratacao (uf, valor_estimado DESC, numero_controle_pncp)
    WHERE valor_estimado > 50000;

-- =============================================
-- Q102/Q103/Q107/Q111: cruzamentos dos novos dados PB com sancoes/PGFN/TSE
-- =============================================

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pb_emp_cnpj_data_valor
    ON pb_empenho (cnpj_basico, data_empenho)
    INCLUDE (valor_empenho, exercicio)
    WHERE cnpj_basico IS NOT NULL
      AND valor_empenho > 0;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ceis_cnpj_basico_j
    ON ceis_sancao (LEFT(cpf_cnpj_norm, 8))
    WHERE tipo_pessoa = 'J'
      AND cpf_cnpj_norm IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cnep_cnpj_basico_j
    ON cnep_sancao (LEFT(cpf_cnpj_norm, 8))
    WHERE tipo_pessoa = 'J'
      AND cpf_cnpj_norm IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pgfn_cnpj_basico_digits_j
    ON pgfn_divida (LEFT(REGEXP_REPLACE(cpf_cnpj, '[^0-9]', '', 'g'), 8))
    WHERE tipo_pessoa LIKE '%jur%'
      AND cpf_cnpj IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pgfn_cnpj_basico_norm
    ON pgfn_divida (LEFT(cpf_cnpj_norm, 8))
    WHERE LENGTH(cpf_cnpj_norm) = 14;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tse_receita_uf_doador_left8
    ON tse_receita_candidato (sg_uf, LEFT(cpf_cnpj_doador, 8))
    WHERE cpf_cnpj_doador IS NOT NULL
      AND LENGTH(cpf_cnpj_doador) >= 14;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_socio_tipo_nome_upper_cnpj
    ON socio (tipo_socio, UPPER(TRIM(nome)), cnpj_basico)
    WHERE nome IS NOT NULL;
