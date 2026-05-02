-- Q25: Empresa com sancao CEIS vigente que ganhou contrato PNCP
SELECT cs.nome_sancionado, cs.cpf_cnpj_sancionado,
       cs.categoria_sancao, cs.dt_inicio_sancao, cs.dt_final_sancao,
       cs.orgao_sancionador,
       pc.uf AS uf_contrato, pc.municipio_nome AS municipio_contrato,
       pc.objeto, pc.valor_global, pc.dt_assinatura, pc.cnpj_orgao
FROM ceis_sancao cs
JOIN pncp_contrato pc ON cs.cpf_cnpj_norm = pc.ni_fornecedor
WHERE (cs.dt_final_sancao IS NULL OR pc.dt_assinatura <= cs.dt_final_sancao)
  AND pc.dt_assinatura >= cs.dt_inicio_sancao
ORDER BY pc.valor_global DESC;

-- Q26: Empresa punida pela Lei Anticorrupcao (CNEP) que recebe emendas durante vigência da sanção
-- FIX #11: adicionado filtro temporal — emenda deve cair dentro do período da sanção
SELECT cn.nome_sancionado, cn.cpf_cnpj_sancionado,
       cn.categoria_sancao, cn.valor_multa,
       cn.dt_inicio_sancao, cn.dt_final_sancao,
       ef.nome_autor, ef.codigo_emenda,
       ef.uf_favorecido, ef.municipio_favorecido,
       ef.valor_recebido, ef.ano_mes
FROM cnep_sancao cn
JOIN emenda_favorecido ef ON cn.cpf_cnpj_norm = ef.codigo_favorecido
WHERE ef.ano_mes >= TO_CHAR(cn.dt_inicio_sancao, 'YYYY/MM')
  AND (cn.dt_final_sancao IS NULL OR ef.ano_mes <= TO_CHAR(cn.dt_final_sancao, 'YYYY/MM'))
ORDER BY ef.valor_recebido DESC;

-- Q27: Servidor expulso (CEAF) que ainda aparece como socio de empresa
-- FIX (CEAF length=6): cpf_cnpj_norm em ceaf_expulsao tem 6 digitos centrais
-- (CSV vem mascarado), mesmo formato que socio.cpf_cnpj_norm para PFs.
-- Adicionado match por nome para evitar colisao em 6 digitos.
SELECT ce.nome_sancionado, ce.cpf_cnpj_sancionado,
       ce.categoria_sancao, ce.cargo_efetivo, ce.orgao_lotacao,
       s.cnpj_basico, e.razao_social, s.qualificacao,
       est.uf AS uf_empresa, est.municipio AS municipio_empresa
FROM ceaf_expulsao ce
JOIN socio s ON ce.cpf_cnpj_norm = s.cpf_cnpj_norm
  AND LENGTH(ce.cpf_cnpj_norm) = 6
  AND s.tipo_socio = 2
  AND normalize_name(ce.nome_sancionado) = normalize_name(s.nome)
JOIN empresa e ON e.cnpj_basico = s.cnpj_basico
LEFT JOIN estabelecimento est ON est.cnpj_basico = s.cnpj_basico
  AND est.cnpj_ordem = '0001' AND est.situacao_cadastral = '2'
WHERE ce.cpf_cnpj_norm IS NOT NULL AND ce.cpf_cnpj_norm != '000000'
ORDER BY ce.dt_inicio_sancao DESC;

-- Q28: Empresa com acordo de leniencia ativo que volta a ganhar contratos
-- FIX #11: filtrar apenas acordos não cumpridos/encerrados + contratos durante vigência
SELECT al.razao_social_rfb, al.cnpj_sancionado,
       al.situacao_acordo, al.dt_inicio_acordo, al.dt_fim_acordo,
       pc.uf AS uf_contrato, pc.municipio_nome AS municipio_contrato,
       pc.objeto, pc.valor_global, pc.dt_assinatura
FROM acordo_leniencia al
JOIN pncp_contrato pc ON al.cnpj_norm = pc.ni_fornecedor
WHERE pc.dt_assinatura > al.dt_inicio_acordo
  AND (al.dt_fim_acordo IS NULL OR pc.dt_assinatura <= al.dt_fim_acordo)
  AND al.situacao_acordo NOT IN ('Cumprido', 'Encerrado', 'cumprido', 'encerrado')
ORDER BY pc.valor_global DESC;
