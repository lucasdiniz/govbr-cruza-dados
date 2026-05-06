-- sql/35c_pb_extras_synthetic_nk_dedupe.sql
--
-- 🚨 PHASE C (DESTRUTIVO): remove rows duplicadas EXATAS no legacy data.
--
-- Por que destrutivo: o ETL legacy tinha bug que inseria mesmas rows múltiplas
-- vezes (até 12x em alguns casos). Para criar UNIQUE INDEX em _nk_md5 (sql/35d),
-- precisamos primeiro deduplicar.
--
-- "EXATA": rows com _nk_md5 idêntico = mesmo payload byte-a-byte. Preservamos
-- a ocorrência com menor `id` (cronologicamente primeira). Nenhuma informação
-- real é perdida, apenas duplicatas redundantes.
--
-- IMPACT em local (referência):
--   pb_liquidacao_desconto: -2,104,286 rows
--   pb_dotacao:               -422,125
--   pb_aditivo_contrato:      -116,047
--   pb_aditivo_convenio:       -61,391
--   pb_empenho_anulacao:        -3,133
--   pb_empenho_suplementacao:     -666
--   pb_diaria:                     -95
--   ───────────────────────────────────
--   Total:                  ~2,707,743 rows deletadas
--
-- Approach: batched DELETE com PROCEDURE + COMMIT entre batches. Resumível.
--
-- PRÉ-REQUISITO: sql/35a (coluna+triggers) E sql/35b (populate _nk_md5).
--
-- ⚠️  RECOMENDAÇÕES PARA PROD:
-- 1. Backup das 7 tabelas afetadas ANTES (pg_dump -t pb_X)
-- 2. Capturar count atual em etl_watermark.bootstrap_target_count? Não — esse
--    bootstrap deveria ter rodado ANTES do 35c, capturando count COM dups.
--    Após 35c, count vai ficar abaixo do bootstrap. Se bootstrap estiver setado,
--    edite manualmente após 35c (raro caso de "correção autorizada").
-- 3. Rodar em janela de manutenção (UPDATE+DELETE de 2.7M rows pode levar 10-30 min)
-- 4. Verificar saída: cada PROCEDURE imprime contagem deletada via RAISE NOTICE
--
-- Como rodar:
--   psql -f sql/35c_pb_extras_synthetic_nk_dedupe.sql
--
-- Para rodar tabela individual:
--   psql -c "CALL etl_admin.dedupe_by_nk_md5_pb_diaria(50000);"


CREATE OR REPLACE PROCEDURE etl_admin.dedupe_by_nk_md5(table_name text, batch_size int DEFAULT 50000)
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $proc$
DECLARE
  total_deleted bigint := 0;
  n int;
BEGIN
  -- Build list of ids to delete (in temp table, single CTE, fast scan)
  EXECUTE format($f$
    CREATE TEMP TABLE _ids_to_delete ON COMMIT DROP AS
    SELECT id FROM (
      SELECT id, ROW_NUMBER() OVER (PARTITION BY _nk_md5 ORDER BY id) AS rn
      FROM %I
      WHERE _nk_md5 IS NOT NULL
    ) ranked
    WHERE rn > 1
  $f$, table_name);

  -- Index for fast deletion lookup
  CREATE INDEX ON _ids_to_delete (id);

  RAISE NOTICE '%: identified % candidate rows to delete',
               table_name, (SELECT count(*) FROM _ids_to_delete);

  LOOP
    EXECUTE format($f$
      DELETE FROM %I WHERE id IN (
        SELECT id FROM _ids_to_delete LIMIT %s
      )
    $f$, table_name, batch_size);
    GET DIAGNOSTICS n = ROW_COUNT;
    EXIT WHEN n = 0;

    -- Remove deleted ids from temp list to avoid re-scanning
    EXECUTE format($f$
      DELETE FROM _ids_to_delete WHERE id IN (
        SELECT id FROM _ids_to_delete LIMIT %s
      )
    $f$, batch_size);

    total_deleted := total_deleted + n;
    RAISE NOTICE '%: deleted % (total %)', table_name, n, total_deleted;
    COMMIT;
  END LOOP;

  RAISE NOTICE '%: DONE - total % rows deleted', table_name, total_deleted;
END
$proc$;


-- ─── Execute dedupe (idempotent: 0 rows deleted on rerun) ───────────────
-- Order: smaller tables first (faster fail-fast if something is off).

CALL etl_admin.dedupe_by_nk_md5('pb_diaria', 10000);
CALL etl_admin.dedupe_by_nk_md5('pb_empenho_suplementacao', 10000);
CALL etl_admin.dedupe_by_nk_md5('pb_empenho_anulacao', 10000);
CALL etl_admin.dedupe_by_nk_md5('pb_aditivo_convenio', 50000);
CALL etl_admin.dedupe_by_nk_md5('pb_aditivo_contrato', 50000);
CALL etl_admin.dedupe_by_nk_md5('pb_dotacao', 50000);
CALL etl_admin.dedupe_by_nk_md5('pb_liquidacao_desconto', 50000);
