-- Synthetic NK = MD5 hash of full row payload for 7 Dados-PB tables.
-- Approach: regular text column + IMMUTABLE function + BEFORE INSERT trigger.
-- (Generated columns rejected because numeric/date::text casts are STABLE not IMMUTABLE.)
--
-- Workflow:
-- 1. Add nullable text column _nk_md5 (no default — populated below)
-- 2. Define IMMUTABLE function etl_admin.row_hash_md5(VARIADIC text[])
-- 3. UPDATE legacy rows com hash, then DELETE dups, then add UNIQUE INDEX
-- 4. Add BEFORE INSERT trigger to populate new rows automatically
--
-- This is non-destructive in the framework sense: no TRUNCATE/DROP TABLE,
-- only DELETE of EXACT duplicates (rows whose every payload byte matches another row).

CREATE OR REPLACE FUNCTION etl_admin.row_hash_md5(VARIADIC vals text[])
RETURNS text AS $$
  SELECT md5(array_to_string(vals, '|'))
$$ LANGUAGE SQL IMMUTABLE PARALLEL SAFE;

GRANT EXECUTE ON FUNCTION etl_admin.row_hash_md5(VARIADIC text[]) TO PUBLIC;


-- ─── Add columns + populate + dedupe + index ─────────────────────────────

-- pb_liquidacao_desconto (10 cols)
ALTER TABLE pb_liquidacao_desconto ADD COLUMN IF NOT EXISTS _nk_md5 text;
UPDATE pb_liquidacao_desconto SET _nk_md5 = etl_admin.row_hash_md5(
  coalesce(exercicio::text,''), coalesce(codigo_orgao,''),
  coalesce(numero_empenho,''), coalesce(numero_documento,''),
  to_char(data_pagamento, 'YYYY-MM-DD'), coalesce(tipo_pagamento,''),
  coalesce(codigo_desconto,''), coalesce(descricao_desconto,''),
  coalesce(codigo_orgao_pagamento,''), coalesce(valor_desconto::text,'')
) WHERE _nk_md5 IS NULL;

-- pb_empenho_anulacao
ALTER TABLE pb_empenho_anulacao ADD COLUMN IF NOT EXISTS _nk_md5 text;
UPDATE pb_empenho_anulacao SET _nk_md5 = etl_admin.row_hash_md5(
  coalesce(exercicio::text,''), coalesce(codigo_unidade_gestora,''),
  coalesce(numero_empenho,''), coalesce(numero_empenho_origem,''),
  to_char(data_empenho, 'YYYY-MM-DD'), coalesce(valor_empenho::text,''),
  coalesce(historico_empenho,''), coalesce(nome_credor,''),
  coalesce(cpfcnpj_credor,''), coalesce(numero_processo_pagamento,''),
  coalesce(numero_contrato,'')
) WHERE _nk_md5 IS NULL;

-- pb_empenho_suplementacao
ALTER TABLE pb_empenho_suplementacao ADD COLUMN IF NOT EXISTS _nk_md5 text;
UPDATE pb_empenho_suplementacao SET _nk_md5 = etl_admin.row_hash_md5(
  coalesce(exercicio::text,''), coalesce(codigo_unidade_gestora,''),
  coalesce(numero_empenho,''), coalesce(numero_empenho_origem,''),
  to_char(data_empenho, 'YYYY-MM-DD'), coalesce(valor_empenho::text,''),
  coalesce(historico_empenho,''), coalesce(nome_credor,''),
  coalesce(cpfcnpj_credor,''), coalesce(numero_processo_pagamento,''),
  coalesce(numero_contrato,'')
) WHERE _nk_md5 IS NULL;

-- pb_diaria
ALTER TABLE pb_diaria ADD COLUMN IF NOT EXISTS _nk_md5 text;
UPDATE pb_diaria SET _nk_md5 = etl_admin.row_hash_md5(
  coalesce(exercicio::text,''), coalesce(codigo_unidade_gestora,''),
  coalesce(numero_empenho,''), to_char(data_empenho, 'YYYY-MM-DD'),
  coalesce(valor_empenho::text,''), coalesce(destino_diarias,''),
  to_char(data_saida_diarias, 'YYYY-MM-DD'),
  to_char(data_chegada_diarias, 'YYYY-MM-DD'),
  coalesce(nome_credor,''), coalesce(cpfcnpj_credor,'')
) WHERE _nk_md5 IS NULL;

