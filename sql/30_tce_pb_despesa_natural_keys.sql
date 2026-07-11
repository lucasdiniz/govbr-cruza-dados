-- TCE-PB despesa: NK natural — DEPRECATED (ADR-0014)
--
-- A NK natural de tce_pb_despesa NAO e unica: analise empirica em prod (2026-06)
-- encontrou 1037 grupos (2530 rows) que compartilham esta NK mas sao registros
-- financeiros DISTINTOS (valor_*/cpf_cnpj/nome_credor/historico diferentes).
-- Um UNIQUE INDEX nesta NK seria semanticamente errado e UPSERT_DO_NOTHING
-- pularia registros distintos silenciosamente.
--
-- Substituida por synthetic md5 (_nk_md5):
--   * sql/42_tce_pb_synthetic_nk.sql  (coluna + trigger + funcao de hash)
--   * sql/42z_tce_pb_finalize.sql     (dedupe + UNIQUE INDEX ix_tce_pb_despesa_nk_md5)
--
-- Este arquivo agora apenas REMOVE o index natural antigo (caso runs/POCs
-- anteriores o tenham criado). NAO recria o UNIQUE INDEX natural.

DROP INDEX IF EXISTS ix_tce_pb_despesa_nk;
