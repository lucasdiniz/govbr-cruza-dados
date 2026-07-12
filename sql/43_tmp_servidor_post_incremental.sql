-- Rebuild das tabelas auxiliares de mv_servidor_pb_risco apos TCE-PB
-- incremental. Executado na mesma transacao do rebuild de _tmp_bf por
-- etl/refresh_post_incremental.py, depois de mv_servidor_pb_base e antes de
-- mv_servidor_pb_risco.
--
-- TRUNCATE + INSERT preserva os OIDs exigidos pela dependencia da MV.
-- Definicoes canonicas: sql/12_views.sql, steps 1-5b.

TRUNCATE TABLE
    _tmp_socio_empresas,
    _tmp_fornecedor_gov,
    _tmp_conflito,
    _tmp_duplo,
    _tmp_siape_federal;

INSERT INTO _tmp_socio_empresas
    (cpf_digitos_6, nome_upper, qtd_empresas, cnpjs)
SELECT srv.cpf_digitos_6,
       srv.nome_upper,
       COUNT(DISTINCT s.cnpj_basico) AS qtd_empresas,
       ARRAY_AGG(DISTINCT s.cnpj_basico ORDER BY s.cnpj_basico) AS cnpjs
FROM mv_servidor_pb_base srv
JOIN socio s ON s.cpf_cnpj_norm = srv.cpf_digitos_6
    AND UPPER(TRIM(s.nome)) = srv.nome_upper
    AND s.tipo_socio = 2
JOIN estabelecimento est ON est.cnpj_basico = s.cnpj_basico
    AND est.cnpj_ordem = '0001'
    AND est.situacao_cadastral = 2
GROUP BY srv.cpf_digitos_6, srv.nome_upper;

CREATE TEMP TABLE _post_inc_d_agg ON COMMIT DROP AS
SELECT cnpj_basico, municipio, SUM(valor_pago) AS total_pago
FROM tce_pb_despesa
WHERE valor_pago > 0
  AND municipio IS NOT NULL
  AND cnpj_basico IS NOT NULL
GROUP BY cnpj_basico, municipio;

ANALYZE _post_inc_d_agg;

CREATE TEMP TABLE _post_inc_se_unnest ON COMMIT DROP AS
SELECT se.cpf_digitos_6, se.nome_upper,
       m AS municipio, cnpj.cnpj_basico
FROM _tmp_socio_empresas se
JOIN mv_servidor_pb_base srv ON srv.cpf_digitos_6 = se.cpf_digitos_6
    AND srv.nome_upper = se.nome_upper
CROSS JOIN LATERAL unnest(se.cnpjs) AS cnpj(cnpj_basico)
CROSS JOIN LATERAL unnest(srv.municipios) AS m;

ANALYZE _post_inc_se_unnest;

INSERT INTO _tmp_conflito
    (cpf_digitos_6, nome_upper, qtd_conflitos, total_conflito)
SELECT u.cpf_digitos_6, u.nome_upper,
       COUNT(DISTINCT d.cnpj_basico) AS qtd_conflitos,
       SUM(d.total_pago) AS total_conflito
FROM _post_inc_se_unnest u
JOIN _post_inc_d_agg d ON d.cnpj_basico = u.cnpj_basico
    AND d.municipio = u.municipio
GROUP BY u.cpf_digitos_6, u.nome_upper;

INSERT INTO _tmp_fornecedor_gov (cpf_digitos_6, nome_upper)
SELECT DISTINCT se.cpf_digitos_6, se.nome_upper
FROM _tmp_socio_empresas se,
     LATERAL unnest(se.cnpjs) AS cnpj(cnpj_basico)
JOIN tce_pb_despesa d
  ON d.cnpj_basico = cnpj.cnpj_basico
 AND d.valor_pago > 0;

INSERT INTO _tmp_duplo (cpf_digitos_6, nome_upper, total_estado)
SELECT srv.cpf_digitos_6,
       srv.nome_upper,
       SUM(pp.valor_pagamento) AS total_estado
FROM mv_servidor_pb_base srv
JOIN pb_pagamento pp ON pp.cpf_digitos_6 = srv.cpf_digitos_6
    AND pp.nome_upper = srv.nome_upper
    AND LENGTH(pp.cpfcnpj_credor) = 11
GROUP BY srv.cpf_digitos_6, srv.nome_upper;

INSERT INTO _tmp_siape_federal (cpf_digitos_6, nome_upper)
SELECT DISTINCT srv.cpf_digitos_6, srv.nome_upper
FROM mv_servidor_pb_base srv
JOIN siape_cadastro sf ON sf.cpf_digitos = srv.cpf_digitos_6
    AND UPPER(TRIM(sf.nome)) = srv.nome_upper
WHERE srv.cpf_digitos_6 IS NOT NULL
  AND srv.cpf_digitos_6 != ''
  AND srv.cpf_digitos_6 != '000000'
  AND sf.cpf_digitos IS NOT NULL
  AND sf.cpf_digitos != ''
  AND sf.cpf_digitos != '000000';

ANALYZE _tmp_socio_empresas;
ANALYZE _tmp_fornecedor_gov;
ANALYZE _tmp_conflito;
ANALYZE _tmp_duplo;
ANALYZE _tmp_siape_federal;
