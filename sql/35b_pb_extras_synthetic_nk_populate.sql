-- sql/35b_pb_extras_synthetic_nk_populate.sql
--
-- Phase B (NÃO-DESTRUTIVO, BATCHED): popula coluna _nk_md5 em rows legacy.
--
-- Cada PROCEDURE itera em batches de 50k rows com COMMIT entre batches.
-- Resumível: WHERE _nk_md5 IS NULL → só atualiza rows ainda não populadas.
-- Pode ser interrompido (Ctrl+C) e re-executado sem perda.
--
-- Dependências:
-- - sql/35a deve ter rodado primeiro (cria coluna)
-- - sql/27_etl_admin_security_definer.sql (cria schema etl_admin)
--
-- Tempo estimado em prod (estimativa baseada em local):
-- - pb_liquidacao_desconto: ~2.4M rows → 5-15 min
-- - pb_diaria: ~642k → 2-5 min
-- - outros: ~1 min cada
-- Total: 15-30 min
--
-- Como rodar:
--   psql -f sql/35b_pb_extras_synthetic_nk_populate.sql
--
-- Para rodar tabela individual (em emergência):
--   psql -c "CALL etl_admin.populate_nk_md5_pb_diaria(50000);"


CREATE OR REPLACE PROCEDURE etl_admin.populate_nk_md5_pb_liquidacao_desconto(batch_size int DEFAULT 50000)
LANGUAGE plpgsql AS $$
DECLARE
  n int;
  total bigint := 0;
BEGIN
  LOOP
    UPDATE pb_liquidacao_desconto SET _nk_md5 = etl_admin.row_hash_md5(
      coalesce(exercicio::text,''), coalesce(codigo_orgao,''),
      coalesce(numero_empenho,''), coalesce(numero_documento,''),
      to_char(data_pagamento, 'YYYY-MM-DD'), coalesce(tipo_pagamento,''),
      coalesce(codigo_desconto,''), coalesce(descricao_desconto,''),
      coalesce(codigo_orgao_pagamento,''), coalesce(valor_desconto::text,'')
    )
    WHERE id IN (
      SELECT id FROM pb_liquidacao_desconto
      WHERE _nk_md5 IS NULL ORDER BY id LIMIT batch_size
    );
    GET DIAGNOSTICS n = ROW_COUNT;
    EXIT WHEN n = 0;
    total := total + n;
    RAISE NOTICE 'pb_liquidacao_desconto: populated % rows (total %)', n, total;
    COMMIT;
  END LOOP;
  RAISE NOTICE 'pb_liquidacao_desconto: DONE - total % rows populated', total;
END $$;


CREATE OR REPLACE PROCEDURE etl_admin.populate_nk_md5_pb_empenho_anulacao(batch_size int DEFAULT 50000)
LANGUAGE plpgsql AS $$
DECLARE n int; total bigint := 0;
BEGIN
  LOOP
    UPDATE pb_empenho_anulacao SET _nk_md5 = etl_admin.row_hash_md5(
      coalesce(exercicio::text,''), coalesce(codigo_unidade_gestora,''),
      coalesce(numero_empenho,''), coalesce(numero_empenho_origem,''),
      to_char(data_empenho, 'YYYY-MM-DD'), coalesce(valor_empenho::text,''),
      coalesce(historico_empenho,''), coalesce(nome_credor,''),
      coalesce(cpfcnpj_credor,''), coalesce(numero_processo_pagamento,''),
      coalesce(numero_contrato,'')
    )
    WHERE id IN (SELECT id FROM pb_empenho_anulacao WHERE _nk_md5 IS NULL ORDER BY id LIMIT batch_size);
    GET DIAGNOSTICS n = ROW_COUNT;
    EXIT WHEN n = 0;
    total := total + n;
    RAISE NOTICE 'pb_empenho_anulacao: populated % rows (total %)', n, total;
    COMMIT;
  END LOOP;
  RAISE NOTICE 'pb_empenho_anulacao: DONE - total % rows populated', total;
END $$;


