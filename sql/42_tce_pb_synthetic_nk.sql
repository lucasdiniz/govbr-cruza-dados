-- Migration: tce_pb_despesa/servidor/licitacao/receita para NK sintetica md5.
-- Framework ETL incremental (P1-P6). Padrao sql/35a-d (pb_extras) e sql/41 (BF).
--
-- Aplicada pelo step "ETL: Incremental" do deploy.yml quando TCE-PB esta no
-- escopo (etl_phase=incremental). Idempotente — pode ser re-aplicada sem dano.
--
-- IMPORTANTE: os UNIQUE INDEX CONCURRENTLY ficam em sql/42z (rodam APOS o
-- populate). Esta migration so tem DDL segura em transacao. Aplicar via
-- `psql -v ON_ERROR_STOP=1 -f` SEM `--single-transaction`.
--
-- ── Por que synthetic md5 e nao NK natural? (ADR-0014) ──────────────────────
--
-- Analise empirica em prod (2026-06):
--
-- 1. tce_pb_despesa (16.2M rows): a NK candidata do spec tem 1037 grupos
--    (2530 rows) com >1 ocorrencia, e ZERO sao duplicatas — todos tem
--    valor_*/cpf_cnpj/nome_credor/historico DISTINTOS (empenhos/parcelas
--    legitimamente diferentes que a NK nao distingue). UNIQUE INDEX na NK
--    seria errado e UPSERT_DO_NOTHING PULARIA novos registros distintos.
--
-- 2. tce_pb_servidor (22.2M rows): a NK natural inclui colunas NULLABLE
--    nao-coalescidas (municipio: 90.047 NULL; nome_servidor: 201 NULL). Em
--    PostgreSQL, UNIQUE INDEX trata NULL como DISTINTO, entao essas 90k+ rows
--    NAO seriam deduplicadas e ON CONFLICT NAO dispararia -> cada re-run do
--    bucket DUPLICARIA essas rows. NK natural e inseguro aqui.
--
-- 3. tce_pb_licitacao / tce_pb_receita: NK natural seria segura hoje
--    (0 NULL nas cols nao-coalescidas), mas usamos md5 por UNIFORMIDADE e
--    para nao depender de auditoria de NULL a cada mudanca de dados upstream.
--
-- Synthetic md5 (hash de TODAS as cols de negocio) so colapsa rows
-- byte-a-byte identicas (true duplicates do ETL classico, que fazia INSERT
-- plano sem dedup). Cobre 100% sem perda e trata NULL uniformemente
-- (coalesce -> '').
--
-- ── Idempotencia cross-boundary (ETL classico -> incremental) ──────────────
--
-- Para que re-inserir um bucket ja carregado NAO duplique, o _nk_md5 de uma
-- row re-inserida (trigger) deve igualar o da row legacy (populate). Garantido
-- porque ambos usam a MESMA funcao de hash (etl_admin.nk_md5_<tabela>_row,
-- single source of truth) e os valores armazenados sao canonicos:
--   * TEXT: ETL classico (etl/19_tce_pb.py) e o framework (build_typed_select)
--     ambos aplicam trim. coalesce(col,'').
--   * DECIMAL(15,2): escala fixa pela coluna -> ::text canonico ('N.NN') em
--     ambos os caminhos (validado: 10.50 armazenado -> '10.50').
--   * DATE: to_char(col,'YYYY-MM-DD').
--   * SMALLINT (ano/ano_arquivo/ano_licitacao): ::text.
-- Cols de NORMALIZACAO (cnpj_basico, ano, cpf_digitos, cpf_digitos_6,
-- nome_upper, cnpj_basico_proponente, cpf_digitos_proponente) sao EXCLUIDAS:
-- ficam NULL em rows recem-inseridas (populadas por fase posterior) e
-- preenchidas em rows legacy -> inclui-las quebraria a idempotencia.
--
-- Ver ADR-0014 e docs/etl-incremental-guide.md.


-- ============================================================================
-- 0. Pre-flight: a funcao de hash injetiva precisa existir (sql/35a)
-- ============================================================================
-- etl_admin.row_hash_md5() usa array_to_json (injective). NAO redefinimos aqui
-- para evitar drift entre trigger (rows novas) e populate (rows legacy).
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'etl_admin' AND p.proname = 'row_hash_md5'
    ) THEN
        RAISE EXCEPTION
            'etl_admin.row_hash_md5() ausente. Rode sql/35a_pb_extras_synthetic_nk_columns.sql '
            'antes (schema base; aplicado por etl_phase=sql ou ETL completo).';
    END IF;
END $$;


-- ============================================================================
-- tce_pb_despesa
-- ============================================================================
ALTER TABLE tce_pb_despesa ADD COLUMN IF NOT EXISTS _nk_md5 TEXT;
COMMENT ON COLUMN tce_pb_despesa._nk_md5 IS
    'Hash md5 (injetivo) das 41 cols de negocio. Trigger BEFORE INSERT. '
    'UNIQUE INDEX garante idempotencia sem perder registros distintos que '
    'compartilham a NK natural (1037 grupos de colisao reais). Ver ADR-0014.';

