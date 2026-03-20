-- Índices criados APÓS a carga completa dos dados (Fase 6)
-- Criar índices depois da carga é significativamente mais rápido

-- =============================================
-- RFB: Empresa
-- =============================================
CREATE INDEX idx_empresa_razao ON empresa USING gin(razao_social gin_trgm_ops);
CREATE INDEX idx_empresa_porte ON empresa(porte);
CREATE INDEX idx_empresa_natureza ON empresa(natureza_juridica);

-- =============================================
-- RFB: Estabelecimento
-- =============================================
CREATE INDEX idx_estab_cnpj_completo ON estabelecimento(cnpj_completo);
CREATE INDEX idx_estab_cnpj_basico ON estabelecimento(cnpj_basico);
CREATE INDEX idx_estab_uf ON estabelecimento(uf);
CREATE INDEX idx_estab_municipio ON estabelecimento(municipio);
CREATE INDEX idx_estab_cnae ON estabelecimento(cnae_principal);
CREATE INDEX idx_estab_situacao ON estabelecimento(situacao_cadastral);
CREATE INDEX idx_estab_dt_inicio ON estabelecimento(dt_inicio_atividade);

-- =============================================
-- RFB: Sócio
-- =============================================
CREATE INDEX idx_socio_cnpj_basico ON socio(cnpj_basico);
-- Partial index: exclui CPFs invalidos/mascarados zerados (~40% dos registros)
CREATE INDEX idx_socio_cpf_cnpj ON socio(cpf_cnpj_socio)
    WHERE cpf_cnpj_socio IS NOT NULL AND cpf_cnpj_socio NOT IN ('***000000**', '');
CREATE INDEX idx_socio_nome ON socio USING gin(nome gin_trgm_ops)
    WHERE nome IS NOT NULL;
CREATE INDEX idx_socio_tipo ON socio(tipo_socio);

-- =============================================
-- PNCP: Contratação
-- =============================================
CREATE INDEX idx_pncp_contratacao_cnpj ON pncp_contratacao(cnpj_orgao);
CREATE INDEX idx_pncp_contratacao_uf ON pncp_contratacao(uf);
CREATE INDEX idx_pncp_contratacao_modalidade ON pncp_contratacao(modalidade_id);
CREATE INDEX idx_pncp_contratacao_dt_pub ON pncp_contratacao(dt_publicacao_pncp);
CREATE INDEX idx_pncp_contratacao_valor ON pncp_contratacao(valor_estimado);
CREATE INDEX idx_pncp_contratacao_objeto ON pncp_contratacao USING gin(objeto gin_trgm_ops);

-- =============================================
-- PNCP: Contrato
-- =============================================
CREATE INDEX idx_pncp_contrato_contratacao ON pncp_contrato(numero_controle_contratacao);
CREATE INDEX idx_pncp_contrato_fornecedor ON pncp_contrato(ni_fornecedor);
CREATE INDEX idx_pncp_contrato_cnpj_orgao ON pncp_contrato(cnpj_orgao);
CREATE INDEX idx_pncp_contrato_dt_assinatura ON pncp_contrato(dt_assinatura);
CREATE INDEX idx_pncp_contrato_valor ON pncp_contrato(valor_global);
CREATE INDEX idx_pncp_contrato_nome_forn ON pncp_contrato USING gin(nome_fornecedor gin_trgm_ops);

-- =============================================
-- Emendas: Tesouro
-- =============================================
CREATE INDEX idx_emenda_tes_cnpj ON emenda_tesouro(cnpj_favorecido);
CREATE INDEX idx_emenda_tes_uf ON emenda_tesouro(uf);
CREATE INDEX idx_emenda_tes_ano ON emenda_tesouro(ano);
CREATE INDEX idx_emenda_tes_valor ON emenda_tesouro(valor);
CREATE INDEX idx_emenda_tes_nome ON emenda_tesouro USING gin(nome_emenda gin_trgm_ops);

-- =============================================
-- Emendas: Convênio
-- =============================================
CREATE INDEX idx_emconv_codigo ON emenda_convenio(codigo_emenda);
CREATE INDEX idx_emconv_convenente ON emenda_convenio USING gin(convenente gin_trgm_ops);

