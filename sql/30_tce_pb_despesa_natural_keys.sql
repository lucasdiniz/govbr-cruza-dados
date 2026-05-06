-- TCE-PB despesa: UNIQUE INDEX expression-based (resolve '' vs NULL)
--
-- Legacy ETL pode ter inserido literal '' em cols opcionais; nosso
-- incremental converte CSV vazio para NULL. ON CONFLICT precisa tratar
-- '' e NULL como equivalentes.
--
-- Solução: COALESCE(NULLIF(col, ''), '__NULL__')
--   '' → '__NULL__', NULL → '__NULL__', 'X' → 'X'
--
-- ON CONFLICT em build_upsert_sql precisa usar EXATAMENTE a mesma expressão.

DROP INDEX IF EXISTS ix_tce_pb_despesa_nk;

CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS ix_tce_pb_despesa_nk
ON tce_pb_despesa (
    municipio, codigo_ug, numero_empenho, data_empenho, ano_arquivo,
    COALESCE(NULLIF(codigo_subelemento, ''), '__NULL__'),
    COALESCE(NULLIF(codigo_fonte_recurso, ''), '__NULL__'),
    COALESCE(NULLIF(numero_obra, ''), '__NULL__'),
    COALESCE(NULLIF(numero_licitacao, ''), '__NULL__'),
    COALESCE(NULLIF(codigo_natureza, ''), '__NULL__')
);