-- pb_dotacao
ALTER TABLE pb_dotacao ADD COLUMN IF NOT EXISTS _nk_md5 text;
UPDATE pb_dotacao SET _nk_md5 = etl_admin.row_hash_md5(
  coalesce(codigo_unidade_gestora,''), coalesce(exercicio::text,''),
  coalesce(codigo_unidade_orcamentaria,''), coalesce(codigo_funcao,''),
  coalesce(codigo_subfuncao,''), coalesce(codigo_programa,''),
  coalesce(codigo_acao,''), coalesce(meta,''),
  coalesce(localidade,''), coalesce(categoria,''),
  coalesce(grupo_despesa,''), coalesce(modalidade,''),
  coalesce(elemento_despesa,''), coalesce(fonte_recurso,''),
  coalesce(valor_orcado::text,'')
) WHERE _nk_md5 IS NULL;

-- pb_aditivo_contrato
ALTER TABLE pb_aditivo_contrato ADD COLUMN IF NOT EXISTS _nk_md5 text;
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
) WHERE _nk_md5 IS NULL;

-- pb_aditivo_convenio
ALTER TABLE pb_aditivo_convenio ADD COLUMN IF NOT EXISTS _nk_md5 text;
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
) WHERE _nk_md5 IS NULL;


-- ─── Dedupe legacy: keep min(id) per _nk_md5 ─────────────────────────────
DO $$
DECLARE tbl text; cnt bigint;
BEGIN
  FOREACH tbl IN ARRAY ARRAY[
    'pb_liquidacao_desconto','pb_empenho_anulacao','pb_empenho_suplementacao',
    'pb_diaria','pb_dotacao','pb_aditivo_contrato','pb_aditivo_convenio'
  ] LOOP
    EXECUTE format($f$
      WITH dedup AS (
        SELECT id, _nk_md5,
               row_number() OVER (PARTITION BY _nk_md5 ORDER BY id) AS rn
        FROM %I
      )
      DELETE FROM %I WHERE id IN (SELECT id FROM dedup WHERE rn > 1)
    $f$, tbl, tbl);
    GET DIAGNOSTICS cnt = ROW_COUNT;
    RAISE NOTICE 'Deleted % legacy duplicate rows from %', cnt, tbl;
  END LOOP;
END $$;


-- ─── UNIQUE INDEXes ──────────────────────────────────────────────────────
CREATE UNIQUE INDEX IF NOT EXISTS ix_pb_liquidacao_desconto_nk_md5 ON pb_liquidacao_desconto (_nk_md5);
CREATE UNIQUE INDEX IF NOT EXISTS ix_pb_empenho_anulacao_nk_md5 ON pb_empenho_anulacao (_nk_md5);
CREATE UNIQUE INDEX IF NOT EXISTS ix_pb_empenho_suplementacao_nk_md5 ON pb_empenho_suplementacao (_nk_md5);
CREATE UNIQUE INDEX IF NOT EXISTS ix_pb_diaria_nk_md5 ON pb_diaria (_nk_md5);
CREATE UNIQUE INDEX IF NOT EXISTS ix_pb_dotacao_nk_md5 ON pb_dotacao (_nk_md5);
CREATE UNIQUE INDEX IF NOT EXISTS ix_pb_aditivo_contrato_nk_md5 ON pb_aditivo_contrato (_nk_md5);
CREATE UNIQUE INDEX IF NOT EXISTS ix_pb_aditivo_convenio_nk_md5 ON pb_aditivo_convenio (_nk_md5);


-- ─── BEFORE INSERT triggers para auto-popular _nk_md5 em novos rows ─────
-- ETL faz INSERT sem _nk_md5; trigger calcula. Permite incremental seamless.

