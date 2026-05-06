-- ETL Incremental Framework — Onda PB POC (Phase 1a)
-- Migration: etl_download_log
--
-- Tracking de download por-arquivo. Habilita conditional GET / HEAD probe e
-- detecção de mudança de conteúdo (content_sha256) para invalidar bucket_token
-- em etl_watermark.
--
-- Princípios:
--   D15/D16 (plan v7): download incremental separado do processamento.
--   - HEAD probe (ou conditional GET com If-None-Match / If-Modified-Since)
--     decide se baixa ou não.
--   - sha256 do conteúdo permite detectar mudança mesmo se servidor não respeitar
--     ETag/Last-Modified (caso comum em sources gov.br BR).
--   - last_checked_at != last_downloaded_at: distinguir "verifiquei e não mudou"
--     de "baixei nova versão".
--   - bucket_id: liga arquivo a janela do cursor (e.g., '2024' para year window;
--     '2024-03' para month window). Permite refetch policy declarativa.

CREATE TABLE IF NOT EXISTS etl_download_log (
    id                 BIGSERIAL PRIMARY KEY,
    source             TEXT NOT NULL,           -- 'tce_pb' | 'dados_pb'
    table_name         TEXT,                    -- target table (opcional — alguns ZIPs servem múltiplas tables)
    bucket_id          TEXT NOT NULL,           -- '2024' (year), '2024-03' (month), 'snapshot' (no cursor)
    -- Source identity
    url                TEXT NOT NULL,
    dest_path          TEXT NOT NULL,           -- caminho local
    -- HTTP cache headers
    etag               TEXT,
    last_modified      TEXT,                    -- raw header value (RFC 7231 IMF-fixdate)
    content_length     BIGINT,
    -- Content fingerprint (post-download)
    content_sha256     TEXT,                    -- sha256 do arquivo completo (após extract de ZIP, hash do CSV)
    -- Lifecycle
    first_seen_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_checked_at    TIMESTAMPTZ NOT NULL DEFAULT now(),  -- HEAD/conditional GET timestamp
    last_downloaded_at TIMESTAMPTZ,                          -- última vez que efetivamente baixou
    last_status        TEXT NOT NULL,                        -- 'ok' | 'not_modified' | 'failed' | 'partial'
    last_error         TEXT,
    -- Run correlation (audit)
    last_run_id        UUID,                    -- run que efetuou o último download/check
    -- Unique por (source, table_name, bucket_id, url) garante 1 row por arquivo
    UNIQUE (source, table_name, bucket_id, url),
    CHECK (last_status IN ('ok', 'not_modified', 'failed', 'partial'))
);

COMMENT ON TABLE etl_download_log IS
    'Tracking por-arquivo de download. Habilita conditional GET + content-hash invalidation. Plan v7 D15/D16.';
COMMENT ON COLUMN etl_download_log.content_sha256 IS
    'sha256 do conteúdo. Mudança vs valor anterior invalida bucket_token em etl_watermark.';
COMMENT ON COLUMN etl_download_log.bucket_id IS
    'Identificador da janela do cursor: ano (2024), ano-mês (2024-03), ou ''snapshot'' para fontes sem cursor.';
COMMENT ON COLUMN etl_download_log.last_checked_at IS
    'HEAD probe ou conditional GET timestamp. != last_downloaded_at quando 304 Not Modified.';

-- Index para queries de orchestrator: "quais arquivos do bucket X?"
CREATE INDEX IF NOT EXISTS idx_etl_download_log_bucket
    ON etl_download_log(source, bucket_id, last_checked_at DESC);

-- Index parcial para detectar arquivos com falha recente
CREATE INDEX IF NOT EXISTS idx_etl_download_log_failed
    ON etl_download_log(source, last_checked_at DESC)
    WHERE last_status IN ('failed', 'partial');

-- ──────────────────────────────────────────────────────────────────────────────
-- Trigger: bloqueia DELETE para etl_incremental (download log é audit).
-- Job de retention via etl_admin (futuro).
-- ──────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION etl_admin.protect_download_log_no_delete()
RETURNS TRIGGER
SET search_path = pg_catalog, etl_admin, public
LANGUAGE plpgsql AS
$func$
BEGIN
    IF current_user = 'etl_incremental' THEN
        RAISE EXCEPTION 'etl_download_log: DELETE forbidden for etl_incremental role';
    END IF;
    RETURN OLD;
END;
$func$;

DROP TRIGGER IF EXISTS etl_download_log_no_delete ON etl_download_log;
CREATE TRIGGER etl_download_log_no_delete
    BEFORE DELETE ON etl_download_log
    FOR EACH ROW EXECUTE FUNCTION etl_admin.protect_download_log_no_delete();

-- ──────────────────────────────────────────────────────────────────────────────
-- SECURITY DEFINER function: invalidate_bucket_token
--
-- Quando download_log detecta content_sha256 mudou, precisa NULLar bucket_token
-- em etl_watermark para forçar reprocessing. Mas etl_incremental NÃO tem UPDATE
-- direto em etl_watermark (apenas via set_watermark). Esta função é o caminho.
-- ──────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION etl_admin.invalidate_bucket_token(
    p_run_id   UUID,
    p_source   TEXT,
    p_table    TEXT,
    p_reason   TEXT
) RETURNS BOOLEAN
SET search_path = pg_catalog, etl_admin, public
LANGUAGE plpgsql SECURITY DEFINER
AS $func$
DECLARE
    v_run_alive BOOLEAN;
