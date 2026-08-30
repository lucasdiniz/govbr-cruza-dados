-- Corrige o janitor para o formato atual de staging com bucket no nome.
-- Fonte canônica: sql/27_etl_admin_security_definer.sql.

CREATE OR REPLACE FUNCTION etl_admin.cleanup_orphan_staging()
RETURNS INT
SET search_path = pg_catalog, etl_admin, public
LANGUAGE plpgsql SECURITY DEFINER
AS $func$
DECLARE
    r       RECORD;
    v_count INT := 0;
    v_run8  TEXT;
BEGIN
    FOR r IN
        SELECT schemaname, tablename
        FROM pg_tables
        WHERE schemaname = 'etl_staging'
          AND tablename LIKE '\_stg\_%' ESCAPE '\'
    LOOP
        v_run8 := substring(
            r.tablename
            FROM '^_stg_([a-f0-9]{8})_(?:[a-zA-Z0-9_]{1,8}_)?\d+_(?:raw|typed|final)$'
        );
        IF v_run8 IS NULL THEN
            v_run8 := substring(
                r.tablename
                FROM '^_stg_.+_([a-f0-9]{8})_(?:[a-zA-Z0-9_]{1,8}_)?\d+_(?:raw|typed|final)$'
            );
        END IF;

        IF v_run8 IS NULL THEN
            CONTINUE;
        END IF;

        IF EXISTS (
            SELECT 1 FROM etl_run_log
            WHERE substring(run_id::text, 1, 8) = v_run8
        ) AND NOT EXISTS (
            SELECT 1 FROM etl_run_log
            WHERE substring(run_id::text, 1, 8) = v_run8
              AND status = 'running'
        ) THEN
            BEGIN
                EXECUTE format(
                    'DROP TABLE IF EXISTS %I.%I',
                    r.schemaname,
                    r.tablename
                );
                v_count := v_count + 1;
            EXCEPTION WHEN OTHERS THEN
                RAISE NOTICE 'cleanup_orphan_staging: failed to drop %.%: %',
                    r.schemaname, r.tablename, SQLERRM;
            END;
        END IF;
    END LOOP;

    RETURN v_count;
END;
$func$;

COMMENT ON FUNCTION etl_admin.cleanup_orphan_staging() IS
    'Janitor de etl_staging para nomes com ou sem bucket; preserva runs ativas.';

GRANT EXECUTE ON FUNCTION etl_admin.cleanup_orphan_staging()
TO etl_incremental;