CREATE OR REPLACE PROCEDURE etl_admin.populate_nk_md5_pb_empenho_suplementacao(batch_size int DEFAULT 50000)
LANGUAGE plpgsql AS $$
DECLARE n int; total bigint := 0;
BEGIN
  LOOP
    UPDATE pb_empenho_suplementacao SET _nk_md5 = etl_admin.row_hash_md5(
      coalesce(exercicio::text,''), coalesce(codigo_unidade_gestora,''),
      coalesce(numero_empenho,''), coalesce(numero_empenho_origem,''),
      to_char(data_empenho, 'YYYY-MM-DD'), coalesce(valor_empenho::text,''),
      coalesce(historico_empenho,''), coalesce(nome_credor,''),
      coalesce(cpfcnpj_credor,''), coalesce(numero_processo_pagamento,''),
      coalesce(numero_contrato,'')
    )
    WHERE id IN (SELECT id FROM pb_empenho_suplementacao WHERE _nk_md5 IS NULL ORDER BY id LIMIT batch_size);
    GET DIAGNOSTICS n = ROW_COUNT;
    EXIT WHEN n = 0;
    total := total + n;
    RAISE NOTICE 'pb_empenho_suplementacao: populated % rows (total %)', n, total;
    COMMIT;
  END LOOP;
  RAISE NOTICE 'pb_empenho_suplementacao: DONE - total % rows populated', total;
END $$;


CREATE OR REPLACE PROCEDURE etl_admin.populate_nk_md5_pb_diaria(batch_size int DEFAULT 50000)
LANGUAGE plpgsql AS $$
DECLARE n int; total bigint := 0;
BEGIN
  LOOP
    UPDATE pb_diaria SET _nk_md5 = etl_admin.row_hash_md5(
      coalesce(exercicio::text,''), coalesce(codigo_unidade_gestora,''),
      coalesce(numero_empenho,''), to_char(data_empenho, 'YYYY-MM-DD'),
      coalesce(valor_empenho::text,''), coalesce(destino_diarias,''),
      to_char(data_saida_diarias, 'YYYY-MM-DD'),
      to_char(data_chegada_diarias, 'YYYY-MM-DD'),
      coalesce(nome_credor,''), coalesce(cpfcnpj_credor,'')
    )
    WHERE id IN (SELECT id FROM pb_diaria WHERE _nk_md5 IS NULL ORDER BY id LIMIT batch_size);
    GET DIAGNOSTICS n = ROW_COUNT;
    EXIT WHEN n = 0;
    total := total + n;
    RAISE NOTICE 'pb_diaria: populated % rows (total %)', n, total;
    COMMIT;
  END LOOP;
  RAISE NOTICE 'pb_diaria: DONE - total % rows populated', total;
END $$;


CREATE OR REPLACE PROCEDURE etl_admin.populate_nk_md5_pb_dotacao(batch_size int DEFAULT 50000)
LANGUAGE plpgsql AS $$
DECLARE n int; total bigint := 0;
BEGIN
  LOOP
    UPDATE pb_dotacao SET _nk_md5 = etl_admin.row_hash_md5(
      coalesce(codigo_unidade_gestora,''), coalesce(exercicio::text,''),
      coalesce(codigo_unidade_orcamentaria,''), coalesce(codigo_funcao,''),
      coalesce(codigo_subfuncao,''), coalesce(codigo_programa,''),
      coalesce(codigo_acao,''), coalesce(meta,''),
      coalesce(localidade,''), coalesce(categoria,''),
      coalesce(grupo_despesa,''), coalesce(modalidade,''),
      coalesce(elemento_despesa,''), coalesce(fonte_recurso,''),
      coalesce(valor_orcado::text,'')
    )
    WHERE id IN (SELECT id FROM pb_dotacao WHERE _nk_md5 IS NULL ORDER BY id LIMIT batch_size);
    GET DIAGNOSTICS n = ROW_COUNT;
    EXIT WHEN n = 0;
    total := total + n;
    RAISE NOTICE 'pb_dotacao: populated % rows (total %)', n, total;
    COMMIT;
  END LOOP;
  RAISE NOTICE 'pb_dotacao: DONE - total % rows populated', total;