CREATE OR REPLACE FUNCTION etl_admin.compute_nk_md5_pb_liquidacao_desconto()
RETURNS trigger AS $$
BEGIN
  IF NEW._nk_md5 IS NULL THEN
    NEW._nk_md5 := etl_admin.row_hash_md5(
      coalesce(NEW.exercicio::text,''), coalesce(NEW.codigo_orgao,''),
      coalesce(NEW.numero_empenho,''), coalesce(NEW.numero_documento,''),
      to_char(NEW.data_pagamento, 'YYYY-MM-DD'), coalesce(NEW.tipo_pagamento,''),
      coalesce(NEW.codigo_desconto,''), coalesce(NEW.descricao_desconto,''),
      coalesce(NEW.codigo_orgao_pagamento,''), coalesce(NEW.valor_desconto::text,'')
    );
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_compute_nk_md5 ON pb_liquidacao_desconto;
CREATE TRIGGER trg_compute_nk_md5 BEFORE INSERT ON pb_liquidacao_desconto
FOR EACH ROW EXECUTE FUNCTION etl_admin.compute_nk_md5_pb_liquidacao_desconto();


CREATE OR REPLACE FUNCTION etl_admin.compute_nk_md5_pb_empenho_anulacao()
RETURNS trigger AS $$
BEGIN
  IF NEW._nk_md5 IS NULL THEN
    NEW._nk_md5 := etl_admin.row_hash_md5(
      coalesce(NEW.exercicio::text,''), coalesce(NEW.codigo_unidade_gestora,''),
      coalesce(NEW.numero_empenho,''), coalesce(NEW.numero_empenho_origem,''),
      to_char(NEW.data_empenho, 'YYYY-MM-DD'), coalesce(NEW.valor_empenho::text,''),
      coalesce(NEW.historico_empenho,''), coalesce(NEW.nome_credor,''),
      coalesce(NEW.cpfcnpj_credor,''), coalesce(NEW.numero_processo_pagamento,''),
      coalesce(NEW.numero_contrato,'')
    );
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_compute_nk_md5 ON pb_empenho_anulacao;
CREATE TRIGGER trg_compute_nk_md5 BEFORE INSERT ON pb_empenho_anulacao
FOR EACH ROW EXECUTE FUNCTION etl_admin.compute_nk_md5_pb_empenho_anulacao();


CREATE OR REPLACE FUNCTION etl_admin.compute_nk_md5_pb_empenho_suplementacao()
RETURNS trigger AS $$
BEGIN
  IF NEW._nk_md5 IS NULL THEN
    NEW._nk_md5 := etl_admin.row_hash_md5(
      coalesce(NEW.exercicio::text,''), coalesce(NEW.codigo_unidade_gestora,''),
      coalesce(NEW.numero_empenho,''), coalesce(NEW.numero_empenho_origem,''),
      to_char(NEW.data_empenho, 'YYYY-MM-DD'), coalesce(NEW.valor_empenho::text,''),
      coalesce(NEW.historico_empenho,''), coalesce(NEW.nome_credor,''),
      coalesce(NEW.cpfcnpj_credor,''), coalesce(NEW.numero_processo_pagamento,''),
      coalesce(NEW.numero_contrato,'')
    );
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_compute_nk_md5 ON pb_empenho_suplementacao;
CREATE TRIGGER trg_compute_nk_md5 BEFORE INSERT ON pb_empenho_suplementacao
FOR EACH ROW EXECUTE FUNCTION etl_admin.compute_nk_md5_pb_empenho_suplementacao();


CREATE OR REPLACE FUNCTION etl_admin.compute_nk_md5_pb_diaria()
RETURNS trigger AS $$
BEGIN
  IF NEW._nk_md5 IS NULL THEN
    NEW._nk_md5 := etl_admin.row_hash_md5(
      coalesce(NEW.exercicio::text,''), coalesce(NEW.codigo_unidade_gestora,''),
      coalesce(NEW.numero_empenho,''), to_char(NEW.data_empenho, 'YYYY-MM-DD'),
      coalesce(NEW.valor_empenho::text,''), coalesce(NEW.destino_diarias,''),
      to_char(NEW.data_saida_diarias, 'YYYY-MM-DD'),
      to_char(NEW.data_chegada_diarias, 'YYYY-MM-DD'),
      coalesce(NEW.nome_credor,''), coalesce(NEW.cpfcnpj_credor,'')
    );
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_compute_nk_md5 ON pb_diaria;
CREATE TRIGGER trg_compute_nk_md5 BEFORE INSERT ON pb_diaria
FOR EACH ROW EXECUTE FUNCTION etl_admin.compute_nk_md5_pb_diaria();


