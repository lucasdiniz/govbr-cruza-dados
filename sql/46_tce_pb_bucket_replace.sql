-- =============================================================================
-- sql/46_tce_pb_bucket_replace.sql — substituicao por bucket (ADR-0015)
-- =============================================================================
-- Os arquivos anuais do TCE-PB (despesas-YYYY, receitas-YYYY) sao SNAPSHOTS:
-- cada publicacao e a verdade do ano inteiro. Com UPSERT_DO_NOTHING sobre o
-- _nk_md5 (hash de TODAS as colunas, ADR-0014), qualquer edicao upstream
-- (valor_pago que avanca, descricao corrigida, CO recodificado) gera hash
-- novo -> a versao nova entra e a antiga NUNCA sai -> duplicatas logicas
-- (issue #211: ~40-50% das linhas de tce_pb_despesa 2020-2026).
--
-- etl_admin.tce_pb_replace_bucket() faz o target do bucket ficar IGUAL ao
-- arquivo: remove as linhas do ano cujo _nk_md5 nao esta no arquivo. Chamado
-- pelo loader incremental DEPOIS do upsert, na MESMA transacao do arquivo
-- (atomico por bucket: falha/guarda -> rollback de tudo, inclusive do upsert).
--
-- Defesa em camadas (P1 do framework): etl_incremental continua SEM DELETE nas
-- tabelas alvo; a unica forma de remover e esta funcao, com allowlist de
-- tabelas, guardas e backup obrigatorio de cada linha removida.
--
-- Guardas (qualquer violacao -> RAISE -> rollback do arquivo inteiro):
--   G1 escopo   : toda linha do arquivo esta no bucket (despesa.ano_arquivo /
--                 receita.ano = p_bucket).
--   G2 paridade : todo hash do arquivo existe no target apos o upsert. Prova
--                 que o hash calculado do arquivo == hash do trigger; se
--                 divergir, o replace apagaria linhas validas.
--   G3 orfaos   : linha removida SEM "gemeo" (mesmo registro logico no
--                 arquivo, ex. mesmo empenho) <= max(p_min_orphan_abs,
--                 p_max_orphan_pct% do bucket). Pega arquivo truncado/errado.
--   G4 arquivo  : arquivo com 0 hashes nunca apaga nada.
-- O conjunto de gemeos vem das linhas MANTIDAS do proprio target (nao do
-- chamador), entao "versao_substituida" so remove linha que tem sucessora.
--
-- Backup: <tabela>_removido guarda a linha inteira + run/bucket/motivo.
-- Restauracao: docs/ops.md#restaurar-linhas-removidas-pelo-replace-tce-pb.
--
-- Idempotente (IF NOT EXISTS / CREATE OR REPLACE). Aplicado pelo step
-- "ETL: Incremental" do deploy.yml quando TCE-PB esta no escopo, antes do
-- runner.
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS etl_admin;

-- ── Backups ──────────────────────────────────────────────────────────────────
-- LIKE copia as colunas atuais (sem defaults/constraints: id vira INTEGER
-- simples, preservando o id original). Colunas adicionadas depois no alvo nao
-- aparecem aqui — a funcao copia so a intersecao de colunas.
CREATE TABLE IF NOT EXISTS tce_pb_despesa_removido (LIKE tce_pb_despesa);
ALTER TABLE tce_pb_despesa_removido
    ADD COLUMN IF NOT EXISTS removido_id     BIGSERIAL,
    ADD COLUMN IF NOT EXISTS removido_em     TIMESTAMPTZ NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS removido_run_id UUID,
    ADD COLUMN IF NOT EXISTS removido_bucket INTEGER,
    ADD COLUMN IF NOT EXISTS removido_motivo TEXT;
CREATE INDEX IF NOT EXISTS idx_tce_pb_despesa_removido_run
    ON tce_pb_despesa_removido (removido_run_id);

CREATE TABLE IF NOT EXISTS tce_pb_receita_removido (LIKE tce_pb_receita);
ALTER TABLE tce_pb_receita_removido
    ADD COLUMN IF NOT EXISTS removido_id     BIGSERIAL,
    ADD COLUMN IF NOT EXISTS removido_em     TIMESTAMPTZ NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS removido_run_id UUID,
    ADD COLUMN IF NOT EXISTS removido_bucket INTEGER,
    ADD COLUMN IF NOT EXISTS removido_motivo TEXT;
CREATE INDEX IF NOT EXISTS idx_tce_pb_receita_removido_run
    ON tce_pb_receita_removido (removido_run_id);

COMMENT ON TABLE tce_pb_despesa_removido IS
    'Linhas removidas de tce_pb_despesa pelo replace por bucket (ADR-0015). '
    'motivo: versao_substituida (o mesmo empenho segue no arquivo com outra '
    'versao) | ausente_no_arquivo (sumiu da publicacao TCE-PB).';
COMMENT ON TABLE tce_pb_receita_removido IS
    'Linhas removidas de tce_pb_receita pelo replace por bucket (ADR-0015).';


-- ── Funcao principal ─────────────────────────────────────────────────────────
-- p_file: tabela (normalmente TEMP da sessao do loader) com coluna `h` TEXT =
--         _nk_md5 de cada linha do arquivo, calculado com
--         etl_admin.nk_md5_<tabela>_row (mesma funcao do trigger).
CREATE OR REPLACE FUNCTION etl_admin.tce_pb_replace_bucket(
    p_table           TEXT,
    p_bucket          INTEGER,
    p_file            REGCLASS,
    p_run_id          UUID,
    p_max_orphan_pct  NUMERIC DEFAULT 1.0,
    p_min_orphan_abs  BIGINT  DEFAULT 2000,
    p_dry_run         BOOLEAN DEFAULT FALSE
) RETURNS JSONB
-- pg_temp explicito e por ULTIMO: as temp tables sao sempre referenciadas
-- como pg_temp.<nome>, e nenhuma funcao/tabela do chamador pode sombrear
-- objetos de pg_catalog/etl_admin/public.
SET search_path = pg_catalog, etl_admin, public, pg_temp
LANGUAGE plpgsql SECURITY DEFINER AS
$func$
DECLARE
    v_scope_col     TEXT;
    v_twin_expr     TEXT;
    v_backup        TEXT;
    v_cols          TEXT;
    v_file_hashes   BIGINT;
    v_scope_before  BIGINT;
    v_kept          BIGINT;
    v_out_of_scope  BIGINT;
    v_del_twin      BIGINT;
    v_del_orphan    BIGINT;
    v_orphan_limit  BIGINT;
    v_deleted       BIGINT := 0;
    v_stats         JSONB;
BEGIN
    -- Allowlist: tabela -> coluna de escopo, chave "gemeo", backup.
    IF p_table = 'tce_pb_despesa' THEN
        v_scope_col := 'ano_arquivo';
        v_twin_expr := 'etl_admin.row_hash_md5('
            'etl_admin.nk_norm_text(t.municipio), etl_admin.nk_norm_text(t.codigo_ug), '
            'etl_admin.nk_norm_text(t.numero_empenho), to_char(t.data_empenho, ''YYYY-MM-DD''))';
        v_backup := 'tce_pb_despesa_removido';
    ELSIF p_table = 'tce_pb_receita' THEN
        v_scope_col := 'ano';
        v_twin_expr := 'etl_admin.row_hash_md5('
            'etl_admin.nk_norm_text(t.municipio), etl_admin.nk_norm_text(t.codigo_ug), '
            'etl_admin.nk_norm_text(t.mes_ano), etl_admin.nk_norm_text(t.codigo_receita))';
        v_backup := 'tce_pb_receita_removido';
    ELSE
        RAISE EXCEPTION 'tce_pb_replace_bucket: tabela % fora da allowlist', p_table;
    END IF;

    IF p_bucket IS NULL OR p_run_id IS NULL OR p_file IS NULL THEN
        RAISE EXCEPTION 'tce_pb_replace_bucket: parametros obrigatorios nulos';
    END IF;
    IF p_max_orphan_pct IS NULL OR p_max_orphan_pct < 0 OR p_max_orphan_pct > 100
       OR p_min_orphan_abs IS NULL OR p_min_orphan_abs < 0 THEN
        RAISE EXCEPTION 'tce_pb_replace_bucket: limites de orfaos invalidos';
    END IF;

    -- Hashes do arquivo (distintos).
    DROP TABLE IF EXISTS pg_temp._rb_file;
    EXECUTE format(
        'CREATE TEMP TABLE _rb_file ON COMMIT DROP AS
           SELECT DISTINCT h FROM %s WHERE h IS NOT NULL', p_file);
    CREATE UNIQUE INDEX ON pg_temp._rb_file (h);
    ANALYZE pg_temp._rb_file;
    SELECT count(*) INTO v_file_hashes FROM pg_temp._rb_file;

    -- G4: arquivo vazio nunca apaga.
    IF v_file_hashes = 0 THEN
        RAISE EXCEPTION 'GUARDA_REPLACE G4: % bucket % — arquivo sem linhas; nada sera removido',
            p_table, p_bucket;
    END IF;

    -- Linhas atuais do bucket (1 seq scan).
    DROP TABLE IF EXISTS pg_temp._rb_scope;
    EXECUTE format(
        'CREATE TEMP TABLE _rb_scope ON COMMIT DROP AS
           SELECT t.id, t._nk_md5 AS h, %s AS twin FROM public.%I t WHERE t.%I = $1',
        v_twin_expr, p_table, v_scope_col) USING p_bucket;
    ANALYZE pg_temp._rb_scope;
    SELECT count(*) INTO v_scope_before FROM pg_temp._rb_scope;

    -- Linhas mantidas = do bucket com hash presente no arquivo.
    DROP TABLE IF EXISTS pg_temp._rb_keep;
    CREATE TEMP TABLE _rb_keep ON COMMIT DROP AS
        SELECT s.id, s.h, s.twin FROM pg_temp._rb_scope s
        JOIN pg_temp._rb_file f ON f.h = s.h;
    SELECT count(*) INTO v_kept FROM pg_temp._rb_keep;

    -- G1 + G2: todo hash do arquivo tem que estar no target E dentro do bucket.
    IF v_kept <> v_file_hashes THEN
        EXECUTE format(
            'SELECT count(*) FROM public.%I t JOIN pg_temp._rb_file f ON f.h = t._nk_md5
              WHERE t.%I IS DISTINCT FROM $1', p_table, v_scope_col)
            INTO v_out_of_scope USING p_bucket;
        IF v_out_of_scope > 0 THEN
            RAISE EXCEPTION 'GUARDA_REPLACE G1: % bucket % — % linha(s) do arquivo fora do bucket (%.% <> %)',
                p_table, p_bucket, v_out_of_scope, p_table, v_scope_col, p_bucket;
        END IF;
        RAISE EXCEPTION 'GUARDA_REPLACE G2: % bucket % — % hash(es) do arquivo ausentes no target apos o upsert (paridade hash arquivo x trigger quebrada)',
            p_table, p_bucket, v_file_hashes - v_kept;
    END IF;

    CREATE INDEX ON pg_temp._rb_keep (twin);
    ANALYZE pg_temp._rb_keep;

    -- Candidatas a remocao + motivo.
    DROP TABLE IF EXISTS pg_temp._rb_del;
    CREATE TEMP TABLE _rb_del ON COMMIT DROP AS
        SELECT s.id,
               EXISTS (SELECT 1 FROM pg_temp._rb_keep k WHERE k.twin = s.twin) AS tem_gemeo
        FROM pg_temp._rb_scope s
        WHERE NOT EXISTS (SELECT 1 FROM pg_temp._rb_file f WHERE f.h = s.h);
    SELECT count(*) FILTER (WHERE tem_gemeo), count(*) FILTER (WHERE NOT tem_gemeo)
      INTO v_del_twin, v_del_orphan FROM pg_temp._rb_del;

    v_orphan_limit := GREATEST(p_min_orphan_abs, floor(v_scope_before * p_max_orphan_pct / 100.0)::BIGINT);

    v_stats := jsonb_build_object(
        'tabela', p_table, 'bucket', p_bucket,
        'linhas_bucket_antes', v_scope_before,
        'hashes_arquivo', v_file_hashes,
        'mantidas', v_kept,
        'remover_versao_substituida', v_del_twin,
        'remover_ausente_no_arquivo', v_del_orphan,
        'limite_ausentes', v_orphan_limit,
        'linhas_bucket_depois', v_scope_before - v_del_twin - v_del_orphan,
        'dry_run', p_dry_run);

    -- G3: remocoes sem sucessora limitadas.
    IF v_del_orphan > v_orphan_limit THEN
        RAISE EXCEPTION 'GUARDA_REPLACE G3: % bucket % — % linha(s) sumiram do arquivo (limite %). stats=%',
            p_table, p_bucket, v_del_orphan, v_orphan_limit, v_stats;
    END IF;

    IF p_dry_run OR (v_del_twin + v_del_orphan) = 0 THEN
        RETURN v_stats || jsonb_build_object('removidas', 0);
    END IF;

    -- Colunas comuns alvo x backup (o backup pode ter sido criado antes de
    -- uma coluna nova no alvo).
    SELECT string_agg(quote_ident(c.column_name), ', ' ORDER BY c.ordinal_position)
      INTO v_cols
      FROM information_schema.columns c
     WHERE c.table_schema = 'public' AND c.table_name = p_table
       AND EXISTS (SELECT 1 FROM information_schema.columns b
                    WHERE b.table_schema = 'public' AND b.table_name = v_backup
                      AND b.column_name = c.column_name);
    IF v_cols IS NULL THEN
        RAISE EXCEPTION 'tce_pb_replace_bucket: backup % ausente (rode sql/46)', v_backup;
    END IF;

    EXECUTE format(
        'WITH del AS (
            DELETE FROM public.%1$I t USING pg_temp._rb_del d
             WHERE t.id = d.id
            RETURNING t.*, d.tem_gemeo
         )
         INSERT INTO public.%2$I (%3$s, removido_run_id, removido_bucket, removido_motivo)
         SELECT %3$s, $1, $2,
                CASE WHEN tem_gemeo THEN ''versao_substituida'' ELSE ''ausente_no_arquivo'' END
           FROM del',
        p_table, v_backup, v_cols) USING p_run_id, p_bucket;
    GET DIAGNOSTICS v_deleted = ROW_COUNT;

    IF v_deleted <> v_del_twin + v_del_orphan THEN
        RAISE EXCEPTION 'tce_pb_replace_bucket: removidas % <> previstas %',
            v_deleted, v_del_twin + v_del_orphan;
    END IF;

    RETURN v_stats || jsonb_build_object('removidas', v_deleted);
END;
$func$;

COMMENT ON FUNCTION etl_admin.tce_pb_replace_bucket IS
    'Replace por bucket TCE-PB (ADR-0015): remove do ano as linhas cujo _nk_md5 '
    'nao esta no arquivo, com guardas G1-G4 e backup em <tabela>_removido.';

REVOKE ALL ON FUNCTION etl_admin.tce_pb_replace_bucket(TEXT, INTEGER, REGCLASS, UUID, NUMERIC, BIGINT, BOOLEAN) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'etl_incremental') THEN
        EXECUTE 'GRANT EXECUTE ON FUNCTION etl_admin.tce_pb_replace_bucket(TEXT, INTEGER, REGCLASS, UUID, NUMERIC, BIGINT, BOOLEAN) TO etl_incremental';
    END IF;
END $$;
