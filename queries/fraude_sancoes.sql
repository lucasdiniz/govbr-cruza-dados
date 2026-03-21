-- Q25: Empresa com sancao CEIS vigente que ganhou contrato PNCP
SELECT cs.nome_sancionado, cs.cpf_cnpj_sancionado,
       cs.categoria_sancao, cs.dt_inicio_sancao, cs.dt_final_sancao,
       cs.orgao_sancionador,
       pc.uf AS uf_contrato, pc.municipio_nome AS municipio_contrato,
       pc.objeto, pc.valor_global, pc.dt_assinatura, pc.cnpj_orgao
FROM ceis_sancao cs
JOIN pncp_contrato pc ON REGEXP_REPLACE(cs.cpf_cnpj_sancionado, '[^0-9]', '', 'g') = pc.ni_fornecedor
WHERE (cs.dt_final_sancao IS NULL OR pc.dt_assinatura <= cs.dt_final_sancao)
  AND pc.dt_assinatura >= cs.dt_inicio_sancao
ORDER BY pc.valor_global DESC
LIMIT 20;

-- Q26: Empresa punida pela Lei Anticorrupcao (CNEP) que recebe emendas
SELECT cn.nome_sancionado, cn.cpf_cnpj_sancionado,
       cn.categoria_sancao, cn.valor_multa,
       ef.nome_autor, ef.codigo_emenda,
       ef.uf_favorecido, ef.municipio_favorecido,
       ef.valor_recebido
FROM cnep_sancao cn
JOIN emenda_favorecido ef ON REGEXP_REPLACE(cn.cpf_cnpj_sancionado, '[^0-9]', '', 'g') = ef.codigo_favorecido
ORDER BY ef.valor_recebido DESC
LIMIT 20;

-- Q27: Servidor expulso (CEAF) que ainda aparece como socio de empresa
SELECT ce.nome_sancionado, ce.cpf_cnpj_sancionado,
       ce.categoria_sancao, ce.cargo_efetivo, ce.orgao_lotacao,
       s.cnpj_basico, e.razao_social, s.qualificacao,
       est.uf AS uf_empresa, est.municipio AS municipio_empresa
FROM ceaf_expulsao ce
JOIN socio s ON s.cpf_cnpj_socio LIKE '%' || SUBSTRING(REGEXP_REPLACE(ce.cpf_cnpj_sancionado, '[^0-9]', '', 'g'), 4, 6) || '%'
  AND s.tipo_socio = 2
JOIN empresa e ON e.cnpj_basico = s.cnpj_basico
LEFT JOIN estabelecimento est ON est.cnpj_basico = s.cnpj_basico
  AND est.cnpj_ordem = '0001' AND est.situacao_cadastral = '2'
WHERE SUBSTRING(REGEXP_REPLACE(ce.cpf_cnpj_sancionado, '[^0-9]', '', 'g'), 4, 6) != '000000'
ORDER BY ce.dt_inicio_sancao DESC
LIMIT 20;

-- Q28: Empresa com acordo de leniencia que volta a ganhar contratos
SELECT al.razao_social_rfb, al.cnpj_sancionado,
       al.situacao_acordo, al.dt_inicio_acordo, al.dt_fim_acordo,
       pc.uf AS uf_contrato, pc.municipio_nome AS municipio_contrato,
       pc.objeto, pc.valor_global, pc.dt_assinatura
FROM acordo_leniencia al
JOIN pncp_contrato pc ON REGEXP_REPLACE(al.cnpj_sancionado, '[^0-9]', '', 'g') = pc.ni_fornecedor
WHERE pc.dt_assinatura > al.dt_inicio_acordo
ORDER BY pc.valor_global DESC
LIMIT 20;
