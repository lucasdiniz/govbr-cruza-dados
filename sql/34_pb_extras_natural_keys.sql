-- 13 UNIQUE INDEXes for Dados-PB extras tables
-- All varchar NK cols are wrapped in COALESCE(NULLIF(c, ''), '__NULL__') to
-- treat '' = NULL = unknown identically. INTs/SMALLINTs/DATEs use plain refs.
--
-- Pattern matches PG-normalized expression form: (col)::text + ''::text + '__NULL__'::text
-- See commit 2107597 for context.
--
-- 6 dessas 13 tabelas usam NK simples (este arquivo).
-- 7 outras precisam synthetic NK md5 (ver sql/35a-d) por causa de duplicações
-- exatas no legacy data.
--
-- IMPORTANT FOR PROD: Each CREATE INDEX CONCURRENTLY must run OUTSIDE any
-- transaction block. Run via psql -f (not -c) to avoid implicit BEGIN.
-- If any CONCURRENTLY index creation fails partway, the index is left INVALID;
-- DROP it manually before retrying.
--
-- Pre-flight check (run separately): SELECT * FROM v_etl_status; ensure no
-- active runs before applying. ETL framework supports re-entrant runs via
-- IF NOT EXISTS, so safe to re-run.

CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS ix_pb_saude_nk ON public.pb_saude (
    COALESCE(NULLIF(codigo_envio, ''), '__NULL__'),
    COALESCE(NULLIF(codigo_lancamento, ''), '__NULL__')
);

CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS ix_pb_pagamento_anulacao_nk ON public.pb_pagamento_anulacao (
    exercicio,
    COALESCE(NULLIF(codigo_unidade_gestora, ''), '__NULL__'),
    COALESCE(NULLIF(numero_empenho, ''), '__NULL__'),
    COALESCE(NULLIF(numero_guia_devolucao, ''), '__NULL__'),
    COALESCE(NULLIF(numero_autorizacao_pagamento, ''), '__NULL__')
);

CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS ix_pb_liquidacao_despesa_nk ON public.pb_liquidacao_despesa (
    exercicio,
    COALESCE(NULLIF(codigo_orgao, ''), '__NULL__'),
    COALESCE(NULLIF(numero_empenho, ''), '__NULL__'),
    COALESCE(NULLIF(documento, ''), '__NULL__'),
    data_movimentacao
);

CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS ix_pb_liquidacao_cge_nk ON public.pb_liquidacao_cge (
    exercicio,
    COALESCE(NULLIF(codigo_orgao, ''), '__NULL__'),
    COALESCE(NULLIF(numero_empenho, ''), '__NULL__'),
    COALESCE(NULLIF(documento, ''), '__NULL__'),
    data_movimentacao
);

CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS ix_pb_convenio_nk ON public.pb_convenio (
    COALESCE(NULLIF(codigo_convenio, ''), '__NULL__'),
    COALESCE(NULLIF(numero_registro_cge, ''), '__NULL__')
);

CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS ix_pb_unidade_gestora_nk ON public.pb_unidade_gestora (
    exercicio,
    COALESCE(NULLIF(codigo_unidade_gestora, ''), '__NULL__')
);
