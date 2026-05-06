-- sql/35a_pb_extras_synthetic_nk_columns.sql
--
-- Phase A (NÃO-DESTRUTIVO, RAPIDO): adiciona coluna _nk_md5 + função IMMUTABLE
-- de hash + triggers BEFORE INSERT em 7 tabelas Dados-PB.
--
-- ALTER TABLE ADD COLUMN é metadata-only em PG (rápido), apenas requer ACCESS
-- EXCLUSIVE lock breve. Coluna é nullable, sem default → não reescreve rows.
--
-- Triggers só atuam em INSERT futuros; rows existentes ficam com _nk_md5 NULL
-- até serem populadas (ver sql/35b).
--
-- Idempotent: ADD COLUMN IF NOT EXISTS, CREATE OR REPLACE FUNCTION.
--
-- Run order: 35a → 35b (populate) → 35c (dedupe) → 35d (indexes).

CREATE OR REPLACE FUNCTION etl_admin.row_hash_md5(VARIADIC vals text[])
RETURNS text AS $func$
  SELECT md5(array_to_string(vals, '|'))
$func$ LANGUAGE SQL IMMUTABLE PARALLEL SAFE SET search_path = pg_catalog, public;

GRANT EXECUTE ON FUNCTION etl_admin.row_hash_md5(VARIADIC text[]) TO PUBLIC;


-- ─── ADD COLUMNS (idempotent) ────────────────────────────────────────────
ALTER TABLE pb_liquidacao_desconto ADD COLUMN IF NOT EXISTS _nk_md5 text;
ALTER TABLE pb_empenho_anulacao ADD COLUMN IF NOT EXISTS _nk_md5 text;
ALTER TABLE pb_empenho_suplementacao ADD COLUMN IF NOT EXISTS _nk_md5 text;
ALTER TABLE pb_diaria ADD COLUMN IF NOT EXISTS _nk_md5 text;
ALTER TABLE pb_dotacao ADD COLUMN IF NOT EXISTS _nk_md5 text;
ALTER TABLE pb_aditivo_contrato ADD COLUMN IF NOT EXISTS _nk_md5 text;
ALTER TABLE pb_aditivo_convenio ADD COLUMN IF NOT EXISTS _nk_md5 text;


-- ─── BEFORE INSERT triggers (auto-popular _nk_md5) ──────────────────────

CREATE OR REPLACE FUNCTION etl_admin.compute_nk_md5_pb_liquidacao_desconto()
RETURNS trigger AS $func$
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
END
$func$ LANGUAGE plpgsql SET search_path = pg_catalog, public;

DROP TRIGGER IF EXISTS trg_compute_nk_md5 ON pb_liquidacao_desconto;
CREATE TRIGGER trg_compute_nk_md5 BEFORE INSERT ON pb_liquidacao_desconto
FOR EACH ROW EXECUTE FUNCTION etl_admin.compute_nk_md5_pb_liquidacao_desconto();


CREATE OR REPLACE FUNCTION etl_admin.compute_nk_md5_pb_empenho_anulacao()
RETURNS trigger AS $func$
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
END
$func$ LANGUAGE plpgsql SET search_path = pg_catalog, public;

DROP TRIGGER IF EXISTS trg_compute_nk_md5 ON pb_empenho_anulacao;
CREATE TRIGGER trg_compute_nk_md5 BEFORE INSERT ON pb_empenho_anulacao
FOR EACH ROW EXECUTE FUNCTION etl_admin.compute_nk_md5_pb_empenho_anulacao();


CREATE OR REPLACE FUNCTION etl_admin.compute_nk_md5_pb_empenho_suplementacao()
RETURNS trigger AS $func$
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
END
$func$ LANGUAGE plpgsql SET search_path = pg_catalog, public;

DROP TRIGGER IF EXISTS trg_compute_nk_md5 ON pb_empenho_suplementacao;
CREATE TRIGGER trg_compute_nk_md5 BEFORE INSERT ON pb_empenho_suplementacao
FOR EACH ROW EXECUTE FUNCTION etl_admin.compute_nk_md5_pb_empenho_suplementacao();


CREATE OR REPLACE FUNCTION etl_admin.compute_nk_md5_pb_diaria()
RETURNS trigger AS $func$
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
END
$func$ LANGUAGE plpgsql SET search_path = pg_catalog, public;

DROP TRIGGER IF EXISTS trg_compute_nk_md5 ON pb_diaria;
CREATE TRIGGER trg_compute_nk_md5 BEFORE INSERT ON pb_diaria
FOR EACH ROW EXECUTE FUNCTION etl_admin.compute_nk_md5_pb_diaria();


CREATE OR REPLACE FUNCTION etl_admin.compute_nk_md5_pb_dotacao()
RETURNS trigger AS $func$
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
END
$func$ LANGUAGE plpgsql SET search_path = pg_catalog, public;

DROP TRIGGER IF EXISTS trg_compute_nk_md5 ON pb_dotacao;
CREATE TRIGGER trg_compute_nk_md5 BEFORE INSERT ON pb_dotacao
FOR EACH ROW EXECUTE FUNCTION etl_admin.compute_nk_md5_pb_dotacao();


CREATE OR REPLACE FUNCTION etl_admin.compute_nk_md5_pb_aditivo_contrato()
RETURNS trigger AS $func$
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
END
$func$ LANGUAGE plpgsql SET search_path = pg_catalog, public;

DROP TRIGGER IF EXISTS trg_compute_nk_md5 ON pb_aditivo_contrato;
CREATE TRIGGER trg_compute_nk_md5 BEFORE INSERT ON pb_aditivo_contrato
FOR EACH ROW EXECUTE FUNCTION etl_admin.compute_nk_md5_pb_aditivo_contrato();


CREATE OR REPLACE FUNCTION etl_admin.compute_nk_md5_pb_aditivo_convenio()
RETURNS trigger AS $func$
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
END
$func$ LANGUAGE plpgsql SET search_path = pg_catalog, public;

DROP TRIGGER IF EXISTS trg_compute_nk_md5 ON pb_aditivo_convenio;
CREATE TRIGGER trg_compute_nk_md5 BEFORE INSERT ON pb_aditivo_convenio
FOR EACH ROW EXECUTE FUNCTION etl_admin.compute_nk_md5_pb_aditivo_convenio();
