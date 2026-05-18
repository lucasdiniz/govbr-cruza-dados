-- Migration: Bolsa Familia para o framework ETL incremental (P1-P6).
-- Estrategia: synthetic NK md5 (padrao sql/35a-d das 7 tabelas pb_extras).
--
-- Aplicada pelo step "ETL: Incremental" do deploy.yml (etl_phase=incremental).
-- Idempotente — pode ser re-aplicada sem dano.
--
-- IMPORTANTE: CREATE INDEX CONCURRENTLY exige execucao FORA de transacao
-- explicita. Aplicar via `psql -v ON_ERROR_STOP=1 -f sql/41_*.sql` SEM
-- `--single-transaction`. Se interrompida no meio, o index pode ficar
-- INVALID — o bloco DO $$ no final detecta e aborta.
--
-- Por que synthetic NK md5 e nao NK natural?
--   Empirical analysis (2026-05) na base local + VM revelou:
--   * 21% dos rows tem cpf_favorecido='' (CADUNICO com CPF nao-vinculado;
--     adultos reais, NAO menores como inicialmente assumido).
--   * Portal publica parcelas RETROATIVAS no mesmo mes_competencia com
--     mes_referencia diferentes (legitimo — recebimentos atrasados).
--   * Nenhuma combinacao razoavel de cols naturais gera NK 100%-unica
--     sem perda de dado: trio (mes_comp, cpf, nis) tem 93k dups; mesmo
--     5-uplo (+ mes_referencia + cd_municipio_siafi) tem 36 dups.
--   * 9 grupos com TODAS 9 cols iguais (22 rows) sao true duplicates legacy.
--   Synthetic md5 da hash de todas as 9 cols cobre 100% dos casos sem
--   perda; segue padrao pb_extras + tem dedupe step inline.
--
-- Ver ADR-0010.


-- ============================================================================
-- 1. Colunas auxiliares (idempotente)
-- ============================================================================

-- cpf_digitos: populado pelo framework via derived_columns. Em prod legada
-- foi adicionada por etl/15_normalizar.py.
ALTER TABLE bolsa_familia
    ADD COLUMN IF NOT EXISTS cpf_digitos TEXT;

COMMENT ON COLUMN bolsa_familia.cpf_digitos IS
    'Digitos do cpf_favorecido com nao-numericos removidos. '
    'Bolsa Familia divulga CPF mascarado como ***.NNN.NNN-** — esta coluna '
    'contem apenas os 6 digitos centrais (NAO 11 como em outras tabelas). '
    'Para join cross-source, ver mv_pessoa_pb.cpf_digitos_6.';

-- inserted_at: auditoria de quando o framework inseriu a row.
ALTER TABLE bolsa_familia
    ADD COLUMN IF NOT EXISTS inserted_at TIMESTAMPTZ DEFAULT now();

COMMENT ON COLUMN bolsa_familia.inserted_at IS
    'Timestamp de insercao da row pelo framework ETL incremental. '
    'Para rows inseridas pela fase classica legada (pre-ADR-0010) o valor '
    'sera o timestamp da primeira aplicacao desta migration.';

-- _nk_md5: synthetic NK calculada via trigger BEFORE INSERT (etapa 2 abaixo).
ALTER TABLE bolsa_familia
    ADD COLUMN IF NOT EXISTS _nk_md5 TEXT;

COMMENT ON COLUMN bolsa_familia._nk_md5 IS
    'Hash md5 de todas 9 cols (mes_competencia, mes_referencia, uf, '
    'cd_municipio_siafi, nm_municipio, cpf_favorecido, nis_favorecido, '
    'nm_favorecido, valor_parcela). Calculado por trigger BEFORE INSERT. '
    'UNIQUE INDEX em (_nk_md5) garante idempotencia em republish do Portal. '
    'Ver sql/35a (padrao pb_extras) e ADR-0010.';


-- ============================================================================
-- 2. Trigger BEFORE INSERT para popular _nk_md5
-- ============================================================================
-- Reusa funcao etl_admin.row_hash_md5() definida em sql/35a (collision-free
-- via array_to_json injective serialization).

CREATE OR REPLACE FUNCTION etl_admin.compute_nk_md5_bolsa_familia()
RETURNS trigger AS $func$
BEGIN
  IF NEW._nk_md5 IS NULL THEN
    NEW._nk_md5 := etl_admin.row_hash_md5(
      coalesce(NEW.mes_competencia, ''),
      coalesce(NEW.mes_referencia, ''),
      coalesce(NEW.uf, ''),
      coalesce(NEW.cd_municipio_siafi, ''),
      coalesce(NEW.nm_municipio, ''),
      coalesce(NEW.cpf_favorecido, ''),
      coalesce(NEW.nis_favorecido, ''),
      coalesce(NEW.nm_favorecido, ''),
      coalesce(NEW.valor_parcela::text, '')
    );
  END IF;
  RETURN NEW;