-- Single source of truth do hash (trigger E populate chamam esta funcao).
CREATE OR REPLACE FUNCTION etl_admin.nk_md5_tce_pb_despesa_row(r tce_pb_despesa)
RETURNS text AS $func$
  SELECT etl_admin.row_hash_md5(
    coalesce(r.municipio, ''), coalesce(r.codigo_ug, ''),
    coalesce(r.descricao_ug, ''), coalesce(r.numero_empenho, ''),
    to_char(r.data_empenho, 'YYYY-MM-DD'), coalesce(r.mes, ''),
    coalesce(r.cpf_cnpj, ''), coalesce(r.nome_credor, ''),
    coalesce(r.valor_empenhado::text, ''), coalesce(r.valor_liquidado::text, ''),
    coalesce(r.valor_pago::text, ''), coalesce(r.codigo_unidade_orcamentaria, ''),
    coalesce(r.descricao_unidade_orcamentaria, ''), coalesce(r.codigo_funcao, ''),
    coalesce(r.funcao, ''), coalesce(r.codigo_subfuncao, ''),
    coalesce(r.subfuncao, ''), coalesce(r.codigo_programa, ''),
    coalesce(r.programa, ''), coalesce(r.codigo_acao, ''),
    coalesce(r.acao, ''), coalesce(r.codigo_categoria_economica, ''),
    coalesce(r.categoria_economica, ''), coalesce(r.codigo_natureza, ''),
    coalesce(r.grupo_natureza_despesa, ''), coalesce(r.codigo_modalidade_aplicacao, ''),
    coalesce(r.modalidade_aplicacao, ''), coalesce(r.codigo_elemento_despesa, ''),
    coalesce(r.elemento_despesa, ''), coalesce(r.codigo_subelemento, ''),
    coalesce(r.codigo_subelemento_exibicao, ''), coalesce(r.numero_licitacao, ''),
    coalesce(r.modalidade_licitacao, ''), coalesce(r.numero_obra, ''),
    coalesce(r.historico, ''), coalesce(r.codigo_fonte_recurso, ''),
    coalesce(r.descricao_fonte_recurso, ''), coalesce(r.ano_fonte, ''),
    coalesce(r.co, ''), coalesce(r.descricao_co, ''),
    coalesce(r.ano_arquivo::text, '')
  )
$func$ LANGUAGE sql STABLE SET search_path = pg_catalog, public;

CREATE OR REPLACE FUNCTION etl_admin.compute_nk_md5_tce_pb_despesa()
RETURNS trigger AS $func$
BEGIN
  IF NEW._nk_md5 IS NULL THEN
    NEW._nk_md5 := etl_admin.nk_md5_tce_pb_despesa_row(NEW);
  END IF;
  RETURN NEW;
END
$func$ LANGUAGE plpgsql SET search_path = pg_catalog, public;

DROP TRIGGER IF EXISTS trg_compute_nk_md5 ON tce_pb_despesa;
CREATE TRIGGER trg_compute_nk_md5 BEFORE INSERT ON tce_pb_despesa
FOR EACH ROW EXECUTE FUNCTION etl_admin.compute_nk_md5_tce_pb_despesa();


-- ============================================================================
-- tce_pb_servidor
-- ============================================================================
ALTER TABLE tce_pb_servidor ADD COLUMN IF NOT EXISTS _nk_md5 TEXT;
COMMENT ON COLUMN tce_pb_servidor._nk_md5 IS
    'Hash md5 (injetivo) das 11 cols de negocio. Trigger BEFORE INSERT. '
    'NK natural inviavel: municipio/nome_servidor tem NULLs e UNIQUE trata '
    'NULL como distinto -> double-load. Ver ADR-0014.';

CREATE OR REPLACE FUNCTION etl_admin.nk_md5_tce_pb_servidor_row(r tce_pb_servidor)
RETURNS text AS $func$
  SELECT etl_admin.row_hash_md5(
    coalesce(r.municipio, ''), coalesce(r.codigo_ug, ''),
    coalesce(r.descricao_ug, ''), coalesce(r.cpf_cnpj, ''),
    coalesce(r.nome_servidor, ''), coalesce(r.tipo_cargo, ''),
    coalesce(r.descricao_cargo, ''), coalesce(r.valor_vantagem::text, ''),
    to_char(r.data_admissao, 'YYYY-MM-DD'), coalesce(r.matricula, ''),
    coalesce(r.ano_mes, '')
  )
$func$ LANGUAGE sql STABLE SET search_path = pg_catalog, public;

CREATE OR REPLACE FUNCTION etl_admin.compute_nk_md5_tce_pb_servidor()
RETURNS trigger AS $func$
BEGIN
  IF NEW._nk_md5 IS NULL THEN
    NEW._nk_md5 := etl_admin.nk_md5_tce_pb_servidor_row(NEW);
  END IF;
  RETURN NEW;
END
$func$ LANGUAGE plpgsql SET search_path = pg_catalog, public;

