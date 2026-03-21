-- Normalização de identificadores (CPF/CNPJ) para facilitar JOINs entre tabelas.
-- Cria coluna _norm com apenas dígitos em cada tabela que tem CPF/CNPJ formatado.
-- Executar APÓS a carga completa dos dados (sem processos de INSERT ativos).

-- =============================================
-- PGFN: cpf_cnpj tem pontuação (84.461.748/0001-81)
-- =============================================
ALTER TABLE pgfn_divida ADD COLUMN IF NOT EXISTS cpf_cnpj_norm TEXT;
UPDATE pgfn_divida SET cpf_cnpj_norm = REGEXP_REPLACE(cpf_cnpj, '[^0-9]', '', 'g')
WHERE cpf_cnpj_norm IS NULL;
CREATE INDEX IF NOT EXISTS idx_pgfn_norm ON pgfn_divida(cpf_cnpj_norm);

-- =============================================
-- CEIS: cpf_cnpj_sancionado pode ter pontuação
-- =============================================
ALTER TABLE ceis_sancao ADD COLUMN IF NOT EXISTS cpf_cnpj_norm TEXT;
UPDATE ceis_sancao SET cpf_cnpj_norm = REGEXP_REPLACE(cpf_cnpj_sancionado, '[^0-9]', '', 'g')
WHERE cpf_cnpj_norm IS NULL;
CREATE INDEX IF NOT EXISTS idx_ceis_norm ON ceis_sancao(cpf_cnpj_norm);

-- =============================================
-- CNEP: cpf_cnpj_sancionado pode ter pontuação
-- =============================================
ALTER TABLE cnep_sancao ADD COLUMN IF NOT EXISTS cpf_cnpj_norm TEXT;
UPDATE cnep_sancao SET cpf_cnpj_norm = REGEXP_REPLACE(cpf_cnpj_sancionado, '[^0-9]', '', 'g')
WHERE cpf_cnpj_norm IS NULL;
CREATE INDEX IF NOT EXISTS idx_cnep_norm ON cnep_sancao(cpf_cnpj_norm);

-- =============================================
-- CEAF: cpf_cnpj_sancionado pode ter pontuação
-- =============================================
ALTER TABLE ceaf_expulsao ADD COLUMN IF NOT EXISTS cpf_cnpj_norm TEXT;
UPDATE ceaf_expulsao SET cpf_cnpj_norm = REGEXP_REPLACE(cpf_cnpj_sancionado, '[^0-9]', '', 'g')
WHERE cpf_cnpj_norm IS NULL;
CREATE INDEX IF NOT EXISTS idx_ceaf_norm ON ceaf_expulsao(cpf_cnpj_norm);

-- =============================================
-- Acordos de Leniência: cnpj_sancionado pode ter pontuação
-- =============================================
ALTER TABLE acordo_leniencia ADD COLUMN IF NOT EXISTS cnpj_norm TEXT;
UPDATE acordo_leniencia SET cnpj_norm = REGEXP_REPLACE(cnpj_sancionado, '[^0-9]', '', 'g')
WHERE cnpj_norm IS NULL;
CREATE INDEX IF NOT EXISTS idx_acordo_norm ON acordo_leniencia(cnpj_norm);

-- =============================================
-- SIAPE: cpf mascarado (***.017.623-**) -> extrair 6 dígitos centrais
-- =============================================
ALTER TABLE siape_cadastro ADD COLUMN IF NOT EXISTS cpf_masked6 TEXT;
UPDATE siape_cadastro SET cpf_masked6 = SUBSTRING(REGEXP_REPLACE(cpf, '[^0-9]', '', 'g'), 1, 6)
WHERE cpf_masked6 IS NULL AND cpf IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_siape_masked6 ON siape_cadastro(cpf_masked6)
WHERE cpf_masked6 IS NOT NULL AND cpf_masked6 != '000000';

-- =============================================
-- CPGF: cpf_portador mascarado -> extrair 6 dígitos centrais
-- =============================================
ALTER TABLE cpgf_transacao ADD COLUMN IF NOT EXISTS cpf_portador_masked6 TEXT;
UPDATE cpgf_transacao SET cpf_portador_masked6 = SUBSTRING(REGEXP_REPLACE(cpf_portador, '[^0-9]', '', 'g'), 1, 6)
WHERE cpf_portador_masked6 IS NULL AND cpf_portador IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_cpgf_masked6 ON cpgf_transacao(cpf_portador_masked6)
WHERE cpf_portador_masked6 IS NOT NULL AND cpf_portador_masked6 != '000000';

-- =============================================
-- Sócio: cpf_cnpj_socio mascarado -> extrair 6 dígitos centrais
-- =============================================
ALTER TABLE socio ADD COLUMN IF NOT EXISTS cpf_cnpj_norm TEXT;
UPDATE socio SET cpf_cnpj_norm = REGEXP_REPLACE(cpf_cnpj_socio, '[^0-9]', '', 'g')
WHERE cpf_cnpj_norm IS NULL AND cpf_cnpj_socio IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_socio_norm ON socio(cpf_cnpj_norm)
WHERE cpf_cnpj_norm IS NOT NULL AND cpf_cnpj_norm != '000000';

-- =============================================
-- Viagem: cpf_viajante mascarado -> extrair 6 dígitos centrais
-- =============================================
ALTER TABLE viagem ADD COLUMN IF NOT EXISTS cpf_viajante_masked6 TEXT;
UPDATE viagem SET cpf_viajante_masked6 = SUBSTRING(REGEXP_REPLACE(cpf_viajante, '[^0-9]', '', 'g'), 1, 6)
WHERE cpf_viajante_masked6 IS NULL AND cpf_viajante IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_viagem_masked6 ON viagem(cpf_viajante_masked6)
WHERE cpf_viajante_masked6 IS NOT NULL AND cpf_viajante_masked6 != '000000';

-- =============================================
-- PNCP contrato: ni_fornecedor já é só dígitos, mas criar cnpj_basico_fornecedor (8 dígitos)
-- para JOIN direto com empresa
-- =============================================
ALTER TABLE pncp_contrato ADD COLUMN IF NOT EXISTS cnpj_basico_fornecedor TEXT;
UPDATE pncp_contrato SET cnpj_basico_fornecedor = LEFT(REGEXP_REPLACE(ni_fornecedor, '[^0-9]', '', 'g'), 8)
WHERE cnpj_basico_fornecedor IS NULL AND ni_fornecedor IS NOT NULL AND LENGTH(ni_fornecedor) >= 8;
CREATE INDEX IF NOT EXISTS idx_pncp_contrato_cnpj_basico ON pncp_contrato(cnpj_basico_fornecedor);

-- =============================================
-- Emenda favorecido: codigo_favorecido já é só dígitos, criar cnpj_basico
-- =============================================
ALTER TABLE emenda_favorecido ADD COLUMN IF NOT EXISTS cnpj_basico_favorecido TEXT;
UPDATE emenda_favorecido SET cnpj_basico_favorecido = LEFT(codigo_favorecido, 8)
WHERE cnpj_basico_favorecido IS NULL AND codigo_favorecido IS NOT NULL AND LENGTH(codigo_favorecido) >= 8;
CREATE INDEX IF NOT EXISTS idx_emfav_cnpj_basico ON emenda_favorecido(cnpj_basico_favorecido);