CREATE OR REPLACE FUNCTION etl_admin.compute_nk_md5_pb_dotacao()
RETURNS trigger AS $$
BEGIN
  IF NEW._nk_md5 IS NULL THEN
    NEW._nk_md5 := etl_admin.row_hash_md5(
      coalesce(NEW.codigo_unidade_gestora,''), coalesce(NEW.exercicio::text,''),
      coalesce(NEW.codigo_unidade_orcamentaria,''), coalesce(NEW.codigo_funcao,''),
      coalesce(NEW.codigo_subfuncao,''), coalesce(NEW.codigo_programa,''),
      coalesce(NEW.codigo_acao,''), coalesce(NEW.meta,''),
      coalesce(NEW.localidade,''), coalesce(NEW.categoria,''),
      coalesce(NEW.grupo_despesa,''), coalesce(NEW.modalidade,''),
      coalesce(NEW.elemento_despesa,''), coalesce(NEW.fonte_recurso,''),
      coalesce(NEW.valor_orcado::text,'')
    );
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_compute_nk_md5 ON pb_dotacao;
CREATE TRIGGER trg_compute_nk_md5 BEFORE INSERT ON pb_dotacao
FOR EACH ROW EXECUTE FUNCTION etl_admin.compute_nk_md5_pb_dotacao();


CREATE OR REPLACE FUNCTION etl_admin.compute_nk_md5_pb_aditivo_contrato()
RETURNS trigger AS $$
BEGIN
  IF NEW._nk_md5 IS NULL THEN
    NEW._nk_md5 := etl_admin.row_hash_md5(
      coalesce(NEW.codigo_aditivo_contrato,''), coalesce(NEW.codigo_contrato,''),
      coalesce(NEW.motivo_aditivacao,''), coalesce(NEW.numero_aditivo_contrato,''),
      to_char(NEW.data_inicio_vigencia, 'YYYY-MM-DD'),
      to_char(NEW.data_termino_vigencia, 'YYYY-MM-DD'),
      coalesce(NEW.valor_aditivo::text,''), coalesce(NEW.objeto_aditivo,''),
      to_char(NEW.data_celebracao_aditivo, 'YYYY-MM-DD'),
      to_char(NEW.data_publicacao, 'YYYY-MM-DD'),
      to_char(NEW.data_republicacao, 'YYYY-MM-DD'),
      coalesce(NEW.url_aditivo_contrato,'')
    );
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_compute_nk_md5 ON pb_aditivo_contrato;
CREATE TRIGGER trg_compute_nk_md5 BEFORE INSERT ON pb_aditivo_contrato
FOR EACH ROW EXECUTE FUNCTION etl_admin.compute_nk_md5_pb_aditivo_contrato();


CREATE OR REPLACE FUNCTION etl_admin.compute_nk_md5_pb_aditivo_convenio()
RETURNS trigger AS $$
BEGIN
  IF NEW._nk_md5 IS NULL THEN
    NEW._nk_md5 := etl_admin.row_hash_md5(
      coalesce(NEW.codigo_aditivo_convenio,''), coalesce(NEW.codigo_convenio,''),
      coalesce(NEW.motivo_aditivacao,''), coalesce(NEW.numero_aditivo_convenio,''),
      to_char(NEW.data_inicio_vigencia, 'YYYY-MM-DD'),
      to_char(NEW.data_termino_vigencia, 'YYYY-MM-DD'),
      coalesce(NEW.valor_concedente::text,''), coalesce(NEW.valor_convenente::text,''),
      coalesce(NEW.objeto_aditivo,''),
      to_char(NEW.data_celebracao_aditivo, 'YYYY-MM-DD'),
      to_char(NEW.data_publicacao, 'YYYY-MM-DD'),
      to_char(NEW.data_republicacao, 'YYYY-MM-DD'),
      coalesce(NEW.url_aditivo_convenio,'')
    );
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_compute_nk_md5 ON pb_aditivo_convenio;
CREATE TRIGGER trg_compute_nk_md5 BEFORE INSERT ON pb_aditivo_convenio
FOR EACH ROW EXECUTE FUNCTION etl_admin.compute_nk_md5_pb_aditivo_convenio();