END $$;


CREATE OR REPLACE PROCEDURE etl_admin.populate_nk_md5_pb_aditivo_contrato(batch_size int DEFAULT 50000)
LANGUAGE plpgsql AS $$
DECLARE n int; total bigint := 0;
BEGIN
  LOOP
    UPDATE pb_aditivo_contrato SET _nk_md5 = etl_admin.row_hash_md5(
      coalesce(codigo_aditivo_contrato,''), coalesce(codigo_contrato,''),
      coalesce(motivo_aditivacao,''), coalesce(numero_aditivo_contrato,''),
      to_char(data_inicio_vigencia, 'YYYY-MM-DD'),
      to_char(data_termino_vigencia, 'YYYY-MM-DD'),
      coalesce(valor_aditivo::text,''), coalesce(objeto_aditivo,''),
      to_char(data_celebracao_aditivo, 'YYYY-MM-DD'),
      to_char(data_publicacao, 'YYYY-MM-DD'),
      to_char(data_republicacao, 'YYYY-MM-DD'),
      coalesce(url_aditivo_contrato,'')
    )
    WHERE id IN (SELECT id FROM pb_aditivo_contrato WHERE _nk_md5 IS NULL ORDER BY id LIMIT batch_size);
    GET DIAGNOSTICS n = ROW_COUNT;
    EXIT WHEN n = 0;
    total := total + n;
    RAISE NOTICE 'pb_aditivo_contrato: populated % rows (total %)', n, total;
    COMMIT;
  END LOOP;
  RAISE NOTICE 'pb_aditivo_contrato: DONE - total % rows populated', total;
END $$;


CREATE OR REPLACE PROCEDURE etl_admin.populate_nk_md5_pb_aditivo_convenio(batch_size int DEFAULT 50000)
LANGUAGE plpgsql AS $$
DECLARE n int; total bigint := 0;
BEGIN
  LOOP
    UPDATE pb_aditivo_convenio SET _nk_md5 = etl_admin.row_hash_md5(
      coalesce(codigo_aditivo_convenio,''), coalesce(codigo_convenio,''),
      coalesce(motivo_aditivacao,''), coalesce(numero_aditivo_convenio,''),
      to_char(data_inicio_vigencia, 'YYYY-MM-DD'),
      to_char(data_termino_vigencia, 'YYYY-MM-DD'),
      coalesce(valor_concedente::text,''), coalesce(valor_convenente::text,''),
      coalesce(objeto_aditivo,''),
      to_char(data_celebracao_aditivo, 'YYYY-MM-DD'),
      to_char(data_publicacao, 'YYYY-MM-DD'),
      to_char(data_republicacao, 'YYYY-MM-DD'),
      coalesce(url_aditivo_convenio,'')
    )
    WHERE id IN (SELECT id FROM pb_aditivo_convenio WHERE _nk_md5 IS NULL ORDER BY id LIMIT batch_size);
    GET DIAGNOSTICS n = ROW_COUNT;
    EXIT WHEN n = 0;
    total := total + n;
    RAISE NOTICE 'pb_aditivo_convenio: populated % rows (total %)', n, total;
    COMMIT;
  END LOOP;
  RAISE NOTICE 'pb_aditivo_convenio: DONE - total % rows populated', total;
END $$;


-- ─── Execute all populates (idempotent) ──────────────────────────────────
CALL etl_admin.populate_nk_md5_pb_liquidacao_desconto();
CALL etl_admin.populate_nk_md5_pb_empenho_anulacao();
CALL etl_admin.populate_nk_md5_pb_empenho_suplementacao();
CALL etl_admin.populate_nk_md5_pb_diaria();
CALL etl_admin.populate_nk_md5_pb_dotacao();
CALL etl_admin.populate_nk_md5_pb_aditivo_contrato();
CALL etl_admin.populate_nk_md5_pb_aditivo_convenio();