-- =============================================
-- Emendas: Favorecido
-- =============================================
CREATE INDEX idx_emfav_codigo ON emenda_favorecido(codigo_emenda);
CREATE INDEX idx_emfav_autor ON emenda_favorecido(codigo_autor);
CREATE INDEX idx_emfav_favorecido ON emenda_favorecido(codigo_favorecido);
CREATE INDEX idx_emfav_uf ON emenda_favorecido(uf_favorecido);
CREATE INDEX idx_emfav_valor ON emenda_favorecido(valor_recebido);

-- =============================================
-- CPGF
-- =============================================
CREATE INDEX idx_cpgf_favorecido ON cpgf_transacao(cnpj_cpf_favorecido);
CREATE INDEX idx_cpgf_portador ON cpgf_transacao(cpf_portador);
CREATE INDEX idx_cpgf_orgao ON cpgf_transacao(codigo_unidade_gestora);
CREATE INDEX idx_cpgf_dt ON cpgf_transacao(dt_transacao);
CREATE INDEX idx_cpgf_valor ON cpgf_transacao(valor_transacao);
CREATE INDEX idx_cpgf_ano_mes ON cpgf_transacao(ano_extrato, mes_extrato);

-- =============================================
-- PGFN
-- =============================================
CREATE INDEX idx_pgfn_cpf_cnpj ON pgfn_divida(cpf_cnpj);
CREATE INDEX idx_pgfn_valor ON pgfn_divida(valor_consolidado);
CREATE INDEX idx_pgfn_situacao ON pgfn_divida(tipo_situacao_inscricao);
CREATE INDEX idx_pgfn_uf ON pgfn_divida(uf_devedor);
CREATE INDEX idx_pgfn_nome ON pgfn_divida USING gin(nome_devedor gin_trgm_ops);

-- =============================================
-- Renúncias Fiscais
-- =============================================
CREATE INDEX idx_renuncia_cnpj ON renuncia_fiscal(cnpj);
CREATE INDEX idx_renuncia_valor ON renuncia_fiscal(valor_renuncia);
CREATE INDEX idx_renuncia_ano ON renuncia_fiscal(ano_calendario);
CREATE INDEX idx_renuncia_tipo ON renuncia_fiscal(tipo_renuncia);
CREATE INDEX idx_habilitada_cnpj ON empresa_habilitada(cnpj);
CREATE INDEX idx_imune_cnpj ON empresa_imune(cnpj);
CREATE INDEX idx_ren_benef_cnpj ON renuncia_beneficiario(cnpj);

-- =============================================
-- Complementar: BNDES
-- =============================================
CREATE INDEX idx_bndes_cnpj ON bndes_contrato(cnpj);
CREATE INDEX idx_bndes_valor ON bndes_contrato(valor_contratado);
CREATE INDEX idx_bndes_uf ON bndes_contrato(uf);

-- =============================================
-- Complementar: Holdings
-- =============================================
CREATE INDEX idx_holding_cnpj ON holding_vinculo(holding_cnpj);
CREATE INDEX idx_holding_sub ON holding_vinculo(cnpj_subsidiaria);

-- =============================================
-- Complementar: ComprasNet
-- =============================================
CREATE INDEX idx_compras_fornecedor ON comprasnet_contrato(fornecedor_cnpj_cpf);
CREATE INDEX idx_compras_orgao ON comprasnet_contrato(orgao_codigo);
CREATE INDEX idx_compras_dt ON comprasnet_contrato(dt_assinatura);
CREATE INDEX idx_compras_valor ON comprasnet_contrato(valor_global);

-- =============================================
-- Pessoa (Entity Resolution)
-- =============================================
CREATE INDEX idx_pessoa_nome_cpf ON pessoa(nome_normalizado, cpf_masked);
CREATE UNIQUE INDEX idx_pessoa_cpf_completo ON pessoa(cpf_completo) WHERE cpf_completo IS NOT NULL;
CREATE INDEX idx_pessoa_nome_trgm ON pessoa USING gin(nome_normalizado gin_trgm_ops);
CREATE INDEX idx_obs_pessoa ON pessoa_observacao(pessoa_id);
CREATE INDEX idx_obs_fonte ON pessoa_observacao(fonte, fonte_id);
CREATE UNIQUE INDEX idx_merge_par ON pessoa_merge(pessoa_a_id, pessoa_b_id);
CREATE INDEX idx_merge_status ON pessoa_merge(status);