BEGIN
    -- Fence check
    SELECT EXISTS(SELECT 1 FROM etl_run_log WHERE run_id = p_run_id AND status = 'running')
        INTO v_run_alive;
    IF NOT v_run_alive THEN
        RAISE EXCEPTION 'invalidate_bucket_token: run % not running', p_run_id;
    END IF;

    IF p_reason IS NULL OR length(trim(p_reason)) < 5 THEN
        RAISE EXCEPTION 'invalidate_bucket_token: reason required';
    END IF;

    UPDATE etl_watermark
    SET bucket_token = NULL,
        last_error = format('bucket_token invalidated by run %s: %s', p_run_id, p_reason)
    WHERE source = p_source AND table_name = p_table
      AND bucket_token IS NOT NULL;

    RETURN FOUND;
END;
$func$;

COMMENT ON FUNCTION etl_admin.invalidate_bucket_token(UUID, TEXT, TEXT, TEXT) IS
    'Invalida bucket_token em etl_watermark quando download detecta content_sha256 mudou. Força reprocessing no próximo run (idempotent via UPSERT).';

-- ──────────────────────────────────────────────────────────────────────────────
-- SECURITY DEFINER: upsert_download_log_check (HEAD probe / conditional GET resultado)
-- ──────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION etl_admin.upsert_download_log_check(
    p_run_id          UUID,
    p_source          TEXT,
    p_table           TEXT,
    p_bucket_id       TEXT,
    p_url             TEXT,
    p_dest_path       TEXT,
    p_etag            TEXT,
    p_last_modified   TEXT,
    p_content_length  BIGINT,
    p_status          TEXT
) RETURNS VOID
SET search_path = pg_catalog, etl_admin, public
LANGUAGE plpgsql SECURITY DEFINER
AS $func$
BEGIN
    IF p_status NOT IN ('not_modified', 'failed', 'partial') THEN
        RAISE EXCEPTION 'upsert_download_log_check: invalid status % (use upsert_download_log_done for ok)', p_status;
    END IF;

    INSERT INTO etl_download_log (
        source, table_name, bucket_id, url, dest_path,
        etag, last_modified, content_length,
        first_seen_at, last_checked_at, last_status, last_run_id
    ) VALUES (
        p_source, p_table, p_bucket_id, p_url, p_dest_path,
        p_etag, p_last_modified, p_content_length,
        now(), now(), p_status, p_run_id
    )
    ON CONFLICT (source, table_name, bucket_id, url) DO UPDATE SET
        last_checked_at = now(),
        etag            = COALESCE(EXCLUDED.etag, etl_download_log.etag),
        last_modified   = COALESCE(EXCLUDED.last_modified, etl_download_log.last_modified),
        content_length  = COALESCE(EXCLUDED.content_length, etl_download_log.content_length),
        last_status     = EXCLUDED.last_status,
        last_run_id     = EXCLUDED.last_run_id;
END;
$func$;

COMMENT ON FUNCTION etl_admin.upsert_download_log_check IS
    'Atualiza última verificação (HEAD probe ou conditional GET 304/failed). Não muda last_downloaded_at.';

-- ──────────────────────────────────────────────────────────────────────────────
-- SECURITY DEFINER: upsert_download_log_done (download bem-sucedido)
-- Retorna TRUE se content_sha256 mudou (caller deve chamar invalidate_bucket_token).
-- ──────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION etl_admin.upsert_download_log_done(
    p_run_id          UUID,
    p_source          TEXT,
    p_table           TEXT,
    p_bucket_id       TEXT,
    p_url             TEXT,
    p_dest_path       TEXT,
    p_etag            TEXT,
    p_last_modified   TEXT,
    p_content_length  BIGINT,
    p_content_sha256  TEXT
) RETURNS BOOLEAN
SET search_path = pg_catalog, etl_admin, public
LANGUAGE plpgsql SECURITY DEFINER
AS $func$
DECLARE
    v_existing_sha TEXT;
    v_changed BOOLEAN := FALSE;
BEGIN
    SELECT content_sha256 INTO v_existing_sha
    FROM etl_download_log
    WHERE source = p_source
      AND table_name IS NOT DISTINCT FROM p_table
      AND bucket_id = p_bucket_id
      AND url = p_url;

    -- Mudou se: novo (NULL) ou hash diferente
    v_changed := (v_existing_sha IS NULL) OR (v_existing_sha != p_content_sha256);

    INSERT INTO etl_download_log (
        source, table_name, bucket_id, url, dest_path,
        etag, last_modified, content_length, content_sha256,
        first_seen_at, last_checked_at, last_downloaded_at,
        last_status, last_run_id
    ) VALUES (
        p_source, p_table, p_bucket_id, p_url, p_dest_path,
        p_etag, p_last_modified, p_content_length, p_content_sha256,
        now(), now(), now(),
        'ok', p_run_id
    )
    ON CONFLICT (source, table_name, bucket_id, url) DO UPDATE SET
        last_checked_at    = now(),
        last_downloaded_at = now(),
        etag               = EXCLUDED.etag,
        last_modified      = EXCLUDED.last_modified,
        content_length     = EXCLUDED.content_length,
        content_sha256     = EXCLUDED.content_sha256,
        last_status        = 'ok',
        last_run_id        = EXCLUDED.last_run_id,
        last_error         = NULL;

    RETURN v_changed;
END;
$func$;

COMMENT ON FUNCTION etl_admin.upsert_download_log_done IS
    'Registra download bem-sucedido. Retorna TRUE se content_sha256 mudou (caller deve invalidar bucket_token).';