END
$func$ LANGUAGE plpgsql SET search_path = pg_catalog, public;

DROP TRIGGER IF EXISTS trg_compute_nk_md5 ON bolsa_familia;
CREATE TRIGGER trg_compute_nk_md5 BEFORE INSERT ON bolsa_familia
FOR EACH ROW EXECUTE FUNCTION etl_admin.compute_nk_md5_bolsa_familia();


-- ============================================================================
-- 3. Popular _nk_md5 nas rows existentes (BATCHED — padrao sql/35b)
-- ============================================================================
-- ~18,7M rows em prod. UPDATE single-statement gera WAL e bloat extremos
-- (testado local: 30s → 3MB de progresso, ETA 6-10h). Batched com COMMIT
-- entre cada batch de 100k rows: ~3-5 min em SSD, segura para prod ate sob
-- query load (lock fica curto, autovacuum tem chance de limpar dead tuples).
--
-- Resumivel: WHERE _nk_md5 IS NULL → so atualiza rows ainda nao populadas.
-- Pode ser interrompido (Ctrl+C) e re-executado sem perda.
--
-- IMPORTANTE: COMMIT dentro de PROCEDURE precisa rodar fora de transacao
-- explicita. No PG 16, `psql -c "CALL ..."`, `psql -f` com a CALL inline e
-- ate stdin wrappam o comando em transacao implicita, fazendo o COMMIT
-- interno da PROCEDURE falhar com "encerramento de transacao invalido".
-- O step do deploy.yml chama via Python autocommit explicito:
--    python -m etl.refresh_post_incremental --source bolsa_familia --populate-only
-- A funcao Python em etl/refresh_post_incremental.py:populate_nk_md5_bolsa_familia
-- replica a logica desta PROCEDURE com `conn.autocommit = True` antes do
-- loop. A PROCEDURE serve como (a) documentacao SQL da logica de batches,
-- (b) ponto de entrada para recovery interativo via `psql` (sessao
-- interativa NAO wrappa CALL em transacao):
--    PGPASSWORD=$PASS psql -U govbr -d govbr
--    govbr=# CALL etl_admin.populate_nk_md5_bolsa_familia(100000);

CREATE OR REPLACE PROCEDURE etl_admin.populate_nk_md5_bolsa_familia(batch_size int DEFAULT 100000)
LANGUAGE plpgsql SET search_path = pg_catalog, public AS $$
DECLARE
  n int;
  total bigint := 0;
BEGIN
  LOOP
    UPDATE bolsa_familia SET _nk_md5 = etl_admin.row_hash_md5(
      coalesce(mes_competencia, ''),
      coalesce(mes_referencia, ''),
      coalesce(uf, ''),
      coalesce(cd_municipio_siafi, ''),
      coalesce(nm_municipio, ''),
      coalesce(cpf_favorecido, ''),
      coalesce(nis_favorecido, ''),
      coalesce(nm_favorecido, ''),
      coalesce(valor_parcela::text, '')
    )
    WHERE id IN (
      SELECT id FROM bolsa_familia
      WHERE _nk_md5 IS NULL ORDER BY id LIMIT batch_size
    );
    GET DIAGNOSTICS n = ROW_COUNT;
    EXIT WHEN n = 0;
    total := total + n;
    RAISE NOTICE 'bolsa_familia: populated % rows (total %)', n, total;
    COMMIT;
  END LOOP;
  RAISE NOTICE 'bolsa_familia: DONE - total % rows populated', total;
END $$;

-- NAO chamamos a procedure aqui (psql -f wrapping). Deploy step chama
-- separadamente: `psql -c "CALL etl_admin.populate_nk_md5_bolsa_familia(100000);"`
--
-- Em seguida, rodar sql/41z_bolsa_familia_finalize.sql que faz dedupe + UNIQUE INDEX.


-- ============================================================================
-- Steps 4-7 (dedupe + UNIQUE INDEX + validation) ficam em sql/41z_*.sql.
-- Motivo: precisam rodar DEPOIS da CALL (que tem que ser comando psql -c
-- separado por causa de COMMIT-em-PROCEDURE). Ver ADR-0010 secao "Deploy
-- ordering" e docs/ops.md.
-- ============================================================================
