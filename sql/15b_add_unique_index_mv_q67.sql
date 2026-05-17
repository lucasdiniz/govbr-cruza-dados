-- =============================================================================
-- sql/15b_add_unique_index_mv_q67.sql
-- =============================================================================
-- mv_q67_dated_pb foi criada via hotfix (PR #54) sem UNIQUE INDEX, o que impede
-- REFRESH MATERIALIZED VIEW CONCURRENTLY. Pra propagar o fix de CPF padded
-- (via fix em sql/15a_fix_cnpj_basico_contamination.sql) sem downtime, esta MV
-- precisa de UNIQUE INDEX.
--
-- Chave natural da MV: (municipio, ano, cnpj_basico). Como cnpj_basico pode ser
-- NULL apos o fix retroativo, usamos `NULLS NOT DISTINCT` (PG15+) pra forcar
-- Postgres a tratar NULLs como iguais e garantir unicidade real.
--
-- Por que NAO expression index com COALESCE:
--   PostgreSQL exige UNIQUE index com colunas PLAIN (nao expression) pra
--   REFRESH MATERIALIZED VIEW CONCURRENTLY. Expression index (ex: COALESCE)
--   pode existir mas REFRESH CONCURRENTLY ignora ele. Apontado em review
--   GPT-5.5 da PR #156.
--
-- IMPORTANTE — pre-checks:
-- 1. Dupes check primeiro: se a MV tem chaves duplicadas em
--    (municipio, ano, cnpj_basico) tratando NULLs como iguais, CREATE UNIQUE
--    INDEX falha e deixa indice INVALID em pg_index. Subsequente IF NOT EXISTS
--    pula a criacao silenciosamente (so checa nome, nao validade), entao
--    REFRESH CONCURRENTLY ainda falha com mensagem confusa "no unique index".
-- 2. DROP INDEX IF EXISTS antes do CREATE pra limpar qualquer indice INVALID
--    stale de runs anteriores que falharam (idempotente).
--
-- CREATE INDEX CONCURRENTLY: nao bloqueia leituras. Custo: 1 scan completo
-- da MV + write do indice. Estimativa em prod (B4): 2-5 min.
--
-- REQUER: PostgreSQL 15+ (NULLS NOT DISTINCT). Projeto usa PG16 — OK.
--
-- USO:
--   psql -d govbr -f sql/15b_add_unique_index_mv_q67.sql
--   ou via workflow: deploy.yml step que roda antes do refresh_mvs
-- =============================================================================

-- Guard: aborta se a MV tem duplicates antes de tentar criar o index.
-- Sem isso, CREATE UNIQUE INDEX CONCURRENTLY falha e deixa indice INVALID.
DO $$
DECLARE
    dupe_count BIGINT;
    dupe_example RECORD;
BEGIN
    -- Dupes considerando NULL == NULL (mesma semantica do NULLS NOT DISTINCT)
    SELECT COUNT(*) INTO dupe_count
    FROM (
        SELECT municipio, ano, cnpj_basico
        FROM mv_q67_dated_pb
        GROUP BY municipio, ano, cnpj_basico
        HAVING COUNT(*) > 1
    ) dupes;

    IF dupe_count > 0 THEN
        SELECT municipio, ano, cnpj_basico AS cb, COUNT(*) AS qtd
        INTO dupe_example
        FROM mv_q67_dated_pb
        GROUP BY municipio, ano, cnpj_basico
        HAVING COUNT(*) > 1
        LIMIT 1;

        RAISE EXCEPTION
            'mv_q67_dated_pb tem % chaves duplicadas em (municipio, ano, cnpj_basico). Exemplo: % / % / % (% rows). Investigue antes de criar UNIQUE INDEX.',
            dupe_count, dupe_example.municipio, dupe_example.ano,
            COALESCE(dupe_example.cb, 'NULL'), dupe_example.qtd;
    END IF;
END $$;

-- Limpa indice INVALID stale de runs anteriores (se houver). Idempotente.
DROP INDEX CONCURRENTLY IF EXISTS idx_mv_q67_dated_unique;

-- NULLS NOT DISTINCT (PG15+): trata NULLs como iguais, satisfazendo unicidade
-- real mesmo com cnpj_basico = NULL pos-cleanup retroativo. Crucial: como sao
-- colunas plain (nao expression), REFRESH MATERIALIZED VIEW CONCURRENTLY usa
-- este indice corretamente.
CREATE UNIQUE INDEX CONCURRENTLY idx_mv_q67_dated_unique
    ON mv_q67_dated_pb (municipio, ano, cnpj_basico) NULLS NOT DISTINCT;