DROP TRIGGER IF EXISTS trg_compute_nk_md5 ON tce_pb_servidor;
CREATE TRIGGER trg_compute_nk_md5 BEFORE INSERT ON tce_pb_servidor
FOR EACH ROW EXECUTE FUNCTION etl_admin.compute_nk_md5_tce_pb_servidor();


-- ============================================================================
-- tce_pb_licitacao
-- ============================================================================
ALTER TABLE tce_pb_licitacao ADD COLUMN IF NOT EXISTS _nk_md5 TEXT;
COMMENT ON COLUMN tce_pb_licitacao._nk_md5 IS
    'Hash md5 (injetivo) das 13 cols de negocio. Trigger BEFORE INSERT. '
    'Synthetic NK por uniformidade com despesa/servidor. Ver ADR-0014.';

CREATE OR REPLACE FUNCTION etl_admin.nk_md5_tce_pb_licitacao_row(r tce_pb_licitacao)
RETURNS text AS $func$
  SELECT etl_admin.row_hash_md5(
    coalesce(r.municipio, ''), coalesce(r.codigo_ug, ''),
    coalesce(r.descricao_ug, ''), coalesce(r.numero_licitacao, ''),
    coalesce(r.numero_protocolo_tce, ''), coalesce(r.ano_licitacao::text, ''),
    coalesce(r.modalidade, ''), coalesce(r.objeto_licitacao, ''),
    to_char(r.data_homologacao, 'YYYY-MM-DD'), coalesce(r.nome_proponente, ''),
    coalesce(r.cpf_cnpj_proponente, ''), coalesce(r.valor_ofertado::text, ''),
    coalesce(r.situacao_proposta, '')
  )
$func$ LANGUAGE sql STABLE SET search_path = pg_catalog, public;

CREATE OR REPLACE FUNCTION etl_admin.compute_nk_md5_tce_pb_licitacao()
RETURNS trigger AS $func$
BEGIN
  IF NEW._nk_md5 IS NULL THEN
    NEW._nk_md5 := etl_admin.nk_md5_tce_pb_licitacao_row(NEW);
  END IF;
  RETURN NEW;
END
$func$ LANGUAGE plpgsql SET search_path = pg_catalog, public;

DROP TRIGGER IF EXISTS trg_compute_nk_md5 ON tce_pb_licitacao;
CREATE TRIGGER trg_compute_nk_md5 BEFORE INSERT ON tce_pb_licitacao
FOR EACH ROW EXECUTE FUNCTION etl_admin.compute_nk_md5_tce_pb_licitacao();


-- ============================================================================
-- tce_pb_receita
-- ============================================================================
ALTER TABLE tce_pb_receita ADD COLUMN IF NOT EXISTS _nk_md5 TEXT;
COMMENT ON COLUMN tce_pb_receita._nk_md5 IS
    'Hash md5 (injetivo) das 13 cols de negocio. Trigger BEFORE INSERT. '
    'Synthetic NK por uniformidade com despesa/servidor. Ver ADR-0014.';

CREATE OR REPLACE FUNCTION etl_admin.nk_md5_tce_pb_receita_row(r tce_pb_receita)
RETURNS text AS $func$
  SELECT etl_admin.row_hash_md5(
    coalesce(r.municipio, ''), coalesce(r.codigo_ug, ''),
    coalesce(r.descricao_ug, ''), coalesce(r.mes_ano, ''),
    coalesce(r.ano::text, ''), coalesce(r.codigo_receita, ''),
    coalesce(r.descricao_receita, ''), coalesce(r.tipo_atualizacao_receita, ''),
    coalesce(r.valor::text, ''), coalesce(r.codigo_fonte_recurso, ''),
    coalesce(r.descricao_fonte_recurso, ''), coalesce(r.co, ''),
    coalesce(r.descricao_co, '')
  )
$func$ LANGUAGE sql STABLE SET search_path = pg_catalog, public;

CREATE OR REPLACE FUNCTION etl_admin.compute_nk_md5_tce_pb_receita()
RETURNS trigger AS $func$
BEGIN
  IF NEW._nk_md5 IS NULL THEN
    NEW._nk_md5 := etl_admin.nk_md5_tce_pb_receita_row(NEW);
  END IF;
  RETURN NEW;
END
$func$ LANGUAGE plpgsql SET search_path = pg_catalog, public;

DROP TRIGGER IF EXISTS trg_compute_nk_md5 ON tce_pb_receita;
CREATE TRIGGER trg_compute_nk_md5 BEFORE INSERT ON tce_pb_receita
FOR EACH ROW EXECUTE FUNCTION etl_admin.compute_nk_md5_tce_pb_receita();


-- Populate de _nk_md5 nas rows legacy: feito via Python autocommit (batched +
-- partial index), reusando as funcoes nk_md5_<tabela>_row acima:
--   python -m etl.refresh_post_incremental --source tce_pb --populate-only
-- Em seguida, sql/42z faz dedupe + UNIQUE INDEX. Ver ADR-0014.
